import pytest
import pandas as pd
from src.processing.analytics import process_and_impute_ohlcv

def test_pandas_imputation_success():
    """
    Verifies that raw datasets with gaps are forward-filled correctly.
    """
    # 2 ticks separated by a 2-hour gap (1 gap row should be inserted)
    raw_data = [
        [1716656400000, 68000.0, 68500.0, 67800.0, 68200.0],  # 2024-05-25 17:00 UTC
        [1716663600000, 68300.0, 68900.0, 68100.0, 68700.0]   # 2024-05-25 19:00 UTC (18:00 gap)
    ]
    
    df = process_and_impute_ohlcv("BTC", raw_data)
    
    # 3 rows should exist after hourly gap index generation
    assert len(df) == 3
    
    # Check that index 18:00 was inserted and forward filled close from 17:00
    gap_row = df.loc["2024-05-25 18:00:00"]
    assert gap_row["close"] == 68200.0
    assert gap_row["volume"] == 0.0  # Vol is zero-filled
