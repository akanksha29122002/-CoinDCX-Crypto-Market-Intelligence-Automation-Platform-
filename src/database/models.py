from sqlalchemy import Column, String, Numeric, DateTime, Integer, ForeignKey, Boolean, text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from src.database.db_connection import Base

class Asset(Base):
    __tablename__ = "assets"

    symbol = Column(String(12), primary_key=True)
    name = Column(String(100), nullable=False)
    coingecko_id = Column(String(100), unique=True, nullable=False)
    current_market_cap = Column(Numeric(24, 4), default=0.0)
    current_circulating_supply = Column(Numeric(24, 4), default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    ohlcv_records = relationship("MarketOHLCVHourly", back_populates="asset", cascade="all, delete-orphan")
    liquidity_records = relationship("OrderbookLiquidity", back_populates="asset", cascade="all, delete-orphan")
    anomaly_records = relationship("AnomalyAlert", back_populates="asset", cascade="all, delete-orphan")

class MarketOHLCVHourly(Base):
    __tablename__ = "market_ohlcv_hourly"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(12), ForeignKey("assets.symbol", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    open = Column(Numeric(18, 8), nullable=False)
    high = Column(Numeric(18, 8), nullable=False)
    low = Column(Numeric(18, 8), nullable=False)
    close = Column(Numeric(18, 8), nullable=False)
    volume = Column(Numeric(24, 4), nullable=False)
    hourly_volatility = Column(Numeric(8, 4), nullable=True) # Volatility calculated over moving windows
    ingested_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("symbol", "timestamp", name="unique_symbol_timestamp_constraint"),
    )

    asset = relationship("Asset", back_populates="ohlcv_records")

class OrderbookLiquidity(Base):
    __tablename__ = "orderbook_liquidity"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(12), ForeignKey("assets.symbol", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    bid_depth_1pct = Column(Numeric(18, 8), nullable=False)
    ask_depth_1pct = Column(Numeric(18, 8), nullable=False)
    spread_percentage = Column(Numeric(6, 4), nullable=False)
    ingested_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    asset = relationship("Asset", back_populates="liquidity_records")

class AnomalyAlert(Base):
    __tablename__ = "anomaly_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(12), ForeignKey("assets.symbol", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    anomaly_type = Column(String(30), nullable=False) # e.g. CRASH, SPIKE, VOLATILITY
    detected_value = Column(Numeric(18, 8), nullable=False)
    threshold_value = Column(Numeric(18, 8), nullable=False)
    description = Column(String, nullable=True)
    alert_dispatched = Column(Boolean, default=False, nullable=False)
    logged_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    asset = relationship("Asset", back_populates="anomaly_records")
