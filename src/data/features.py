"""
Feature engineering module with proper data leakage prevention.

This module provides technical indicator calculation and feature normalization
using a stateful fit/transform pattern to prevent data leakage in ML models.

Key features:
- Technical indicators (RSI, MACD, Bollinger Bands, etc.)
- Cyclical time features
- Stateful normalization (fit on train, transform on test)
- Save/load fitted scalers for production use
"""

import logging
import pickle
from pathlib import Path
from typing import Optional, List
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler

# Technical Analysis
from ta.trend import SMAIndicator, EMAIndicator, MACD
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands
from ta.volume import VolumeWeightedAveragePrice


logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Feature engineer with proper data leakage prevention.
    
    Uses scikit-learn's fit/transform pattern to ensure normalization
    statistics are learned from training data only and applied to test data.
    
    Usage:
        # Training
        fe = FeatureEngineer()
        train_features = fe.fit_transform(train_df)
        
        # Testing (uses training statistics)
        test_features = fe.transform(test_df)
        
        # Save for production
        fe.save('models/feature_engineer.pkl')
        
        # Load in production
        fe_prod = FeatureEngineer.load('models/feature_engineer.pkl')
        live_features = fe_prod.transform(live_df)
    """
    
    def __init__(self):
        """Initialize feature engineer with empty scaler."""
        self.scaler = StandardScaler()
        self.is_fitted = False
        self.feature_columns = None
        logger.info("FeatureEngineer initialized")
    
    def calculate_indicators(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        Calculate technical indicators for OHLCV data.
        
        Args:
            df: DataFrame with OHLCV columns (open, high, low, close, volume)
        
        Returns:
            DataFrame with technical indicators added, or None if error
        """
        if df is None or df.empty:
            logger.error("Empty or None dataframe provided")
            return None
        
        try:
            logger.debug(f"Calculating indicators for {len(df)} rows")
            
            # Create copy to avoid modifying original
            df_copy = df.copy()
            
            # Ensure timestamp index
            if not isinstance(df_copy.index, pd.DatetimeIndex):
                if 'timestamp' in df_copy.columns:
                    df_copy['timestamp'] = pd.to_datetime(df_copy['timestamp'], utc=True)
                    df_copy.set_index('timestamp', inplace=True)
                else:
                    logger.error("DataFrame must have timestamp column or DatetimeIndex")
                    return None
            
            # Ensure timezone-aware
            if df_copy.index.tz is None:
                df_copy.index = df_copy.index.tz_localize('UTC')
            else:
                df_copy.index = df_copy.index.tz_convert('UTC')
            
            # Sort by time
            df_copy.sort_index(inplace=True)
            
            # Validate required columns
            required_columns = {'open', 'high', 'low', 'close', 'volume'}
            missing_columns = required_columns - set(df_copy.columns)
            if missing_columns:
                logger.error(f"Missing required columns: {missing_columns}")
                return None
            
            # Convert to numeric
            for col in required_columns:
                df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce')
            
            # Check minimum data points
            min_required_points = 50
            if len(df_copy) < min_required_points:
                logger.warning(f"Insufficient data ({len(df_copy)} < {min_required_points})")
                return None
            
            # Calculate time-based cyclical features
            df_copy['hour'] = df_copy.index.hour
            df_copy['day_of_week'] = df_copy.index.dayofweek
            
            # Convert to cyclical (prevents discontinuity at 23h->0h and Sun->Mon)
            df_copy['hour_sin'] = np.sin(2 * np.pi * df_copy['hour'] / 24.0)
            df_copy['hour_cos'] = np.cos(2 * np.pi * df_copy['hour'] / 24.0)
            df_copy['day_of_week_sin'] = np.sin(2 * np.pi * df_copy['day_of_week'] / 7.0)
            df_copy['day_of_week_cos'] = np.cos(2 * np.pi * df_copy['day_of_week'] / 7.0)
            
            df_copy = df_copy.drop(['hour', 'day_of_week'], axis=1)
            
            # Adjust indicator windows based on data length
            data_length = len(df_copy)
            rsi_window = min(14, data_length // 4)
            sma_short_window = min(20, data_length // 3)
            sma_long_window = min(50, data_length // 2)
            ema_short_window = min(12, data_length // 4)
            ema_long_window = min(26, data_length // 3)
            
            # RSI - Relative Strength Index
            rsi = RSIIndicator(close=df_copy['close'], window=rsi_window)
            df_copy['rsi'] = rsi.rsi()
            
            # MACD - Moving Average Convergence Divergence
            macd = MACD(
                close=df_copy['close'],
                window_slow=ema_long_window,
                window_fast=ema_short_window,
                window_sign=min(9, data_length // 5)
            )
            df_copy['macd'] = macd.macd()
            df_copy['macd_signal'] = macd.macd_signal()
            df_copy['macd_diff'] = macd.macd_diff()
            
            # Bollinger Bands
            bb = BollingerBands(close=df_copy['close'], window=sma_short_window, window_dev=2)
            df_copy['bb_high'] = bb.bollinger_hband()
            df_copy['bb_mid'] = bb.bollinger_mavg()
            df_copy['bb_low'] = bb.bollinger_lband()
            df_copy['bb_width'] = (df_copy['bb_high'] - df_copy['bb_low']) / df_copy['bb_mid']
            
            # Moving Averages
            df_copy['sma_20'] = SMAIndicator(close=df_copy['close'], window=sma_short_window).sma_indicator()
            df_copy['sma_50'] = SMAIndicator(close=df_copy['close'], window=sma_long_window).sma_indicator()
            df_copy['ema_12'] = EMAIndicator(close=df_copy['close'], window=ema_short_window).ema_indicator()
            df_copy['ema_26'] = EMAIndicator(close=df_copy['close'], window=ema_long_window).ema_indicator()
            
            # Stochastic Oscillator
            stoch = StochasticOscillator(
                high=df_copy['high'],
                low=df_copy['low'],
                close=df_copy['close'],
                window=min(14, data_length // 4),
                smooth_window=3
            )
            df_copy['stoch_k'] = stoch.stoch()
            df_copy['stoch_d'] = stoch.stoch_signal()
            
            # VWAP - Volume Weighted Average Price
            vwap = VolumeWeightedAveragePrice(
                high=df_copy['high'],
                low=df_copy['low'],
                close=df_copy['close'],
                volume=df_copy['volume'],
                window=min(14, data_length // 4)
            )
            df_copy['vwap'] = vwap.volume_weighted_average_price()
            
            # Price change features
            max_period = min(24, data_length // 2)
            df_copy['price_change'] = df_copy['close'].pct_change()
            df_copy['price_change_1h'] = df_copy['close'].pct_change(periods=1)
            df_copy['price_change_4h'] = df_copy['close'].pct_change(periods=min(4, max_period // 4))
            df_copy['price_change_24h'] = df_copy['close'].pct_change(periods=max_period)
            
            # Volume change features
            df_copy['volume_change'] = df_copy['volume'].pct_change()
            df_copy['volume_change_1h'] = df_copy['volume'].pct_change(periods=1)
            df_copy['volume_change_4h'] = df_copy['volume'].pct_change(periods=min(4, max_period // 4))
            df_copy['volume_change_24h'] = df_copy['volume'].pct_change(periods=max_period)
            
            # Handle NaN values (from indicator calculation on early rows)
            df_copy = df_copy.fillna(method='ffill').fillna(method='bfill')
            
            # Drop any remaining NaN rows
            initial_len = len(df_copy)
            df_copy = df_copy.dropna()
            if len(df_copy) < initial_len:
                logger.warning(f"Dropped {initial_len - len(df_copy)} rows with NaN values")
            
            logger.info(f"Calculated {len(df_copy.columns)} features for {len(df_copy)} rows")
            return df_copy
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}", exc_info=True)
            return None
    
    def fit_transform(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        Fit scaler on training data and transform.
        
        This should be called ONLY on training data. It learns normalization
        statistics (mean, std) from the provided data and stores them.
        
        Args:
            df: Training DataFrame with OHLCV data
        
        Returns:
            Transformed DataFrame with normalized features
        """
        try:
            logger.info("Fitting feature engineer on training data")
            
            # Calculate technical indicators
            df_features = self.calculate_indicators(df)
            if df_features is None:
                logger.error("Failed to calculate indicators")
                return None
            
            # Define columns to normalize (exclude symbol and timestamp-related)
            exclude_cols = {'symbol'}
            self.feature_columns = [
                col for col in df_features.columns 
                if col not in exclude_cols and pd.api.types.is_numeric_dtype(df_features[col])
            ]
            
            logger.debug(f"Normalizing {len(self.feature_columns)} features")
            
            # Fit scaler on THIS data only (learns mean and std)
            self.scaler.fit(df_features[self.feature_columns])
            self.is_fitted = True
            
            # Transform using learned parameters
            df_features[self.feature_columns] = self.scaler.transform(
                df_features[self.feature_columns]
            )
            
            logger.info(f"Fit and transformed {len(df_features)} samples")
            logger.debug(f"Scaler mean: {self.scaler.mean_[:5]}...")  # Show first 5
            logger.debug(f"Scaler std: {self.scaler.scale_[:5]}...")
            
            return df_features
            
        except Exception as e:
            logger.error(f"Error in fit_transform: {e}", exc_info=True)
            return None
    
    def transform(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        Transform new data using previously fitted scaler.
        
        This should be called on test/validation/live data. It uses the
        normalization statistics learned during fit_transform() - NO PEEKING
        at this data's statistics!
        
        Args:
            df: New DataFrame with OHLCV data
        
        Returns:
            Transformed DataFrame with normalized features
        
        Raises:
            ValueError: If transform called before fit_transform
        """
        if not self.is_fitted:
            raise ValueError("Must call fit_transform() on training data first!")
        
        try:
            logger.info("Transforming data using fitted scaler")
            
            # Calculate technical indicators
            df_features = self.calculate_indicators(df)
            if df_features is None:
                logger.error("Failed to calculate indicators")
                return None
            
            # Transform using PREVIOUSLY LEARNED parameters (no data leakage!)
            df_features[self.feature_columns] = self.scaler.transform(
                df_features[self.feature_columns]
            )
            
            logger.info(f"Transformed {len(df_features)} samples using fitted scaler")
            
            return df_features
            
        except Exception as e:
            logger.error(f"Error in transform: {e}", exc_info=True)
            return None
    
    def save(self, filepath: str):
        """
        Save fitted feature engineer to file.
        
        Args:
            filepath: Path to save the fitted feature engineer
        """
        if not self.is_fitted:
            logger.warning("Saving unfitted feature engineer")
        
        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'wb') as f:
                pickle.dump({
                    'scaler': self.scaler,
                    'is_fitted': self.is_fitted,
                    'feature_columns': self.feature_columns
                }, f)
            
            logger.info(f"Saved feature engineer to {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving feature engineer: {e}")
            raise
    
    @classmethod
    def load(cls, filepath: str) -> 'FeatureEngineer':
        """
        Load fitted feature engineer from file.
        
        Args:
            filepath: Path to saved feature engineer
        
        Returns:
            Loaded FeatureEngineer instance
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            
            fe = cls()
            fe.scaler = data['scaler']
            fe.is_fitted = data['is_fitted']
            fe.feature_columns = data['feature_columns']
            
            logger.info(f"Loaded feature engineer from {filepath}")
            logger.info(f"Fitted: {fe.is_fitted}, Features: {len(fe.feature_columns)}")
            
            return fe
            
        except Exception as e:
            logger.error(f"Error loading feature engineer: {e}")
            raise
    
    def get_feature_names(self) -> List[str]:
        """Get list of feature column names."""
        if self.feature_columns is None:
            return []
        return list(self.feature_columns)
    
    def __repr__(self) -> str:
        status = "fitted" if self.is_fitted else "unfitted"
        n_features = len(self.feature_columns) if self.feature_columns else 0
        return f"FeatureEngineer({status}, {n_features} features)"
