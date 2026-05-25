import logging
import pandas as pd
import numpy as np
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from src.database.models import AnomalyAlert
from src.database.queries import insert_ohlcv_record
from config.settings import VOLATILITY_THRESHOLD, PRICE_DROP_THRESHOLD

logger = logging.getLogger(__name__)

def process_and_impute_ohlcv(symbol: str, raw_ohlcv_data: list) -> pd.DataFrame:
    """
    Transforms raw OHLCV API data into a standardized, complete Pandas DataFrame.
    Performs forward-fill imputation to resolve gaps and null value records.
    """
    if not raw_ohlcv_data:
        return pd.DataFrame()

    # CoinGecko OHLCV format: [timestamp_ms, open, high, low, close]
    # Note: Volume is not provided in CoinGecko's OHLCV array, so we mock or set to 0.0,
    # or handle it if passing a comprehensive list. We default columns here.
    columns = ["timestamp_ms", "open", "high", "low", "close"]
    df = pd.DataFrame(raw_ohlcv_data, columns=columns)
    
    # Convert timestamps
    df["timestamp"] = pd.to_datetime(df["timestamp_ms"], unit="ms")
    df.drop(columns=["timestamp_ms"], inplace=True)
    
    # Ensure sorted order
    df.sort_values("timestamp", inplace=True)
    df.set_index("timestamp", inplace=True)
    
    # 1. Generate full hourly index to locate gaps
    full_index = pd.date_range(start=df.index.min(), end=df.index.max(), freq="h")
    df = df.reindex(full_index)
    df.index.name = "timestamp"

    # 2. Impute prices using forward fill (limit to 3 hours for stability)
    df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].ffill(limit=3)
    
    # 3. Create mock/fallback volume column if missing
    if "volume" not in df.columns:
        df["volume"] = 0.0
    else:
        df["volume"] = df["volume"].fillna(0.0)

    # Clean extreme out-of-bound NaN rows if any remain
    df.dropna(subset=["close"], inplace=True)
    
    return df

def calculate_indicators_and_anomalies(session: Session, symbol: str, df: pd.DataFrame) -> None:
    """
    Calculates moving technical indicators (rolling volatility, SMA) 
    and checks statistical thresholds to raise system anomaly alerts.
    """
    if df.empty or len(df) < 5:
        return

    # Calculate hourly return percentages
    df["returns"] = df["close"].pct_change()
    
    # 24-hour Simple Moving Average (SMA)
    df["sma_24h"] = df["close"].rolling(window=24, min_periods=1).mean()

    # Rolling standard deviation of hourly returns (volatility index)
    df["volatility_24h"] = df["returns"].rolling(window=24, min_periods=1).std().fillna(0.0)

    # 7-day lookback for baseline standard deviation & mean returns
    # (Using maximum available size up to 168 hours)
    lookback = min(len(df), 168)
    rolling_returns_mean = df["returns"].rolling(window=lookback, min_periods=1).mean()
    rolling_returns_std = df["returns"].rolling(window=lookback, min_periods=1).std().fillna(1e-6)

    # Z-Score of the current return
    df["z_score"] = (df["returns"] - rolling_returns_mean) / rolling_returns_std

    # Iterate and write back to database, checking for anomalies
    for timestamp, row in df.iterrows():
        close_price = float(row["close"])
        volatility = float(row["volatility_24h"])
        z_score = float(row["z_score"])
        hourly_return = float(row["returns"]) if not pd.isna(row["returns"]) else 0.0

        # Save record
        insert_ohlcv_record(
            session=session,
            symbol=symbol,
            timestamp=timestamp,
            open_p=float(row["open"]),
            high_p=float(row["high"]),
            low_p=float(row["low"]),
            close_p=close_price,
            volume_p=float(row["volume"]),
            volatility=volatility
        )

        # Skip anomaly checking on first row due to NaN returns
        if pd.isna(row["returns"]):
            continue

        # Anomaly Condition 1: Volatility Limit breach
        if volatility > VOLATILITY_THRESHOLD:
            _raise_anomaly(
                session=session,
                symbol=symbol,
                timestamp=timestamp,
                anomaly_type="EXCESSIVE_VOLATILITY",
                detected=volatility,
                threshold=VOLATILITY_THRESHOLD,
                description=f"Hourly volatility spiked to {volatility:.2%}, surpassing risk threshold of {VOLATILITY_THRESHOLD:.2%}."
            )

        # Anomaly Condition 2: Flash Crash (Price drops by 5% or more in 1 hour)
        if hourly_return <= -PRICE_DROP_THRESHOLD:
            _raise_anomaly(
                session=session,
                symbol=symbol,
                timestamp=timestamp,
                anomaly_type="FLASH_CRASH",
                detected=hourly_return,
                threshold=-PRICE_DROP_THRESHOLD,
                description=f"Asset price dropped by {hourly_return:.2%} in a single hour, breaching limit of -{PRICE_DROP_THRESHOLD:.2%}."
            )

        # Anomaly Condition 3: Statistical Outlier (Z-Score drop exceeds 3 sigma)
        if z_score <= -3.0:
            _raise_anomaly(
                session=session,
                symbol=symbol,
                timestamp=timestamp,
                anomaly_type="STATISTICAL_CRASH",
                detected=z_score,
                threshold=-3.0,
                description=f"Hourly return exhibited a statistical drop of {z_score:.2f} standard deviations (Z-score)."
            )

def _raise_anomaly(session: Session, symbol: str, timestamp: datetime, anomaly_type: str, detected: float, threshold: float, description: str) -> None:
    """
    Submits an anomaly alert log to the database. 
    Prevents duplicate alert logs for the exact same event.
    """
    # Check if this anomaly was already logged
    exists = session.query(AnomalyAlert).filter(
        AnomalyAlert.symbol == symbol,
        AnomalyAlert.timestamp == timestamp,
        AnomalyAlert.anomaly_type == anomaly_type
    ).first()

    if not exists:
        logger.warning(f"🚨 [ANOMALY DETECTED] {symbol} | Type: {anomaly_type} | Val: {detected:.4f} | Desc: {description}")
        alert = AnomalyAlert(
            symbol=symbol,
            timestamp=timestamp,
            anomaly_type=anomaly_type,
            detected_value=Decimal(str(detected)),
            threshold_value=Decimal(str(threshold)),
            description=description,
            alert_dispatched=False
        )
        session.add(alert)
