"""
Data validation utilities for market data quality assurance.

This module provides comprehensive validation for OHLCV data including:
- Data completeness checks
- Price consistency validation
- Outlier detection
- Gap detection and handling
- Timestamp validation
- Data type verification
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import timedelta
import pandas as pd
import numpy as np


logger = logging.getLogger(__name__)


class DataValidator:
    """
    Comprehensive data validator for market data.
    
    Performs multiple validation checks on OHLCV dataframes to ensure
    data quality before use in strategies or backtesting.
    """
    
    def __init__(self, strict_mode: bool = True):
        """
        Initialize data validator.
        
        Args:
            strict_mode: If True, fail on any validation error.
                        If False, issue warnings but don't fail.
        """
        self.strict_mode = strict_mode
        self.validation_results = {}
    
    def validate(self, df: pd.DataFrame, symbol: str = "") -> bool:
        """
        Run all validation checks on a dataframe.
        
        Args:
            df: DataFrame with OHLCV data
            symbol: Optional symbol name for logging
        
        Returns:
            True if all validations pass, False otherwise
        """
        if symbol:
            logger.info(f"Running validation for {symbol}")
        else:
            logger.info("Running validation")
        
        self.validation_results = {}
        
        # Run all validation checks
        checks = [
            ('empty_data', self._check_empty_data),
            ('required_columns', self._check_required_columns),
            ('data_types', self._check_data_types),
            ('null_values', self._check_null_values),
            ('negative_values', self._check_negative_values),
            ('price_consistency', self._check_price_consistency),
            ('timestamp_index', self._check_timestamp_index),
            ('timezone_aware', self._check_timezone_aware),
            ('duplicates', self._check_duplicates),
            ('gaps', self._check_gaps),
            ('outliers', self._check_outliers),
        ]
        
        all_passed = True
        for check_name, check_func in checks:
            try:
                passed, message = check_func(df)
                self.validation_results[check_name] = {'passed': passed, 'message': message}
                
                if not passed:
                    if self.strict_mode:
                        logger.error(f"✗ {check_name}: {message}")
                        all_passed = False
                    else:
                        logger.warning(f"⚠ {check_name}: {message}")
                else:
                    logger.debug(f"✓ {check_name}: {message}")
            except Exception as e:
                error_msg = f"Error in {check_name}: {str(e)}"
                self.validation_results[check_name] = {'passed': False, 'message': error_msg}
                logger.error(error_msg)
                if self.strict_mode:
                    all_passed = False
        
        if all_passed:
            logger.info("✓ All validation checks passed")
        else:
            logger.error("✗ Some validation checks failed")
        
        return all_passed
    
    def _check_empty_data(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """Check if dataframe is empty."""
        if df is None or df.empty:
            return False, "DataFrame is empty"
        return True, f"DataFrame has {len(df)} rows"
    
    def _check_required_columns(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """Check for required columns."""
        required = {'symbol', 'open', 'high', 'low', 'close', 'volume'}
        missing = required - set(df.columns)
        
        if missing:
            return False, f"Missing required columns: {missing}"
        return True, "All required columns present"
    
    def _check_data_types(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """Check that numeric columns are numeric."""
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        
        for col in numeric_columns:
            if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
                return False, f"Column {col} is not numeric (type: {df[col].dtype})"
        
        return True, "All numeric columns have correct types"
    
    def _check_null_values(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """Check for null/NaN values."""
        required_columns = {'symbol', 'open', 'high', 'low', 'close', 'volume'}
        available_columns = required_columns & set(df.columns)
        
        null_counts = df[list(available_columns)].isnull().sum()
        
        if null_counts.any():
            null_info = null_counts[null_counts > 0].to_dict()
            return False, f"Found null values: {null_info}"
        
        return True, "No null values found"
    
    def _check_negative_values(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """Check for negative values in price/volume columns."""
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        available_columns = [col for col in numeric_columns if col in df.columns]
        
        negative_values = (df[available_columns] < 0).any()
        
        if negative_values.any():
            negative_cols = negative_values[negative_values].index.tolist()
            return False, f"Found negative values in: {negative_cols}"
        
        return True, "No negative values found"
    
    def _check_price_consistency(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Check price consistency rules:
        - high >= low
        - open between low and high
        - close between low and high
        """
        issues = (
            (df['low'] > df['high']) |
            (df['open'] > df['high']) |
            (df['close'] > df['high']) |
            (df['open'] < df['low']) |
            (df['close'] < df['low'])
        )
        
        if issues.any():
            issue_count = issues.sum()
            # Show sample of problematic rows
            sample = df[issues].head(3)
            return False, f"Found {issue_count} rows with inconsistent prices. Sample:\n{sample[['open', 'high', 'low', 'close']]}"
        
        return True, "All prices are consistent (high >= low, open/close within range)"
    
    def _check_timestamp_index(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """Check if index is a DatetimeIndex."""
        if not isinstance(df.index, pd.DatetimeIndex):
            return False, f"Index is not DatetimeIndex (type: {type(df.index)})"
        return True, "Index is DatetimeIndex"
    
    def _check_timezone_aware(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """Check if datetime index is timezone-aware."""
        if not isinstance(df.index, pd.DatetimeIndex):
            return False, "Index is not DatetimeIndex"
        
        if df.index.tz is None:
            return False, "Index is not timezone-aware"
        
        return True, f"Index is timezone-aware ({df.index.tz})"
    
    def _check_duplicates(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """Check for duplicate timestamps."""
        duplicates = df.index.duplicated()
        
        if duplicates.any():
            dup_count = duplicates.sum()
            dup_times = df.index[duplicates][:5].tolist()
            return False, f"Found {dup_count} duplicate timestamps. First few: {dup_times}"
        
        return True, "No duplicate timestamps"
    
    def _check_gaps(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """Check for gaps in time series."""
        if len(df) < 2:
            return True, "Not enough data to check for gaps"
        
        # Calculate time differences
        time_diff = df.index.to_series().diff()
        median_diff = time_diff.median()
        
        # Find gaps (anything > 1.5x median interval)
        gaps = time_diff[time_diff > median_diff * 1.5]
        
        if not gaps.empty:
            total_gap_time = gaps.sum()
            gap_count = len(gaps)
            
            # Get details of largest gaps
            largest_gaps = gaps.nlargest(3)
            gap_details = []
            for idx, gap in largest_gaps.items():
                gap_start = idx - gap
                gap_details.append(f"{gap_start} -> {idx} ({gap})")
            
            message = (f"Found {gap_count} gaps in data. "
                      f"Total gap time: {total_gap_time}. "
                      f"Largest gaps: {', '.join(gap_details)}")
            
            # In strict mode, only fail if gaps are very large
            if self.strict_mode and gap_count > len(df) * 0.1:  # > 10% of data
                return False, message
            else:
                return True, message  # Warning only
        
        return True, "No significant gaps detected"
    
    def _check_outliers(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """Check for statistical outliers in prices."""
        price_cols = ['open', 'high', 'low', 'close']
        outlier_info = {}
        
        for col in price_cols:
            if col not in df.columns:
                continue
            
            # Use IQR method for outlier detection
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            
            lower_bound = Q1 - 3 * IQR  # 3x IQR for more tolerance
            upper_bound = Q3 + 3 * IQR
            
            outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)]
            
            if not outliers.empty:
                outlier_info[col] = {
                    'count': len(outliers),
                    'pct': len(outliers) / len(df) * 100,
                    'values': outliers[col].tolist()[:3]  # First 3 outliers
                }
        
        if outlier_info:
            outlier_summary = {k: f"{v['count']} ({v['pct']:.1f}%)" 
                             for k, v in outlier_info.items()}
            message = f"Found potential outliers: {outlier_summary}"
            
            # Only fail in strict mode if many outliers
            total_outlier_pct = sum(v['pct'] for v in outlier_info.values()) / len(price_cols)
            if self.strict_mode and total_outlier_pct > 5:  # > 5% outliers
                return False, message
            else:
                return True, message  # Warning only
        
        return True, "No significant outliers detected"
    
    def get_validation_report(self) -> Dict:
        """
        Get detailed validation report.
        
        Returns:
            Dictionary with validation results for each check
        """
        return self.validation_results.copy()
    
    def print_validation_report(self):
        """Print a formatted validation report."""
        print("\n" + "="*70)
        print(" Data Validation Report")
        print("="*70)
        
        for check_name, result in self.validation_results.items():
            status = "✓ PASS" if result['passed'] else "✗ FAIL"
            print(f"\n{check_name.upper()}: {status}")
            print(f"  {result['message']}")
        
        print("\n" + "="*70)
        
        passed_count = sum(1 for r in self.validation_results.values() if r['passed'])
        total_count = len(self.validation_results)
        
        print(f"Total: {passed_count}/{total_count} checks passed")
        print("="*70 + "\n")


def validate_ohlcv(df: pd.DataFrame, symbol: str = "", strict: bool = True) -> bool:
    """
    Convenience function to validate OHLCV data.
    
    Args:
        df: DataFrame with OHLCV data
        symbol: Optional symbol name for logging
        strict: If True, fail on any validation error
    
    Returns:
        True if validation passes, False otherwise
    """
    validator = DataValidator(strict_mode=strict)
    result = validator.validate(df, symbol)
    
    if not result and not strict:
        validator.print_validation_report()
    
    return result


def clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean OHLCV data by fixing common issues.
    
    - Removes duplicate timestamps (keeps first)
    - Sorts by timestamp
    - Fills small gaps with forward fill (max 3 periods)
    - Converts to proper types
    
    Args:
        df: DataFrame with OHLCV data
    
    Returns:
        Cleaned DataFrame
    """
    if df.empty:
        return df
    
    df = df.copy()
    
    # Remove duplicates (keep first)
    df = df[~df.index.duplicated(keep='first')]
    
    # Sort by timestamp
    df = df.sort_index()
    
    # Forward fill small gaps (max 3 periods)
    df = df.fillna(method='ffill', limit=3)
    
    # Convert numeric columns
    numeric_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    logger.info(f"Cleaned data: {len(df)} rows")
    
    return df


def detect_and_handle_gaps(df: pd.DataFrame, max_gap_minutes: int = 60) -> pd.DataFrame:
    """
    Detect and handle gaps in time series.
    
    Large gaps (> max_gap_minutes) are left as-is.
    Small gaps are filled with interpolation.
    
    Args:
        df: DataFrame with OHLCV data
        max_gap_minutes: Maximum gap size to interpolate (minutes)
    
    Returns:
        DataFrame with gaps handled
    """
    if len(df) < 2:
        return df
    
    df = df.copy()
    
    # Detect gaps
    time_diff = df.index.to_series().diff()
    median_diff = time_diff.median()
    
    gaps = time_diff[time_diff > median_diff * 1.5]
    
    if gaps.empty:
        logger.debug("No gaps detected")
        return df
    
    logger.info(f"Found {len(gaps)} gaps in data")
    
    # Handle small gaps with interpolation
    for idx, gap in gaps.items():
        gap_minutes = gap.total_seconds() / 60
        
        if gap_minutes <= max_gap_minutes:
            # Interpolate small gaps
            gap_start = idx - gap
            df_slice = df[gap_start:idx]
            
            # Linear interpolation for prices
            price_cols = ['open', 'high', 'low', 'close']
            for col in price_cols:
                if col in df.columns:
                    df.loc[gap_start:idx, col] = df.loc[gap_start:idx, col].interpolate(method='linear')
            
            # Forward fill for volume
            if 'volume' in df.columns:
                df.loc[gap_start:idx, 'volume'] = df.loc[gap_start:idx, 'volume'].fillna(method='ffill')
            
            logger.debug(f"Interpolated gap from {gap_start} to {idx} ({gap_minutes:.1f} min)")
        else:
            logger.warning(f"Large gap detected ({gap_minutes:.1f} min): {idx - gap} -> {idx}")
    
    return df
