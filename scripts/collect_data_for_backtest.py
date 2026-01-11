"""
Collect historical data for backtesting.

This script fetches recent historical data for crypto pairs
to use in backtesting demonstrations.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.collectors import CryptoCollector
from src.data.storage import DatabaseManager
from src.core.event_bus import EventBus
from src.core.config import ConfigManager

def main():
    print("=" * 60)
    print("Collecting Historical Data for Backtesting")
    print("=" * 60)
    print()

    # Initialize components
    config = ConfigManager()
    event_bus = EventBus()
    db = DatabaseManager()

    # Initialize collector
    print("Initializing CCXT collector...")
    collector = CryptoCollector(
        config=config,
        db=db,
        event_bus=event_bus
    )
    print(f"✓ Connected to {collector.exchange.name}")
    print()

    # Symbols to collect
    symbols = ['BTC/USDT', 'ETH/USDT']

    # Collect last 30 days of 1-hour data (more manageable)
    end_time = datetime.now()
    start_time = end_time - timedelta(days=30)
    timeframe = '1h'

    print(f"Collecting {timeframe} data from {start_time.date()} to {end_time.date()}...")
    print()

    for symbol in symbols:
        print(f"Fetching {symbol}...")
        try:
            # Fetch historical data
            df = collector.fetch_historical_data(
                symbol=symbol,
                start_time=start_time,
                end_time=end_time,
                timeframe=timeframe
            )

            if df is not None and not df.empty:
                print(f"  ✓ Collected {len(df)} bars")

                # Store in database
                stored = 0
                for _, row in df.iterrows():
                    success = db.insert_market_data(
                        symbol=symbol,
                        asset_type='CRYPTO',
                        timestamp=row.name,  # Index is timestamp
                        ohlcv={
                            'open': float(row['open']),
                            'high': float(row['high']),
                            'low': float(row['low']),
                            'close': float(row['close']),
                            'volume': float(row['volume'])
                        },
                        data_source='coinbase'
                    )
                    if success:
                        stored += 1

                print(f"  ✓ Stored {stored} bars in database")
            else:
                print(f"  ✗ No data received")

        except Exception as e:
            print(f"  ✗ Error: {e}")

        print()

    print("=" * 60)
    print("Data collection complete!")
    print("=" * 60)
    print()
    print("You can now run: python scripts/run_backtest.py")
    print()

if __name__ == '__main__':
    main()
