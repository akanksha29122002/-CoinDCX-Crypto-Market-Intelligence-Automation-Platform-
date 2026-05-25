from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from decimal import Decimal
from typing import Optional

class AssetValidateModel(BaseModel):
    symbol: str = Field(..., min_length=2, max_length=12)
    name: str = Field(..., min_length=1)
    coingecko_id: str
    current_market_cap: Decimal = Field(default=Decimal("0.0"), ge=0)
    current_circulating_supply: Decimal = Field(default=Decimal("0.0"), ge=0)

    @field_validator('symbol')
    @classmethod
    def format_symbol(cls, value: str) -> str:
        return value.strip().upper()

class OHLCVValidateModel(BaseModel):
    symbol: str
    timestamp: datetime
    open: Decimal = Field(..., gt=0)
    high: Decimal = Field(..., gt=0)
    low: Decimal = Field(..., gt=0)
    close: Decimal = Field(..., gt=0)
    volume: Decimal = Field(..., ge=0)

    @field_validator('high')
    @classmethod
    def validate_high_price(cls, v: Decimal, info) -> Decimal:
        values = info.data
        if 'open' in values and v < values['open']:
            raise ValueError("High price cannot be less than Open price")
        if 'close' in values and v < values['close']:
            raise ValueError("High price cannot be less than Close price")
        return v

    @field_validator('low')
    @classmethod
    def validate_low_price(cls, v: Decimal, info) -> Decimal:
        values = info.data
        if 'open' in values and v > values['open']:
            raise ValueError("Low price cannot be greater than Open price")
        if 'close' in values and v > values['close']:
            raise ValueError("Low price cannot be greater than Close price")
        return v

class OrderbookLiquidityValidateModel(BaseModel):
    symbol: str
    timestamp: datetime
    bid_depth_1pct: Decimal = Field(..., ge=0)
    ask_depth_1pct: Decimal = Field(..., ge=0)
    spread_percentage: Decimal = Field(..., ge=0, le=100)
