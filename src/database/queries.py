import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.database.models import Asset, MarketOHLCVHourly, OrderbookLiquidity, AnomalyAlert

logger = logging.getLogger(__name__)

def upsert_assets(session: Session, assets_list: List[Dict[str, Any]]) -> None:
    """
    Performs bulk UPSERT of tracking asset records to avoid key collisions.
    """
    for asset_data in assets_list:
        stmt = text("""
            INSERT INTO assets (symbol, name, coingecko_id, current_market_cap, current_circulating_supply, updated_at)
            VALUES (:symbol, :name, :coingecko_id, :current_market_cap, :current_circulating_supply, :updated_at)
            ON CONFLICT (symbol) DO UPDATE 
            SET current_market_cap = EXCLUDED.current_market_cap,
                current_circulating_supply = EXCLUDED.current_circulating_supply,
                updated_at = EXCLUDED.updated_at;
        """)
        session.execute(stmt, {
            "symbol": asset_data["symbol"],
            "name": asset_data["name"],
            "coingecko_id": asset_data["coingecko_id"],
            "current_market_cap": asset_data.get("current_market_cap", 0.0),
            "current_circulating_supply": asset_data.get("current_circulating_supply", 0.0),
            "updated_at": datetime.utcnow()
        })

def insert_ohlcv_record(session: Session, symbol: str, timestamp: datetime, open_p: float, high_p: float, low_p: float, close_p: float, volume_p: float, volatility: float = None) -> None:
    """
    Inserts or updates an hourly OHLCV timeseries tick.
    """
    stmt = text("""
        INSERT INTO market_ohlcv_hourly (symbol, timestamp, open, high, low, close, volume, hourly_volatility, ingested_at)
        VALUES (:symbol, :timestamp, :open, :high, :low, :close, :volume, :hourly_volatility, :ingested_at)
        ON CONFLICT (symbol, timestamp) DO UPDATE
        SET open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            hourly_volatility = COALESCE(EXCLUDED.hourly_volatility, market_ohlcv_hourly.hourly_volatility),
            ingested_at = EXCLUDED.ingested_at;
    """)
    session.execute(stmt, {
        "symbol": symbol,
        "timestamp": timestamp,
        "open": open_p,
        "high": high_p,
        "low": low_p,
        "close": close_p,
        "volume": volume_p,
        "hourly_volatility": volatility,
        "ingested_at": datetime.utcnow()
    })

def insert_liquidity_record(session: Session, symbol: str, timestamp: datetime, bid_depth: float, ask_depth: float, spread: float) -> None:
    """
    Inserts a liquidity depth tick into orderbook records.
    """
    record = OrderbookLiquidity(
        symbol=symbol,
        timestamp=timestamp,
        bid_depth_1pct=bid_depth,
        ask_depth_1pct=ask_depth,
        spread_percentage=spread
    )
    session.add(record)

def get_top_movers(session: Session, hours: int = 24) -> List[Tuple[str, float, float, float]]:
    """
    SQL window query to identify the top gainers/losers over a sliding window.
    Returns: List of tuples [(symbol, start_price, end_price, pct_change)]
    """
    time_limit = datetime.utcnow() - timedelta(hours=hours)
    
    query = text("""
        WITH ranked_ticks AS (
            SELECT 
                symbol,
                timestamp,
                close,
                FIRST_VALUE(close) OVER (PARTITION BY symbol ORDER BY timestamp ASC) as start_price,
                LAST_VALUE(close) OVER (PARTITION BY symbol ORDER BY timestamp ASC 
                    RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) as end_price,
                ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY timestamp DESC) as rn
            FROM market_ohlcv_hourly
            WHERE timestamp >= :time_limit
        )
        SELECT 
            symbol,
            start_price,
            end_price,
            ROUND(((end_price - start_price) / start_price * 100.0)::numeric, 2) as pct_change
        FROM ranked_ticks
        WHERE rn = 1 AND start_price > 0
        ORDER BY pct_change DESC;
    """)
    
    result = session.execute(query, {"time_limit": time_limit})
    return [row for row in result]

def get_historical_volatility_stats(session: Session, symbol: str, limit: int = 168) -> List[Dict[str, Any]]:
    """
    Extracts statistical rolling indicators over standard lookbacks (e.g., 7 days = 168 hours).
    Employs SQL analytic functions to calculate rolling averages and standard dev.
    """
    query = text("""
        SELECT 
            timestamp,
            close,
            volume,
            AVG(close) OVER (
                ORDER BY timestamp ASC 
                ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
            ) AS sma_24h,
            STDDEV(close) OVER (
                ORDER BY timestamp ASC 
                ROWS BETWEEN 167 PRECEDING AND CURRENT ROW
            ) AS rolling_std_7d
        FROM market_ohlcv_hourly
        WHERE symbol = :symbol
        ORDER BY timestamp DESC
        LIMIT :limit;
    """)
    
    result = session.execute(query, {"symbol": symbol, "limit": limit})
    return [
        {
            "timestamp": row[0],
            "close": float(row[1]),
            "volume": float(row[2]),
            "sma_24h": float(row[3]) if row[3] is not None else 0.0,
            "rolling_std_7d": float(row[4]) if row[4] is not None else 0.0
        }
        for row in result
    ]

def get_undispatched_alerts(session: Session) -> List[AnomalyAlert]:
    """
    Retrieves all newly raised alerts that require notification broadcasts.
    """
    return session.query(AnomalyAlert).filter(AnomalyAlert.alert_dispatched == False).all()

def mark_alerts_as_dispatched(session: Session, alert_ids: List[int]) -> None:
    """
    Updates notification states in transaction blocks to avoid double alerting.
    """
    session.query(AnomalyAlert).filter(AnomalyAlert.id.in_(alert_ids)).update(
        {AnomalyAlert.alert_dispatched: True}, synchronize_session=False
    )
