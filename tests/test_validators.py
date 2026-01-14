"""
Test suite for DataValidator.

Tests all validation functionality including:
- Valid data validation
- Detection of various data quality issues
- Data cleaning functions
- Gap detection and handling
"""

import pytest
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import pytz

from src.data.validators import DataValidator, validate_ohlcv, clean_ohlcv, detect_and_handle_gaps


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def valid_ohlcv_data():
    """Create a valid OHLCV dataframe for testing."""
    dates = pd.date_range(start='2024-01-01', end='2024-01-02', freq='1h', tz='UTC')
    np.random.seed(42)  # For reproducibility

    df = pd.DataFrame({
        'symbol': 'BTC/USD',
        'open': 50000 + np.random.randn(len(dates)) * 100,
        'high': 50100 + np.random.randn(len(dates)) * 100,
        'low': 49900 + np.random.randn(len(dates)) * 100,
        'close': 50000 + np.random.randn(len(dates)) * 100,
        'volume': np.random.rand(len(dates)) * 1000,
    }, index=dates)

    # Ensure price consistency
    df['high'] = df[['open', 'close']].max(axis=1) + np.abs(np.random.randn(len(df)) * 50)
    df['low'] = df[['open', 'close']].min(axis=1) - np.abs(np.random.randn(len(df)) * 50)

    return df


@pytest.fixture
def strict_validator():
    """Create a strict mode validator."""
    return DataValidator(strict_mode=True)


@pytest.fixture
def non_strict_validator():
    """Create a non-strict mode validator."""
    return DataValidator(strict_mode=False)


# ============================================================================
# Test Valid Data
# ============================================================================

class TestValidData:
    """Tests for valid data handling."""

    def test_valid_data_passes_validation(self, valid_ohlcv_data, strict_validator):
        """Test that valid data passes all checks."""
        result = strict_validator.validate(valid_ohlcv_data, symbol="BTC/USD")
        assert result is True, "Valid data should pass validation"

    def test_valid_data_with_convenience_function(self, valid_ohlcv_data):
        """Test convenience validation function with valid data."""
        result = validate_ohlcv(valid_ohlcv_data, symbol="BTC/USD", strict=True)
        assert result is True, "Convenience function should return True for valid data"


# ============================================================================
# Test Invalid Data Detection
# ============================================================================

class TestInvalidDataDetection:
    """Tests for detecting various data quality issues."""

    def test_empty_dataframe_fails(self, strict_validator):
        """Test that empty dataframe fails validation."""
        df = pd.DataFrame()
        result = strict_validator.validate(df)
        assert result is False, "Empty dataframe should fail validation"

    def test_missing_columns_fails(self, valid_ohlcv_data, strict_validator):
        """Test that missing columns fail validation."""
        df = valid_ohlcv_data.drop('close', axis=1)
        result = strict_validator.validate(df)
        assert result is False, "Missing columns should fail validation"

    def test_null_values_fails(self, valid_ohlcv_data, strict_validator):
        """Test that null values fail validation in strict mode."""
        df = valid_ohlcv_data.copy()
        df.loc[df.index[5:8], 'close'] = np.nan
        result = strict_validator.validate(df)
        assert result is False, "Null values should fail validation"

    def test_negative_values_fails(self, valid_ohlcv_data, strict_validator):
        """Test that negative values fail validation."""
        df = valid_ohlcv_data.copy()
        df.loc[df.index[3], 'volume'] = -100
        result = strict_validator.validate(df)
        assert result is False, "Negative values should fail validation"

    def test_price_inconsistency_fails(self, valid_ohlcv_data, strict_validator):
        """Test that price inconsistency (low > high) fails validation."""
        df = valid_ohlcv_data.copy()
        df.loc[df.index[10], 'low'] = 52000
        df.loc[df.index[10], 'high'] = 51000
        result = strict_validator.validate(df)
        assert result is False, "Price inconsistency should fail validation"

    def test_duplicate_timestamps_fails(self, valid_ohlcv_data, strict_validator):
        """Test that duplicate timestamps fail validation."""
        df = valid_ohlcv_data.copy()
        duplicate_row = df.iloc[0:1].copy()
        df = pd.concat([df, duplicate_row])
        result = strict_validator.validate(df)
        assert result is False, "Duplicate timestamps should fail validation"


# ============================================================================
# Test Gap Detection
# ============================================================================

class TestGapDetection:
    """Tests for gap detection functionality."""

    def test_gap_detection_works(self, valid_ohlcv_data, non_strict_validator):
        """Test that gaps are detected."""
        df = valid_ohlcv_data.drop(valid_ohlcv_data.index[10:15])
        result = non_strict_validator.validate(df)

        # In non-strict mode, gaps don't fail but should be detected
        assert 'gaps' in non_strict_validator.validation_results, \
            "Gap detection should identify gaps in data"


# ============================================================================
# Test Data Cleaning
# ============================================================================

class TestDataCleaning:
    """Tests for data cleaning functions."""

    def test_clean_removes_duplicates(self, valid_ohlcv_data):
        """Test that cleaning removes duplicate rows."""
        df = valid_ohlcv_data.copy()
        duplicate_row = df.iloc[0:1].copy()
        df = pd.concat([df, duplicate_row])

        original_len = len(df)
        df_clean = clean_ohlcv(df)

        assert len(df_clean) < original_len, "Cleaning should remove duplicates"

    def test_clean_sorts_by_timestamp(self, valid_ohlcv_data):
        """Test that cleaning sorts data by timestamp."""
        df = valid_ohlcv_data.sample(frac=1)  # Shuffle rows
        assert not df.index.is_monotonic_increasing, "Data should be shuffled"

        df_clean = clean_ohlcv(df)
        assert df_clean.index.is_monotonic_increasing, "Cleaned data should be sorted"

    def test_gap_handling_interpolates(self, valid_ohlcv_data):
        """Test that gap handling interpolates small gaps."""
        df = valid_ohlcv_data.drop(valid_ohlcv_data.index[10:12])
        original_len = len(df)

        df_handled = detect_and_handle_gaps(df, max_gap_minutes=120)

        assert len(df_handled) >= original_len, \
            "Gap handling should not reduce data size"


# ============================================================================
# Run Tests (for backward compatibility with script)
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
