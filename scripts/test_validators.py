"""
Test script for DataValidator.

Tests all validation functionality including:
- Valid data validation
- Detection of various data quality issues
- Data cleaning functions
- Gap detection and handling
"""

import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import pytz

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.validators import DataValidator, validate_ohlcv, clean_ohlcv, detect_and_handle_gaps


def create_valid_data() -> pd.DataFrame:
    """Create a valid OHLCV dataframe for testing."""
    dates = pd.date_range(start='2024-01-01', end='2024-01-02', freq='1h', tz='UTC')
    
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


def test_valid_data():
    """Test validator with valid data."""
    print("\n" + "="*70)
    print(" Test 1: Valid Data")
    print("="*70 + "\n")
    
    df = create_valid_data()
    validator = DataValidator(strict_mode=True)
    result = validator.validate(df, symbol="BTC/USD")
    
    if result:
        print("✓ Valid data passed all checks")
        return True
    else:
        print("✗ Valid data failed validation")
        validator.print_validation_report()
        return False


def test_empty_data():
    """Test validator with empty dataframe."""
    print("\n" + "="*70)
    print(" Test 2: Empty Data")
    print("="*70 + "\n")
    
    df = pd.DataFrame()
    validator = DataValidator(strict_mode=True)
    result = validator.validate(df)
    
    if not result:
        print("✓ Correctly detected empty dataframe")
        return True
    else:
        print("✗ Should have failed on empty dataframe")
        return False


def test_missing_columns():
    """Test validator with missing columns."""
    print("\n" + "="*70)
    print(" Test 3: Missing Columns")
    print("="*70 + "\n")
    
    df = create_valid_data()
    df = df.drop('close', axis=1)  # Remove close column
    
    validator = DataValidator(strict_mode=True)
    result = validator.validate(df)
    
    if not result:
        print("✓ Correctly detected missing columns")
        return True
    else:
        print("✗ Should have failed on missing columns")
        return False


def test_null_values():
    """Test validator with null values."""
    print("\n" + "="*70)
    print(" Test 4: Null Values")
    print("="*70 + "\n")
    
    df = create_valid_data()
    df.loc[df.index[5:8], 'close'] = np.nan  # Add some nulls
    
    validator = DataValidator(strict_mode=True)
    result = validator.validate(df)
    
    if not result:
        print("✓ Correctly detected null values")
        return True
    else:
        print("✗ Should have failed on null values")
        return False


def test_negative_values():
    """Test validator with negative values."""
    print("\n" + "="*70)
    print(" Test 5: Negative Values")
    print("="*70 + "\n")
    
    df = create_valid_data()
    df.loc[df.index[3], 'volume'] = -100  # Add negative volume
    
    validator = DataValidator(strict_mode=True)
    result = validator.validate(df)
    
    if not result:
        print("✓ Correctly detected negative values")
        return True
    else:
        print("✗ Should have failed on negative values")
        return False


def test_price_inconsistency():
    """Test validator with inconsistent prices."""
    print("\n" + "="*70)
    print(" Test 6: Price Inconsistency")
    print("="*70 + "\n")
    
    df = create_valid_data()
    # Make low > high (inconsistent)
    df.loc[df.index[10], 'low'] = 52000
    df.loc[df.index[10], 'high'] = 51000
    
    validator = DataValidator(strict_mode=True)
    result = validator.validate(df)
    
    if not result:
        print("✓ Correctly detected price inconsistency")
        return True
    else:
        print("✗ Should have failed on price inconsistency")
        return False


def test_duplicates():
    """Test validator with duplicate timestamps."""
    print("\n" + "="*70)
    print(" Test 7: Duplicate Timestamps")
    print("="*70 + "\n")
    
    df = create_valid_data()
    # Add duplicate timestamp
    duplicate_row = df.iloc[0:1].copy()
    df = pd.concat([df, duplicate_row])
    
    validator = DataValidator(strict_mode=True)
    result = validator.validate(df)
    
    if not result:
        print("✓ Correctly detected duplicate timestamps")
        return True
    else:
        print("✗ Should have failed on duplicate timestamps")
        return False


def test_gaps():
    """Test gap detection."""
    print("\n" + "="*70)
    print(" Test 8: Gap Detection")
    print("="*70 + "\n")
    
    df = create_valid_data()
    # Remove some rows to create gaps
    df = df.drop(df.index[10:15])
    
    validator = DataValidator(strict_mode=False)  # Use non-strict mode
    result = validator.validate(df)
    
    # Gaps should be detected but not fail validation in non-strict mode
    if 'gaps' in validator.validation_results:
        print("✓ Gap detection working")
        print(f"  Message: {validator.validation_results['gaps']['message']}")
        return True
    else:
        print("✗ Gap detection not working")
        return False


def test_clean_function():
    """Test data cleaning function."""
    print("\n" + "="*70)
    print(" Test 9: Data Cleaning")
    print("="*70 + "\n")
    
    df = create_valid_data()
    
    # Add issues that cleaning should fix
    duplicate_row = df.iloc[0:1].copy()
    df = pd.concat([df, duplicate_row])  # Add duplicate
    df = df.sample(frac=1)  # Shuffle rows
    
    print(f"Before cleaning: {len(df)} rows, sorted={df.index.is_monotonic_increasing}")
    
    df_clean = clean_ohlcv(df)
    
    print(f"After cleaning: {len(df_clean)} rows, sorted={df_clean.index.is_monotonic_increasing}")
    
    if len(df_clean) < len(df) and df_clean.index.is_monotonic_increasing:
        print("✓ Data cleaning working correctly")
        return True
    else:
        print("✗ Data cleaning not working properly")
        return False


def test_gap_handling():
    """Test gap detection and handling."""
    print("\n" + "="*70)
    print(" Test 10: Gap Handling")
    print("="*70 + "\n")
    
    df = create_valid_data()
    
    # Create a small gap (should be interpolated)
    df_with_gap = df.drop(df.index[10:12])
    
    print(f"Before gap handling: {len(df_with_gap)} rows")
    
    df_handled = detect_and_handle_gaps(df_with_gap, max_gap_minutes=120)
    
    print(f"After gap handling: {len(df_handled)} rows")
    
    if len(df_handled) >= len(df_with_gap):
        print("✓ Gap handling working")
        return True
    else:
        print("✗ Gap handling not working")
        return False


def test_convenience_function():
    """Test convenience validation function."""
    print("\n" + "="*70)
    print(" Test 11: Convenience Function")
    print("="*70 + "\n")
    
    df = create_valid_data()
    result = validate_ohlcv(df, symbol="BTC/USD", strict=True)
    
    if result:
        print("✓ Convenience function working")
        return True
    else:
        print("✗ Convenience function failed")
        return False


def run_all_tests():
    """Run all validation tests."""
    print("\n" + "="*70)
    print(" RUNNING DATA VALIDATOR TESTS")
    print("="*70)
    
    tests = [
        test_valid_data,
        test_empty_data,
        test_missing_columns,
        test_null_values,
        test_negative_values,
        test_price_inconsistency,
        test_duplicates,
        test_gaps,
        test_clean_function,
        test_gap_handling,
        test_convenience_function,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n✗ Test {test.__name__} raised exception: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "="*70)
    print(" TEST SUMMARY")
    print("="*70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\nPassed: {passed}/{total} tests")
    
    if passed == total:
        print("\n✓ ALL TESTS PASSED!\n")
        return True
    else:
        print(f"\n✗ {total - passed} TEST(S) FAILED\n")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
