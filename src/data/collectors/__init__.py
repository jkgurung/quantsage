"""
Data collectors for various asset types.

This package provides data collection modules for different asset classes:
- Crypto: CCXT-based cryptocurrency data collection
- Stocks: Alpaca API for stock market data (future)
"""

from .crypto_collector import CryptoCollector

__all__ = ['CryptoCollector']
