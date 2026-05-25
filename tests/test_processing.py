import pytest
from datetime import datetime
from decimal import Decimal
from pydantic import ValidationError
from src.processing.cleaner import AssetValidateModel, OHLCVValidateModel

def test_asset_validate_success():
    """
    Verifies that a valid asset payload parses and capitalizes correctly.
    """
    data = {
        "symbol": "btc",
        "name": "Bitcoin",
        "coingecko_id": "bitcoin",
        "current_market_cap": "1200000000000.50",
        "current_circulating_supply": "19500000.00"
    }
    validated = AssetValidateModel(**data)
    assert validated.symbol == "BTC"
    assert validated.name == "Bitcoin"
    assert validated.current_market_cap == Decimal("1200000000000.50")

def test_asset_validate_failure():
    """
    Verifies that invalid asset inputs raise Pydantic validation errors.
    """
    invalid_data = {
        "symbol": "btc",
        "name": "Bitcoin",
        "coingecko_id": "bitcoin",
        "current_market_cap": "-100.00",  # Cannot be negative
        "current_circulating_supply": "19500000.00"
    }
    with pytest.raises(ValidationError):
        AssetValidateModel(**invalid_data)

def test_ohlcv_validate_success():
    """
    Verifies that clean OHLCV values pass the data contract successfully.
    """
    data = {
        "symbol": "ETH",
        "timestamp": datetime.utcnow(),
        "open": "3000.00",
        "high": "3100.00",
        "low": "2950.00",
        "close": "3050.00",
        "volume": "1500000.00"
    }
    validated = OHLCVValidateModel(**data)
    assert validated.close == Decimal("3050.00")

def test_ohlcv_validate_boundary_failure():
    """
    Verifies that high-low price boundary errors are captured.
    """
    invalid_data = {
        "symbol": "ETH",
        "timestamp": datetime.utcnow(),
        "open": "3000.00",
        "high": "2900.00",  # High price cannot be less than open price
        "low": "2950.00",
        "close": "3050.00",
        "volume": "1500000.00"
    }
    with pytest.raises(ValidationError) as excinfo:
        OHLCVValidateModel(**invalid_data)
    assert "High price cannot be less than Open price" in str(excinfo.value)
