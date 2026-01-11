"""
Cryptocurrency data collector using CCXT library.

This module provides a unified interface for collecting cryptocurrency data
from multiple exchanges (Coinbase, Binance, Kraken, etc.) using the CCXT library.

Features:
- Multi-exchange support via CCXT
- Rate limiting and retry logic
- Data validation
- Event publishing for real-time updates
- Database persistence
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import pytz

try:
    import ccxt
except ImportError:
    print("CCXT not installed. Install with: pip install ccxt")
    ccxt = None

from src.core.config import ConfigManager
from src.core.events import MarketDataEvent, EventType
from src.core.event_bus import EventBus
from src.data.storage import DatabaseManager


logger = logging.getLogger(__name__)


class CryptoCollector:
    """
    Cryptocurrency data collector using CCXT.
    
    Supports multiple exchanges and provides unified interface for:
    - Historical OHLCV data collection
    - Real-time price updates
    - Data validation
    - Event publishing
    - Database persistence
    """
    
    def __init__(self, config: ConfigManager, db: DatabaseManager, 
                 event_bus: Optional[EventBus] = None):
        """
        Initialize crypto data collector.
        
        Args:
            config: Configuration manager
            db: Database manager
            event_bus: Optional event bus for publishing market data events
        """
        if ccxt is None:
            raise ImportError("CCXT library not installed. Run: pip install ccxt")
        
        self.config = config
        self.db = db
        self.event_bus = event_bus
        
        # Get crypto data source configuration
        self.exchange_name = config.get('data.data_sources.crypto.default', 'coinbase')
        self.rate_limit = config.get('data.data_sources.crypto.rate_limit', 10)
        
        # Initialize exchange
        self.exchange = self._init_exchange()
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0 / self.rate_limit  # seconds between requests
        
        logger.info(f"CryptoCollector initialized with exchange: {self.exchange_name}")
    
    def _init_exchange(self) -> ccxt.Exchange:
        """
        Initialize CCXT exchange.
        
        Returns:
            Initialized CCXT exchange instance
        """
        try:
            # Get exchange class
            exchange_class = getattr(ccxt, self.exchange_name)
            
            # Initialize with configuration
            exchange_config = {
                'enableRateLimit': True,
                'rateLimit': int(1000 / self.rate_limit),  # milliseconds
            }
            
            # Add API credentials if available (for private endpoints)
            api_key = self.config.get('data.data_sources.crypto.api_key')
            api_secret = self.config.get('data.data_sources.crypto.api_secret')
            
            if api_key and api_key != 'placeholder_api_key':
                exchange_config['apiKey'] = api_key
                exchange_config['secret'] = api_secret
            
            exchange = exchange_class(exchange_config)
            
            # Load markets
            exchange.load_markets()
            
            logger.info(f"Exchange {self.exchange_name} initialized successfully")
            logger.info(f"Available markets: {len(exchange.markets)}")
            
            return exchange
            
        except Exception as e:
            logger.error(f"Failed to initialize exchange {self.exchange_name}: {e}")
            raise
    
    def _rate_limit_wait(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def fetch_ohlcv(self, symbol: str, timeframe: str = '1m', 
                     since: Optional[datetime] = None,
                     limit: Optional[int] = None) -> pd.DataFrame:
        """
        Fetch OHLCV (candlestick) data for a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USD', 'ETH/USD')
            timeframe: Candle timeframe ('1m', '5m', '15m', '1h', '1d', etc.)
            since: Start time for historical data
            limit: Maximum number of candles to fetch
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        try:
            # Validate symbol exists
            if symbol not in self.exchange.markets:
                logger.error(f"Symbol {symbol} not found on {self.exchange_name}")
                return pd.DataFrame()
            
            # Convert datetime to milliseconds timestamp if provided
            since_ms = None
            if since:
                if since.tzinfo is None:
                    since = pytz.UTC.localize(since)
                since_ms = int(since.timestamp() * 1000)
            
            # Rate limiting
            self._rate_limit_wait()
            
            # Fetch OHLCV data
            logger.debug(f"Fetching {timeframe} OHLCV for {symbol}")
            ohlcv = self.exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=since_ms,
                limit=limit
            )
            
            if not ohlcv:
                logger.warning(f"No data returned for {symbol}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            
            # Convert timestamp from milliseconds to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            
            # Add symbol column
            df['symbol'] = symbol
            
            # Set timestamp as index
            df.set_index('timestamp', inplace=True)
            
            logger.info(f"Fetched {len(df)} candles for {symbol} ({timeframe})")
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {e}")
            return pd.DataFrame()
    
    def fetch_historical_data(self, symbol: str, start_time: datetime,
                              end_time: datetime, timeframe: str = '1m',
                              max_retries: int = 3) -> pd.DataFrame:
        """
        Fetch historical data for a date range.
        
        Handles pagination for large date ranges and implements retry logic.
        
        Args:
            symbol: Trading pair symbol
            start_time: Start datetime
            end_time: End datetime
            timeframe: Candle timeframe
            max_retries: Maximum retry attempts on failure
        
        Returns:
            DataFrame with all historical data in the range
        """
        try:
            # Ensure timezone awareness
            if start_time.tzinfo is None:
                start_time = pytz.UTC.localize(start_time)
            if end_time.tzinfo is None:
                end_time = pytz.UTC.localize(end_time)
            
            logger.info(f"Fetching historical data for {symbol}")
            logger.info(f"Time range: {start_time} to {end_time}")
            logger.info(f"Timeframe: {timeframe}")
            
            all_data = []
            current_start = start_time
            
            # Determine chunk size based on timeframe
            timeframe_minutes = self._timeframe_to_minutes(timeframe)
            chunk_size = timedelta(hours=24)  # Fetch 24 hours at a time
            
            retry_count = 0
            
            while current_start < end_time:
                current_end = min(current_start + chunk_size, end_time)
                
                try:
                    # Fetch chunk
                    df_chunk = self.fetch_ohlcv(
                        symbol=symbol,
                        timeframe=timeframe,
                        since=current_start,
                        limit=1000  # CCXT default limit
                    )
                    
                    if not df_chunk.empty:
                        # Filter to requested time range
                        df_chunk = df_chunk[
                            (df_chunk.index >= current_start) & 
                            (df_chunk.index < current_end)
                        ]
                        all_data.append(df_chunk)
                        retry_count = 0  # Reset on success
                        
                        # Move to next chunk
                        if not df_chunk.empty:
                            current_start = df_chunk.index[-1] + timedelta(minutes=timeframe_minutes)
                        else:
                            current_start = current_end
                    else:
                        # No data in this chunk, move forward
                        current_start = current_end
                    
                    # Small delay between chunks
                    time.sleep(0.1)
                    
                except Exception as chunk_error:
                    logger.warning(f"Error fetching chunk: {chunk_error}")
                    retry_count += 1
                    
                    if retry_count >= max_retries:
                        logger.error(f"Max retries ({max_retries}) reached. Moving to next chunk.")
                        current_start = current_end
                        retry_count = 0
                    else:
                        time.sleep(2 ** retry_count)  # Exponential backoff
                        continue
            
            # Combine all chunks
            if all_data:
                df = pd.concat(all_data)
                df = df.sort_index()
                df = df[~df.index.duplicated(keep='first')]  # Remove duplicates
                
                logger.info(f"Successfully fetched {len(df)} candles for {symbol}")
                return df
            else:
                logger.warning(f"No data collected for {symbol}")
                return pd.DataFrame()
        
        except Exception as e:
            logger.error(f"Error in fetch_historical_data: {e}")
            return pd.DataFrame()
    
    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch current ticker (price) for a symbol.
        
        Args:
            symbol: Trading pair symbol
        
        Returns:
            Dict with ticker data (bid, ask, last, volume, etc.)
        """
        try:
            self._rate_limit_wait()
            ticker = self.exchange.fetch_ticker(symbol)
            
            logger.debug(f"Ticker for {symbol}: last={ticker.get('last')}")
            
            return {
                'symbol': symbol,
                'timestamp': datetime.fromtimestamp(ticker['timestamp'] / 1000, tz=pytz.UTC),
                'bid': ticker.get('bid'),
                'ask': ticker.get('ask'),
                'last': ticker.get('last'),
                'volume': ticker.get('baseVolume'),
                'quote_volume': ticker.get('quoteVolume'),
            }
            
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {e}")
            return {}
    
    def collect_and_store(self, symbol: str, start_time: datetime,
                          end_time: datetime, timeframe: str = '1m') -> bool:
        """
        Collect historical data and store in database.
        
        Also publishes MarketDataEvents if event bus is configured.
        
        Args:
            symbol: Trading pair symbol
            start_time: Start datetime
            end_time: End datetime
            timeframe: Candle timeframe
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Fetch data
            df = self.fetch_historical_data(symbol, start_time, end_time, timeframe)
            
            if df.empty:
                logger.error(f"No data to store for {symbol}")
                return False
            
            # Validate data
            if not self.validate_data(df):
                logger.error(f"Data validation failed for {symbol}")
                return False
            
            # Store in database
            stored_count = 0
            for timestamp, row in df.iterrows():
                ohlcv = {
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume']),
                }
                
                success = self.db.insert_market_data(
                    symbol=symbol,
                    asset_type='CRYPTO',
                    timestamp=timestamp,
                    ohlcv=ohlcv,
                    data_source=self.exchange_name
                )
                
                if success:
                    stored_count += 1
                    
                    # Publish event if event bus is available
                    if self.event_bus:
                        event = MarketDataEvent(
                            timestamp=timestamp,
                            symbol=symbol,
                            asset_type='CRYPTO',
                            ohlcv=ohlcv,
                            data_source=self.exchange_name
                        )
                        self.event_bus.publish(event)
            
            logger.info(f"Stored {stored_count}/{len(df)} candles for {symbol}")
            return stored_count > 0
            
        except Exception as e:
            logger.error(f"Error in collect_and_store: {e}")
            return False
    
    def validate_data(self, df: pd.DataFrame) -> bool:
        """
        Validate OHLCV data quality.
        
        Args:
            df: DataFrame with OHLCV data
        
        Returns:
            True if data is valid, False otherwise
        """
        try:
            if df is None or df.empty:
                logger.error("Empty DataFrame provided for validation")
                return False
            
            # Check for required columns
            required_columns = {'symbol', 'open', 'high', 'low', 'close', 'volume'}
            missing_columns = required_columns - set(df.columns)
            if missing_columns:
                logger.error(f"Missing required columns: {missing_columns}")
                return False
            
            # Check for null values
            null_counts = df[list(required_columns)].isnull().sum()
            if null_counts.any():
                logger.error(f"Found null values: {null_counts[null_counts > 0]}")
                return False
            
            # Check data types
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_columns:
                if not pd.api.types.is_numeric_dtype(df[col]):
                    logger.error(f"Column {col} is not numeric")
                    return False
            
            # Verify price consistency (high >= low, open/close between high/low)
            price_issues = (
                (df['low'] > df['high']) |
                (df['open'] > df['high']) |
                (df['close'] > df['high']) |
                (df['open'] < df['low']) |
                (df['close'] < df['low'])
            )
            if price_issues.any():
                issue_count = price_issues.sum()
                logger.error(f"Found {issue_count} rows with inconsistent price data")
                # Log first few problematic rows
                problematic = df[price_issues].head()
                logger.error(f"Sample problematic rows:\n{problematic}")
                return False
            
            # Check for negative values
            negative_values = (df[numeric_columns] < 0).any()
            if negative_values.any():
                logger.error(f"Found negative values in: {negative_values[negative_values].index.tolist()}")
                return False
            
            # Check time index
            if not isinstance(df.index, pd.DatetimeIndex):
                logger.error("Index is not DatetimeIndex")
                return False
            
            # Check for timezone awareness
            if df.index.tz is None:
                logger.error("Index is not timezone-aware")
                return False
            
            # Check for outliers (warn only, don't fail)
            for col in ['open', 'high', 'low', 'close']:
                mean = df[col].mean()
                std = df[col].std()
                outliers = df[col].apply(lambda x: abs(x - mean) > 5 * std)
                if outliers.any():
                    logger.warning(f"Found {outliers.sum()} potential outliers in {col}")
            
            # Check for gaps in time series (warn only)
            if len(df) > 1:
                time_diff = df.index.to_series().diff()
                median_diff = time_diff.median()
                gaps = time_diff[time_diff > median_diff * 1.5]
                
                if not gaps.empty:
                    total_gap_minutes = gaps.sum().total_seconds() / 60
                    logger.warning(f"Found {len(gaps)} gaps in data, total: {total_gap_minutes:.1f} minutes")
            
            logger.info("Data validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Error during data validation: {e}")
            return False
    
    def _timeframe_to_minutes(self, timeframe: str) -> int:
        """Convert CCXT timeframe string to minutes."""
        timeframe_map = {
            '1m': 1,
            '5m': 5,
            '15m': 15,
            '30m': 30,
            '1h': 60,
            '2h': 120,
            '4h': 240,
            '6h': 360,
            '12h': 720,
            '1d': 1440,
            '1w': 10080,
        }
        return timeframe_map.get(timeframe, 1)
    
    def get_available_symbols(self) -> List[str]:
        """Get list of available trading symbols on the exchange."""
        try:
            return list(self.exchange.markets.keys())
        except Exception as e:
            logger.error(f"Error getting available symbols: {e}")
            return []
    
    def __repr__(self) -> str:
        return f"CryptoCollector(exchange={self.exchange_name}, markets={len(self.exchange.markets)})"
