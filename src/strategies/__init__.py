"""
Trading strategies package.

Provides:
- BaseStrategy: Abstract base class for all strategies
- MeanReversionStrategy: Bollinger Bands + Z-score + RSI strategy
"""

from .base import BaseStrategy
from .mean_reversion import MeanReversionStrategy

__all__ = ['BaseStrategy', 'MeanReversionStrategy']
