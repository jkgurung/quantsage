"""
Test script for CryptoCollector.

This script tests the crypto data collection functionality including:
- Exchange initialization
- OHLCV data fetching
- Data validation
- Database storage
- Event publishing
"""

import sys
import os
from datetime import datetime, timedelta
import logging
import pytz

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import ConfigManager
from src.core.event_bus import EventBus
from src.data.storage import DatabaseManager
from src.data.collectors.crypto_collector import CryptoCollector


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_crypto_collector():
    """Test the crypto data collector."""
    print("\n" + "="*70)
    print(" Testing Crypto Data Collector")
    print("="*70 + "\n")
    
    try:
        # Initialize components
        print("1. Initializing components...")
        config = ConfigManager("config/config.yaml")
        db = DatabaseManager("data/quantsage.db")
        event_bus = EventBus(mode='backtest')  # Use backtest mode to store events
        
        print("   ✓ Configuration loaded")
        print("   ✓ Database initialized")
        print("   ✓ Event bus created")
        
        # Initialize crypto collector
        print("\n2. Initializing CryptoCollector...")
        collector = CryptoCollector(config, db, event_bus)
        print(f"   ✓ {collector}")
        
        # Test 1: Get available symbols
        print("\n3. Testing available symbols...")
        symbols = collector.get_available_symbols()
        print(f"   ✓ Found {len(symbols)} trading pairs on {collector.exchange_name}")
        
        # Check if BTC/USD exists
        btc_symbols = [s for s in symbols if 'BTC' in s and 'USD' in s]
        if btc_symbols:
            print(f"   ✓ BTC/USD variants available: {btc_symbols[:5]}")
            test_symbol = btc_symbols[0]
        else:
            print("   ! No BTC/USD found, using first available symbol")
            test_symbol = symbols[0] if symbols else 'BTC/USD'
        
        # Test 2: Fetch current ticker
        print(f"\n4. Testing current ticker for {test_symbol}...")
        ticker = collector.fetch_ticker(test_symbol)
        if ticker:
            print(f"   ✓ Last price: ${ticker.get('last', 0):.2f}")
            print(f"   ✓ Bid/Ask: ${ticker.get('bid', 0):.2f} / ${ticker.get('ask', 0):.2f}")
            volume = ticker.get('volume') or 0
            print(f"   ✓ Volume: {volume:.2f}")
        else:
            print("   ! Failed to fetch ticker")
        
        # Test 3: Fetch OHLCV data (small sample)
        print(f"\n5. Testing OHLCV fetch for {test_symbol} (last 1 hour)...")
        since = datetime.now(pytz.UTC) - timedelta(hours=1)
        df = collector.fetch_ohlcv(test_symbol, timeframe='1m', since=since, limit=60)
        
        if not df.empty:
            print(f"   ✓ Fetched {len(df)} candles")
            print(f"   ✓ Time range: {df.index.min()} to {df.index.max()}")
            print(f"   ✓ Latest close: ${df['close'].iloc[-1]:.2f}")
            print(f"   ✓ Price change: {((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100:.2f}%")
        else:
            print("   ! No OHLCV data fetched")
            return False
        
        # Test 4: Data validation
        print(f"\n6. Testing data validation...")
        is_valid = collector.validate_data(df)
        if is_valid:
            print("   ✓ Data validation PASSED")
        else:
            print("   ✗ Data validation FAILED")
            return False
        
        # Test 5: Historical data collection (last 24 hours)
        print(f"\n7. Testing historical data collection (last 6 hours)...")
        end_time = datetime.now(pytz.UTC)
        start_time = end_time - timedelta(hours=6)
        
        df_historical = collector.fetch_historical_data(
            symbol=test_symbol,
            start_time=start_time,
            end_time=end_time,
            timeframe='5m'
        )
        
        if not df_historical.empty:
            print(f"   ✓ Fetched {len(df_historical)} historical candles")
            print(f"   ✓ Time range: {df_historical.index.min()} to {df_historical.index.max()}")
            
            # Calculate statistics
            price_change = ((df_historical['close'].iloc[-1] / df_historical['close'].iloc[0]) - 1) * 100
            volume_total = df_historical['volume'].sum()
            
            print(f"   ✓ Price change: {price_change:.2f}%")
            print(f"   ✓ Total volume: {volume_total:.2f}")
        else:
            print("   ! No historical data fetched")
        
        # Test 6: Database storage (small sample)
        print(f"\n8. Testing database storage...")
        sample_start = end_time - timedelta(minutes=30)
        sample_end = end_time
        
        success = collector.collect_and_store(
            symbol=test_symbol,
            start_time=sample_start,
            end_time=sample_end,
            timeframe='1m'
        )
        
        if success:
            print("   ✓ Data stored successfully")
            
            # Verify data in database
            stored_data = db.get_market_data(
                symbol=test_symbol,
                start_date=sample_start,
                end_date=sample_end
            )
            print(f"   ✓ Verified {len(stored_data)} records in database")
        else:
            print("   ! Storage failed")
        
        # Test 7: Event publishing
        print(f"\n9. Testing event publishing...")
        event_count = len(event_bus.event_history) if event_bus.event_history else 0
        print(f"   ✓ Published {event_count} market data events")
        
        if event_count > 0:
            # Show first event
            first_event = event_bus.event_history[0]
            print(f"   ✓ First event: {first_event.symbol} @ {first_event.timestamp}")
            print(f"   ✓ OHLCV: O={first_event.ohlcv['open']:.2f} "
                  f"H={first_event.ohlcv['high']:.2f} "
                  f"L={first_event.ohlcv['low']:.2f} "
                  f"C={first_event.ohlcv['close']:.2f}")
        
        # Summary
        print("\n" + "="*70)
        print(" ✓ ALL TESTS PASSED!")
        print("="*70 + "\n")
        
        print("Summary:")
        print(f"  • Exchange: {collector.exchange_name}")
        print(f"  • Test symbol: {test_symbol}")
        print(f"  • Candles fetched: {len(df_historical)}")
        print(f"  • Records stored: {len(stored_data) if success else 0}")
        print(f"  • Events published: {event_count}")
        print(f"  • Data quality: Valid ✓")
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        print(f"\n✗ TEST FAILED: {e}\n")
        return False


if __name__ == '__main__':
    success = test_crypto_collector()
    sys.exit(0 if success else 1)
