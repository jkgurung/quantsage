"""
Test suite for FeatureEngineer with data leakage prevention.

Critical tests:
1. Data leakage prevention - verify test data uses training statistics
2. Technical indicators - verify calculations are correct
3. Cyclical features - verify time encoding
4. Save/load - verify persistence works
"""

import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import pytz
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.features import FeatureEngineer


def create_sample_data(n_rows=1000, start_price=50000) -> pd.DataFrame:
    """Create sample OHLCV data for testing."""
    dates = pd.date_range(start='2024-01-01', periods=n_rows, freq='1h', tz='UTC')
    
    # Create realistic price movement
    returns = np.random.randn(n_rows) * 0.01  # 1% volatility
    prices = start_price * np.exp(np.cumsum(returns))
    
    df = pd.DataFrame({
        'symbol': 'BTC/USD',
        'open': prices + np.random.randn(n_rows) * 50,
        'high': prices + np.abs(np.random.randn(n_rows) * 100),
        'low': prices - np.abs(np.random.randn(n_rows) * 100),
        'close': prices,
        'volume': np.abs(np.random.randn(n_rows) * 1000 + 5000),
    }, index=dates)
    
    # Ensure price consistency
    df['high'] = df[['open', 'close']].max(axis=1) + np.abs(np.random.randn(n_rows) * 50)
    df['low'] = df[['open', 'close']].min(axis=1) - np.abs(np.random.randn(n_rows) * 50)
    
    return df


def test_data_leakage_prevention():
    """
    CRITICAL TEST: Verify no data leakage in normalization.
    
    This test ensures that test data normalization uses ONLY training data
    statistics, not test data statistics.
    """
    print("\n" + "="*70)
    print(" TEST 1: Data Leakage Prevention (CRITICAL)")
    print("="*70 + "\n")
    
    # Create data
    data = create_sample_data(n_rows=1000)
    
    # Split into train/test (80/20)
    split_idx = 800
    train_df = data[:split_idx].copy()
    test_df = data[split_idx:].copy()
    
    print(f"Training samples: {len(train_df)}")
    print(f"Test samples: {len(test_df)}")
    
    # Fit on training data only
    fe = FeatureEngineer()
    train_transformed = fe.fit_transform(train_df)
    
    if train_transformed is None:
        print("✗ Failed to fit_transform training data")
        return False
    
    print(f"\n✓ Fitted on training data")
    print(f"  Features: {len(fe.get_feature_names())}")
    print(f"  Scaler mean (first 5): {fe.scaler.mean_[:5]}")
    
    # Transform test data using training statistics
    test_transformed = fe.transform(test_df)
    
    if test_transformed is None:
        print("✗ Failed to transform test data")
        return False
    
    print(f"✓ Transformed test data using training statistics")
    
    # CRITICAL CHECK: Verify scaler was fitted on train data only
    # The scaler's mean should match training data, not test data
    train_close_mean = train_df['close'].mean()
    test_close_mean = test_df['close'].mean()
    
    # Calculate what the normalized close should be for a test sample
    # using training statistics
    if 'close' in fe.feature_columns:
        close_idx = fe.feature_columns.index('close')
        scaler_close_mean = fe.scaler.mean_[close_idx]
        scaler_close_std = fe.scaler.scale_[close_idx]
        
        print(f"\n✓ Data Leakage Check:")
        print(f"  Training close mean: {train_close_mean:.2f}")
        print(f"  Test close mean: {test_close_mean:.2f}")
        print(f"  Scaler close mean: {scaler_close_mean:.2f}")
        
        # Scaler mean should be close to training mean, NOT test mean
        train_diff = abs(scaler_close_mean - train_close_mean)
        test_diff = abs(scaler_close_mean - test_close_mean)
        
        if train_diff < test_diff:
            print(f"  ✓ Scaler uses TRAINING statistics (diff: {train_diff:.2f} vs {test_diff:.2f})")
        else:
            print(f"  ✗ LEAKAGE DETECTED! Scaler might use test statistics")
            return False
    
    # Verify transform doesn't change scaler statistics
    original_mean = fe.scaler.mean_.copy()
    _ = fe.transform(test_df)
    
    if np.array_equal(original_mean, fe.scaler.mean_):
        print("  ✓ Transform doesn't modify scaler (correct behavior)")
    else:
        print("  ✗ Transform modified scaler (data leakage!)")
        return False
    
    print("\n✓ DATA LEAKAGE PREVENTION TEST PASSED!")
    return True


def test_technical_indicators():
    """Test that technical indicators are calculated correctly."""
    print("\n" + "="*70)
    print(" TEST 2: Technical Indicators")
    print("="*70 + "\n")
    
    data = create_sample_data(n_rows=500)
    fe = FeatureEngineer()
    
    # Just calculate indicators (no normalization)
    df_indicators = fe.calculate_indicators(data)
    
    if df_indicators is None:
        print("✗ Failed to calculate indicators")
        return False
    
    print(f"✓ Calculated indicators for {len(df_indicators)} rows")
    
    # Check expected indicators exist
    expected_indicators = [
        'rsi', 'macd', 'macd_signal', 'bb_high', 'bb_low', 'bb_mid',
        'sma_20', 'sma_50', 'ema_12', 'ema_26', 'stoch_k', 'stoch_d',
        'vwap', 'price_change', 'volume_change'
    ]
    
    missing = [ind for ind in expected_indicators if ind not in df_indicators.columns]
    if missing:
        print(f"✗ Missing indicators: {missing}")
        return False
    
    print(f"✓ All expected indicators present ({len(expected_indicators)} indicators)")
    
    # Verify RSI is in valid range (0-100)
    if df_indicators['rsi'].min() < 0 or df_indicators['rsi'].max() > 100:
        print(f"✗ RSI out of range: {df_indicators['rsi'].min():.2f} - {df_indicators['rsi'].max():.2f}")
        return False
    
    print(f"✓ RSI in valid range: {df_indicators['rsi'].min():.2f} - {df_indicators['rsi'].max():.2f}")
    
    # Verify no NaN values after calculation
    nan_count = df_indicators.isnull().sum().sum()
    if nan_count > 0:
        print(f"✗ Found {nan_count} NaN values")
        return False
    
    print("✓ No NaN values in indicators")
    
    print("\n✓ TECHNICAL INDICATORS TEST PASSED!")
    return True


def test_cyclical_features():
    """Test cyclical time encoding."""
    print("\n" + "="*70)
    print(" TEST 3: Cyclical Time Features")
    print("="*70 + "\n")
    
    # Create data spanning full day and week
    data = create_sample_data(n_rows=7*24)  # 1 week of hourly data
    fe = FeatureEngineer()
    
    df_features = fe.calculate_indicators(data)
    
    if df_features is None:
        print("✗ Failed to calculate features")
        return False
    
    # Check cyclical features exist
    cyclical_features = ['hour_sin', 'hour_cos', 'day_of_week_sin', 'day_of_week_cos']
    missing = [f for f in cyclical_features if f not in df_features.columns]
    if missing:
        print(f"✗ Missing cyclical features: {missing}")
        return False
    
    print(f"✓ All cyclical features present")
    
    # Verify hour encoding (should be in range [-1, 1])
    hour_sin_range = (df_features['hour_sin'].min(), df_features['hour_sin'].max())
    hour_cos_range = (df_features['hour_cos'].min(), df_features['hour_cos'].max())
    
    print(f"✓ hour_sin range: {hour_sin_range[0]:.2f} to {hour_sin_range[1]:.2f}")
    print(f"✓ hour_cos range: {hour_cos_range[0]:.2f} to {hour_cos_range[1]:.2f}")
    
    # Verify they're in valid range
    if not (-1 <= hour_sin_range[0] and hour_sin_range[1] <= 1):
        print("✗ hour_sin out of range [-1, 1]")
        return False
    
    print("✓ Cyclical features in valid range [-1, 1]")
    
    # Verify sin^2 + cos^2 = 1 (property of cyclical encoding)
    hour_identity = df_features['hour_sin']**2 + df_features['hour_cos']**2
    if not np.allclose(hour_identity, 1.0, atol=0.01):
        print(f"✗ Hour cyclical identity failed: {hour_identity.describe()}")
        return False
    
    print("✓ Cyclical identity (sin²+cos²=1) verified")
    
    print("\n✓ CYCLICAL FEATURES TEST PASSED!")
    return True


def test_fit_before_transform():
    """Test that transform fails if called before fit."""
    print("\n" + "="*70)
    print(" TEST 4: Fit Before Transform Validation")
    print("="*70 + "\n")
    
    data = create_sample_data(n_rows=200)
    fe = FeatureEngineer()
    
    # Try to transform without fitting
    try:
        fe.transform(data)
        print("✗ Transform should have raised ValueError!")
        return False
    except ValueError as e:
        print(f"✓ Correctly raised ValueError: {e}")
        return True
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def test_save_load():
    """Test saving and loading fitted feature engineer."""
    print("\n" + "="*70)
    print(" TEST 5: Save/Load Fitted Feature Engineer")
    print("="*70 + "\n")
    
    # Create and fit feature engineer
    data = create_sample_data(n_rows=500)
    fe = FeatureEngineer()
    _ = fe.fit_transform(data)
    
    print(f"✓ Created fitted feature engineer: {fe}")
    print(f"  Features: {len(fe.get_feature_names())}")
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        fe.save(tmp_path)
        print(f"✓ Saved to {tmp_path}")
        
        # Load
        fe_loaded = FeatureEngineer.load(tmp_path)
        print(f"✓ Loaded: {fe_loaded}")
        
        # Verify loaded correctly
        if not fe_loaded.is_fitted:
            print("✗ Loaded feature engineer not fitted")
            return False
        
        if len(fe_loaded.get_feature_names()) != len(fe.get_feature_names()):
            print("✗ Feature count mismatch")
            return False
        
        # Verify can transform with loaded engineer
        test_data = create_sample_data(n_rows=100)
        transformed = fe_loaded.transform(test_data)
        
        if transformed is None:
            print("✗ Loaded feature engineer failed to transform")
            return False
        
        print(f"✓ Loaded feature engineer transforms correctly ({len(transformed)} rows)")
        
        print("\n✓ SAVE/LOAD TEST PASSED!")
        return True
        
    finally:
        # Clean up
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_empty_and_edge_cases():
    """Test edge cases and error handling."""
    print("\n" + "="*70)
    print(" TEST 6: Edge Cases & Error Handling")
    print("="*70 + "\n")
    
    fe = FeatureEngineer()
    
    # Test empty dataframe
    empty_df = pd.DataFrame()
    result = fe.calculate_indicators(empty_df)
    if result is not None:
        print("✗ Should return None for empty dataframe")
        return False
    print("✓ Correctly handles empty dataframe")
    
    # Test insufficient data
    small_df = create_sample_data(n_rows=20)  # Less than minimum required (50)
    result = fe.calculate_indicators(small_df)
    if result is not None:
        print("✗ Should return None for insufficient data")
        return False
    print("✓ Correctly handles insufficient data")
    
    # Test missing columns
    bad_df = pd.DataFrame({
        'close': [100, 101, 102],
        'volume': [1000, 1100, 1200]
    }, index=pd.date_range('2024-01-01', periods=3, freq='1h', tz='UTC'))
    result = fe.calculate_indicators(bad_df)
    if result is not None:
        print("✗ Should return None for missing columns")
        return False
    print("✓ Correctly handles missing columns")
    
    print("\n✓ EDGE CASES TEST PASSED!")
    return True


def run_all_tests():
    """Run all feature engineering tests."""
    print("\n" + "="*70)
    print(" RUNNING FEATURE ENGINEERING TESTS")
    print("="*70)
    
    tests = [
        ("Data Leakage Prevention", test_data_leakage_prevention),
        ("Technical Indicators", test_technical_indicators),
        ("Cyclical Features", test_cyclical_features),
        ("Fit Before Transform", test_fit_before_transform),
        ("Save/Load", test_save_load),
        ("Edge Cases", test_empty_and_edge_cases),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ Test '{test_name}' raised exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*70)
    print(" TEST SUMMARY")
    print("="*70 + "\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nPassed: {passed}/{total} tests")
    
    if passed == total:
        print("\n" + "="*70)
        print(" ✓ ALL TESTS PASSED! NO DATA LEAKAGE DETECTED!")
        print("="*70 + "\n")
        return True
    else:
        print(f"\n✗ {total - passed} TEST(S) FAILED\n")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
