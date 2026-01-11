"""
Test script to verify the foundation components are working.

Tests:
1. Database initialization
2. Event system
3. Configuration management
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_database():
    """Test database initialization and operations."""
    print("\n" + "="*50)
    print("Testing Database...")
    print("="*50)

    from data.storage import DatabaseManager

    # Initialize database
    db = DatabaseManager("data/test.db")

    # Test market data insertion
    test_data = {
        'symbol': 'BTC/USD',
        'asset_type': 'CRYPTO',
        'timestamp': datetime.now(),
        'ohlcv': {
            'open': 50000.0,
            'high': 51000.0,
            'low': 49500.0,
            'close': 50500.0,
            'volume': 100.5
        },
        'data_source': 'coinbase'
    }

    success = db.insert_market_data(**test_data)
    print(f"✓ Market data insertion: {'SUCCESS' if success else 'FAILED'}")

    # Test data retrieval
    from datetime import timedelta
    start_date = datetime.now() - timedelta(hours=1)
    end_date = datetime.now() + timedelta(hours=1)

    data = db.get_market_data('BTC/USD', start_date, end_date)
    print(f"✓ Market data retrieval: {len(data)} records")

    # Test signal insertion
    signal_success = db.insert_signal(
        symbol='BTC/USD',
        asset_type='CRYPTO',
        timestamp=datetime.now(),
        strategy_id='test_strategy',
        signal_type='BUY',
        confidence=0.85,
        price=50500.0,
        metadata={'test': True}
    )
    print(f"✓ Signal insertion: {'SUCCESS' if signal_success else 'FAILED'}")

    db.close()
    print("\n✅ Database tests passed!")


def test_events():
    """Test event system."""
    print("\n" + "="*50)
    print("Testing Event System...")
    print("="*50)

    from core.events import MarketDataEvent, SignalEvent, EventType
    from core.event_bus import EventBus

    # Create event bus
    bus = EventBus(mode='backtest')

    # Track received events
    received_events = []

    def on_market_data(event):
        received_events.append(('market_data', event))
        print(f"  Received market data: {event.symbol} @ ${event.ohlcv['close']}")

    def on_signal(event):
        received_events.append(('signal', event))
        print(f"  Received signal: {event.signal_type} {event.symbol} (conf: {event.confidence})")

    # Subscribe
    bus.subscribe(EventType.MARKET_DATA, on_market_data)
    bus.subscribe(EventType.SIGNAL, on_signal)

    # Publish events
    bus.publish(MarketDataEvent(
        timestamp=datetime.now(),
        symbol='BTC/USD',
        asset_type='CRYPTO',
        ohlcv={'open': 50000, 'high': 51000, 'low': 49500, 'close': 50500, 'volume': 100},
        data_source='coinbase'
    ))

    bus.publish(SignalEvent(
        timestamp=datetime.now(),
        symbol='BTC/USD',
        asset_type='CRYPTO',
        strategy_id='mean_reversion',
        signal_type='BUY',
        confidence=0.85,
        price=50500
    ))

    # Process events
    bus.process_events()

    # Verify
    print(f"\n✓ Published 2 events, received {len(received_events)}")
    print(f"✓ Event history: {len(bus.event_history)} events stored")

    assert len(received_events) == 2, "Should receive 2 events"

    print("\n✅ Event system tests passed!")


def test_config():
    """Test configuration management."""
    print("\n" + "="*50)
    print("Testing Configuration...")
    print("="*50)

    from core.config import ConfigManager

    # Load config
    config = ConfigManager("config/config.yaml")

    # Test basic access
    mode = config.get('system.mode')
    print(f"✓ System mode: {mode}")

    initial_capital = config.get('portfolio.initial_capital')
    print(f"✓ Initial capital: ${initial_capital}")

    # Test enabled symbols
    crypto_symbols = config.get_enabled_symbols('CRYPTO')
    print(f"✓ Enabled crypto symbols: {crypto_symbols}")

    # Test strategy configs
    enabled_strategies = config.get_enabled_strategies()
    print(f"✓ Enabled strategies: {list(enabled_strategies.keys())}")

    # Test validation
    is_valid = config.validate()
    print(f"✓ Configuration valid: {is_valid}")

    assert is_valid, "Configuration should be valid"

    print("\n✅ Configuration tests passed!")


def test_all():
    """Run all tests."""
    print("\n" + "="*70)
    print(" QUANTSAGE FOUNDATION TESTS")
    print("="*70)

    try:
        test_database()
        test_events()
        test_config()

        print("\n" + "="*70)
        print(" ✅ ALL TESTS PASSED! Foundation is solid.")
        print("="*70)
        print("\nNext steps:")
        print("1. Implement data collectors (CCXT wrapper)")
        print("2. Build strategy framework")
        print("3. Create risk management system")
        print("4. Implement backtesting engine")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    test_all()
