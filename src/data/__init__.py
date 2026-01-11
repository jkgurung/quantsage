"""
Data collection and management modules.

This package provides data collection, storage, and validation
functionality for the QuantSage trading system.
"""

from .storage import DatabaseManager
from .validators import DataValidator, validate_ohlcv, clean_ohlcv, detect_and_handle_gaps
from .collectors import CryptoCollector
from .features import FeatureEngineer

__all__ = [
    'DatabaseManager',
    'DataValidator',
    'validate_ohlcv',
    'clean_ohlcv',
    'detect_and_handle_gaps',
    'CryptoCollector',
    'FeatureEngineer',
]
