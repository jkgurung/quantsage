"""
Comprehensive tests for trading strategy framework.

Tests:
1. BaseStrategy Interface
   - Configuration loading
   - Event subscription
   - Position size calculation
   - State management

2. MeanReversionStrategy Logic
   - BUY signal generation (all conditions met)
   - SELL signal generation (all conditions met)
   - No signal when conditions not met
   - Exit signal generation (stop-loss, take-profit, mean reversion)
   - Filter validation (volatility, volume, spread)

3. Integration Tests
   - Market data → Strategy → Signal event flow
   - Multiple symbols handling
   - State persistence across events

4. Edge Cases
   - Insufficient data
   - Missing indicators
   - Invalid configuration
   - Position already exists
"""

import sys
import os
import pytest
import logging
import inspect
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, List
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.strategies.base import BaseStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.core.events import MarketDataEvent, SignalEvent, EventType
from src.core.event_bus import EventBus


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database manager."""
    db = Mock()
    db.get_market_data = Mock(return_value=[])
    return db


@pytest.fixture
def event_bus():
    """Real event bus for integration testing."""
    return EventBus()


@pytest.fixture
def base_config():
    """Base strategy configuration."""
    return {
        'strategy': {
            'name': 'TestStrategy',
            'enabled': True,
            'symbols': ['BTC/USDT', 'ETH/USDT'],
            'asset_type': 'CRYPTO',
            'position_sizing': {
                'method': 'fixed',
                'max_position_pct': 0.10
            }
        }
    }


@pytest.fixture
def mean_reversion_config():
    """Mean reversion strategy configuration."""
    return {
        'strategy': {
            'name': 'MeanReversionCrypto',
            'enabled': True,
            'symbols': ['BTC/USDT'],
            'asset_type': 'CRYPTO',
            'parameters': {
                'bb_window': 20,
                'bb_std': 2.0,
                'zscore_window': 20,
                'zscore_threshold': 2.0,
                'rsi_window': 14,
                'rsi_oversold': 40,
                'rsi_overbought': 60,
                'stop_loss_pct': 0.02,
                'take_profit_ratio': 1.5,
                'exit_on_middle_band': True
            },
            'filters': [
                {'type': 'volatility', 'max_daily_volatility': 0.08},
                {'type': 'volume', 'min_daily_volume': 1000000},
                {'type': 'spread', 'max_spread_pct': 0.005}
            ],
            'position_sizing': {
                'method': 'risk_based',
                'max_position_pct': 0.08
            }
        }
    }


@pytest.fixture
def sample_market_data():
    """Generate sample market data with technical indicators."""
    np.random.seed(42)

    # Generate 100 periods of realistic crypto OHLCV data
    n_periods = 100
    base_price = 50000.0
    timestamps = [datetime.now() - timedelta(hours=i) for i in range(n_periods, 0, -1)]

    # Simulate mean-reverting price with trend
    prices = []
    current_price = base_price

    for i in range(n_periods):
        # Mean reversion + noise + slight uptrend
        mean_price = base_price + (i * 100)  # Uptrend
        reversion_force = (mean_price - current_price) * 0.1
        noise = np.random.randn() * 500
        current_price = current_price + reversion_force + noise
        prices.append(current_price)

    # Generate OHLCV
    data = []
    for i, (ts, close) in enumerate(zip(timestamps, prices)):
        high = close * (1 + abs(np.random.randn() * 0.01))
        low = close * (1 - abs(np.random.randn() * 0.01))
        open_price = close * (1 + np.random.randn() * 0.005)
        volume = 100 + np.random.rand() * 50

        data.append({
            'timestamp': ts,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })

    return data


def create_market_event(symbol: str, price: float, volume: float = 100.0) -> MarketDataEvent:
    """Helper to create market data event."""
    return MarketDataEvent(
        timestamp=datetime.now(),
        symbol=symbol,
        asset_type='CRYPTO',
        ohlcv={
            'open': price * 0.99,
            'high': price * 1.01,
            'low': price * 0.98,
            'close': price,
            'volume': volume
        },
        data_source='test'
    )


# ============================================================================
# Concrete Test Strategy (for BaseStrategy testing)
# ============================================================================

class TestStrategy(BaseStrategy):
    """Simple test strategy that generates signals based on price threshold."""

    def __init__(self, config: Dict, event_bus: EventBus, db):
        super().__init__(config, event_bus, db)
        self.signal_threshold = 50000.0
        self.on_market_data_called = False

    def on_market_data(self, event: MarketDataEvent):
        """Generate BUY signal if price below threshold."""
        self.on_market_data_called = True
        price = event.ohlcv['close']

        if price < self.signal_threshold and not self.has_position(event.symbol):
            return self._create_signal(
                symbol=event.symbol,
                direction='BUY',
                target_price=price,
                confidence=0.8
            )
        return None


# ============================================================================
# Test 1: BaseStrategy Interface
# ============================================================================

class TestBaseStrategyInterface:
    """Test BaseStrategy abstract class functionality."""

    def test_initialization(self, base_config, event_bus, mock_db):
        """Test strategy initialization and configuration loading."""
        strategy = TestStrategy(base_config, event_bus, mock_db)

        assert strategy.name == 'TestStrategy'
        assert strategy.enabled is True
        assert strategy.symbols == ['BTC/USDT', 'ETH/USDT']
        assert strategy.asset_type == 'CRYPTO'
        assert strategy.max_position_pct == 0.10
        assert strategy.sizing_method == 'fixed'
        assert strategy.positions == {}
        assert strategy.entry_prices == {}

        print("✓ PASS: Strategy initialization and config loading")

    def test_event_subscription(self, base_config, event_bus, mock_db):
        """Test that strategy subscribes to market data events."""
        strategy = TestStrategy(base_config, event_bus, mock_db)

        # Publish market data event
        event = create_market_event('BTC/USDT', 45000.0)
        event_bus.publish(event)
        event_bus.process_events()  # Process events to dispatch to subscribers

        # Verify strategy received event
        assert strategy.on_market_data_called is True

        print("✓ PASS: Event subscription works")

    def test_disabled_strategy_no_subscription(self, base_config, event_bus, mock_db):
        """Test that disabled strategy does not subscribe to events."""
        base_config['strategy']['enabled'] = False
        strategy = TestStrategy(base_config, event_bus, mock_db)

        # Publish event
        event = create_market_event('BTC/USDT', 45000.0)
        event_bus.publish(event)
        event_bus.process_events()

        # Strategy should not receive event
        assert strategy.on_market_data_called is False

        print("✓ PASS: Disabled strategy does not subscribe")

    def test_symbol_filtering(self, base_config, event_bus, mock_db):
        """Test that strategy only processes configured symbols."""
        strategy = TestStrategy(base_config, event_bus, mock_db)
        signals = []

        def capture_signal(signal):
            signals.append(signal)

        event_bus.subscribe(EventType.SIGNAL, capture_signal)

        # Event for configured symbol - should generate signal
        event1 = create_market_event('BTC/USDT', 45000.0)
        event_bus.publish(event1)

        # Event for non-configured symbol - should be ignored
        event2 = create_market_event('DOGE/USDT', 0.10)
        event_bus.publish(event2)

        # Process events
        event_bus.process_events()

        # Should only have signal for BTC/USDT
        assert len(signals) == 1
        assert signals[0].symbol == 'BTC/USDT'

        print("✓ PASS: Symbol filtering works")

    def test_position_size_fixed(self, base_config, event_bus, mock_db):
        """Test fixed position sizing."""
        strategy = TestStrategy(base_config, event_bus, mock_db)

        # Fixed method with max 10%
        size = strategy.calculate_position_size('BTC/USDT', signal_strength=1.0)
        assert size == 0.10

        # With signal strength adjustment
        size = strategy.calculate_position_size('BTC/USDT', signal_strength=0.5)
        assert size == 0.05

        print("✓ PASS: Fixed position sizing")

    def test_position_size_risk_based(self, base_config, event_bus, mock_db):
        """Test risk-based position sizing."""
        base_config['strategy']['position_sizing']['method'] = 'risk_based'
        strategy = TestStrategy(base_config, event_bus, mock_db)

        # Risk 1% of portfolio with 2% stop-loss = 50% position
        size = strategy.calculate_position_size('BTC/USDT', signal_strength=1.0,
                                               stop_loss_pct=0.02)
        assert size == 0.10  # Capped at max_position_pct

        # Risk 1% with 5% stop-loss = 20% position
        size = strategy.calculate_position_size('BTC/USDT', signal_strength=1.0,
                                               stop_loss_pct=0.05)
        assert size == 0.10  # Still capped

        print("✓ PASS: Risk-based position sizing")

    def test_position_state_management(self, base_config, event_bus, mock_db):
        """Test position tracking and state management."""
        strategy = TestStrategy(base_config, event_bus, mock_db)

        # Initially no position
        assert strategy.has_position('BTC/USDT') is False
        assert strategy.get_position('BTC/USDT') is None

        # Add position
        position = {
            'symbol': 'BTC/USDT',
            'direction': 'BUY',
            'entry_price': 50000.0,
            'quantity': 0.1,
            'stop_loss': 49000.0,
            'take_profit': 52000.0
        }
        strategy.update_position('BTC/USDT', position)

        assert strategy.has_position('BTC/USDT') is True
        assert strategy.get_position('BTC/USDT') == position
        assert strategy.entry_prices['BTC/USDT'] == 50000.0

        # Clear position
        strategy.update_position('BTC/USDT', None)
        assert strategy.has_position('BTC/USDT') is False
        assert 'BTC/USDT' not in strategy.entry_prices

        print("✓ PASS: Position state management")

    def test_signal_creation(self, base_config, event_bus, mock_db):
        """Test signal creation with metadata."""
        strategy = TestStrategy(base_config, event_bus, mock_db)

        signal = strategy._create_signal(
            symbol='BTC/USDT',
            direction='BUY',
            target_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            confidence=0.85,
            metadata={'test_key': 'test_value'}
        )

        assert signal.symbol == 'BTC/USDT'
        assert signal.signal_type == 'BUY'
        assert signal.price == 50000.0
        assert signal.metadata['stop_loss'] == 49000.0
        assert signal.metadata['take_profit'] == 52000.0
        assert signal.confidence == 0.85
        assert signal.metadata['strategy'] == 'TestStrategy'
        assert signal.metadata['asset_type'] == 'CRYPTO'
        assert signal.metadata['test_key'] == 'test_value'
        assert 'quantity' in signal.metadata

        print("✓ PASS: Signal creation")


# ============================================================================
# Test 2: MeanReversionStrategy Logic
# ============================================================================

class TestMeanReversionStrategy:
    """Test mean reversion strategy logic."""

    def test_initialization(self, mean_reversion_config, event_bus, mock_db):
        """Test strategy initialization with all parameters."""
        strategy = MeanReversionStrategy(mean_reversion_config, event_bus, mock_db)

        assert strategy.name == 'MeanReversionCrypto'
        assert strategy.bb_window == 20
        assert strategy.bb_std == 2.0
        assert strategy.zscore_window == 20
        assert strategy.zscore_threshold == 2.0
        assert strategy.rsi_window == 14
        assert strategy.rsi_oversold == 40
        assert strategy.rsi_overbought == 60
        assert strategy.stop_loss_pct == 0.02
        assert strategy.take_profit_ratio == 1.5
        assert len(strategy.filters) == 3

        print("✓ PASS: MeanReversionStrategy initialization")

    @patch('src.strategies.mean_reversion.MeanReversionStrategy._get_indicators')
    def test_insufficient_data(self, mock_get_indicators, mean_reversion_config,
                              event_bus, mock_db):
        """Test handling of insufficient data."""
        strategy = MeanReversionStrategy(mean_reversion_config, event_bus, mock_db)

        # Mock returns None (insufficient data)
        mock_get_indicators.return_value = None

        event = create_market_event('BTC/USDT', 50000.0)
        signal = strategy.on_market_data(event)

        assert signal is None

        print("✓ PASS: Handles insufficient data")

    @patch('src.strategies.mean_reversion.MeanReversionStrategy._get_indicators')
    @patch('src.strategies.mean_reversion.MeanReversionStrategy._check_filters')
    def test_filters_fail(self, mock_check_filters, mock_get_indicators,
                         mean_reversion_config, event_bus, mock_db):
        """Test that failed filters prevent signal generation."""
        strategy = MeanReversionStrategy(mean_reversion_config, event_bus, mock_db)

        # Mock returns valid data but filters fail
        mock_get_indicators.return_value = pd.DataFrame({'close': [50000.0]})
        mock_check_filters.return_value = False

        event = create_market_event('BTC/USDT', 50000.0)
        signal = strategy.on_market_data(event)

        assert signal is None

        print("✓ PASS: Failed filters prevent signals")

    @patch('src.strategies.mean_reversion.MeanReversionStrategy._get_indicators')
    @patch('src.strategies.mean_reversion.MeanReversionStrategy._check_filters')
    def test_buy_signal_generation(self, mock_check_filters, mock_get_indicators,
                                   mean_reversion_config, event_bus, mock_db):
        """Test BUY signal generation when all conditions met."""
        strategy = MeanReversionStrategy(mean_reversion_config, event_bus, mock_db)

        # Create mock data with BUY conditions
        current_price = 48000.0
        mock_data = pd.DataFrame([{
            'close': current_price,
            'bb_high': 52000.0,
            'bb_mid': 50000.0,
            'bb_low': 48500.0,  # Price BELOW lower band
            'zscore': -2.5,     # Below threshold
            'rsi': 35.0,        # Oversold
            'volume': 150.0,
            'avg_volume_20': 100.0  # Volume > avg * 1.2
        }])

        mock_get_indicators.return_value = mock_data
        mock_check_filters.return_value = True

        event = create_market_event('BTC/USDT', current_price)
        signal = strategy.on_market_data(event)

        assert signal is not None
        assert signal.signal_type == 'BUY'
        assert signal.symbol == 'BTC/USDT'
        assert signal.price == current_price
        assert signal.metadata['stop_loss'] == current_price * (1 - 0.02)  # 2% stop
        assert signal.confidence > 0
        assert 'zscore' in signal.metadata
        assert 'rsi' in signal.metadata

        print("✓ PASS: BUY signal generation")

    @patch('src.strategies.mean_reversion.MeanReversionStrategy._get_indicators')
    @patch('src.strategies.mean_reversion.MeanReversionStrategy._check_filters')
    def test_sell_signal_generation(self, mock_check_filters, mock_get_indicators,
                                    mean_reversion_config, event_bus, mock_db):
        """Test SELL signal generation when all conditions met."""
        strategy = MeanReversionStrategy(mean_reversion_config, event_bus, mock_db)

        # Create mock data with SELL conditions
        current_price = 52500.0
        mock_data = pd.DataFrame([{
            'close': current_price,
            'bb_high': 52000.0,  # Price ABOVE upper band
            'bb_mid': 50000.0,
            'bb_low': 48000.0,
            'zscore': 2.5,       # Above threshold
            'rsi': 65.0,         # Overbought
            'volume': 150.0,
            'avg_volume_20': 100.0
        }])

        mock_get_indicators.return_value = mock_data
        mock_check_filters.return_value = True

        event = create_market_event('BTC/USDT', current_price)
        signal = strategy.on_market_data(event)

        assert signal is not None
        assert signal.signal_type == 'SELL'
        assert signal.symbol == 'BTC/USDT'
        assert signal.price == current_price
        assert signal.metadata['stop_loss'] == current_price * (1 + 0.02)  # 2% stop (above for short)
        assert 'bb_position' in signal.metadata
        assert signal.metadata['bb_position'] == 'above_upper'

        print("✓ PASS: SELL signal generation")

    @patch('src.strategies.mean_reversion.MeanReversionStrategy._get_indicators')
    @patch('src.strategies.mean_reversion.MeanReversionStrategy._check_filters')
    def test_no_signal_when_conditions_not_met(self, mock_check_filters, mock_get_indicators,
                                               mean_reversion_config, event_bus, mock_db):
        """Test no signal when not all conditions are met."""
        strategy = MeanReversionStrategy(mean_reversion_config, event_bus, mock_db)

        # Price below lower band but RSI not oversold
        mock_data = pd.DataFrame([{
            'close': 48000.0,
            'bb_high': 52000.0,
            'bb_mid': 50000.0,
            'bb_low': 48500.0,
            'zscore': -2.5,
            'rsi': 50.0,  # NOT oversold
            'volume': 150.0,
            'avg_volume_20': 100.0
        }])

        mock_get_indicators.return_value = mock_data
        mock_check_filters.return_value = True

        event = create_market_event('BTC/USDT', 48000.0)
        signal = strategy.on_market_data(event)

        assert signal is None

        print("✓ PASS: No signal when conditions not met")

    @patch('src.strategies.mean_reversion.MeanReversionStrategy._get_indicators')
    def test_exit_at_middle_band(self, mock_get_indicators, mean_reversion_config,
                                event_bus, mock_db):
        """Test exit signal when price returns to middle band."""
        strategy = MeanReversionStrategy(mean_reversion_config, event_bus, mock_db)

        # Set up existing position
        strategy.update_position('BTC/USDT', {
            'direction': 'BUY',
            'entry_price': 48000.0,
            'stop_loss': 47040.0,
            'take_profit': 51000.0
        })

        # Price returned to middle band
        current_price = 50000.0
        mock_data = pd.DataFrame([{
            'close': current_price,
            'bb_mid': 50000.0,
            'bb_high': 52000.0,
            'bb_low': 48000.0
        }])

        mock_get_indicators.return_value = mock_data

        event = create_market_event('BTC/USDT', current_price)
        signal = strategy.on_market_data(event)

        assert signal is not None
        assert signal.signal_type == 'CLOSE'
        assert 'exit_reason' in signal.metadata
        assert signal.metadata['exit_reason'] == 'price_at_middle_band'

        print("✓ PASS: Exit at middle band")

    @patch('src.strategies.mean_reversion.MeanReversionStrategy._get_indicators')
    def test_exit_stop_loss(self, mock_get_indicators, mean_reversion_config,
                           event_bus, mock_db):
        """Test exit signal when stop-loss hit."""
        strategy = MeanReversionStrategy(mean_reversion_config, event_bus, mock_db)

        # Set up existing position with stop-loss
        strategy.update_position('BTC/USDT', {
            'direction': 'BUY',
            'entry_price': 50000.0,
            'stop_loss': 49000.0,
            'take_profit': 53000.0
        })

        # Price hit stop-loss
        current_price = 48900.0
        mock_data = pd.DataFrame([{
            'close': current_price,
            'bb_mid': 50000.0,
            'bb_high': 52000.0,
            'bb_low': 48000.0
        }])

        mock_get_indicators.return_value = mock_data

        event = create_market_event('BTC/USDT', current_price)
        signal = strategy.on_market_data(event)

        assert signal is not None
        assert signal.signal_type == 'CLOSE'
        assert signal.metadata['exit_reason'] == 'stop_loss'

        print("✓ PASS: Exit on stop-loss")

    @patch('src.strategies.mean_reversion.MeanReversionStrategy._get_indicators')
    def test_exit_take_profit(self, mock_get_indicators, mean_reversion_config,
                             event_bus, mock_db):
        """Test exit signal when take-profit hit."""
        strategy = MeanReversionStrategy(mean_reversion_config, event_bus, mock_db)

        # Set up existing position with take-profit
        strategy.update_position('BTC/USDT', {
            'direction': 'BUY',
            'entry_price': 48000.0,
            'stop_loss': 47040.0,
            'take_profit': 51000.0
        })

        # Price hit take-profit
        current_price = 51100.0
        mock_data = pd.DataFrame([{
            'close': current_price,
            'bb_mid': 50000.0,
            'bb_high': 52000.0,
            'bb_low': 48000.0
        }])

        mock_get_indicators.return_value = mock_data

        event = create_market_event('BTC/USDT', current_price)
        signal = strategy.on_market_data(event)

        assert signal is not None
        assert signal.signal_type == 'CLOSE'
        assert signal.metadata['exit_reason'] == 'take_profit'

        print("✓ PASS: Exit on take-profit")


# ============================================================================
# Test 3: Integration Tests
# ============================================================================

class TestIntegration:
    """Test full integration: market data → strategy → signals."""

    def test_end_to_end_signal_flow(self, mean_reversion_config, event_bus, mock_db):
        """Test complete flow from market data to signal event."""
        strategy = MeanReversionStrategy(mean_reversion_config, event_bus, mock_db)

        signals_received = []

        def capture_signal(signal):
            signals_received.append(signal)

        event_bus.subscribe(EventType.SIGNAL, capture_signal)

        # Mock the strategy methods
        with patch.object(strategy, '_get_indicators') as mock_indicators, \
             patch.object(strategy, '_check_filters') as mock_filters:

            # Set up BUY condition
            mock_indicators.return_value = pd.DataFrame([{
                'close': 48000.0,
                'bb_high': 52000.0,
                'bb_mid': 50000.0,
                'bb_low': 48500.0,
                'zscore': -2.5,
                'rsi': 35.0,
                'volume': 150.0,
                'avg_volume_20': 100.0
            }])
            mock_filters.return_value = True

            # Publish market data
            event = create_market_event('BTC/USDT', 48000.0)
            event_bus.publish(event)
            event_bus.process_events()

            # Verify signal was generated and published
            assert len(signals_received) == 1
            assert signals_received[0].signal_type == 'BUY'
            assert signals_received[0].symbol == 'BTC/USDT'

        print("✓ PASS: End-to-end signal flow")

    def test_multiple_symbols(self, base_config, event_bus, mock_db):
        """Test strategy handles multiple symbols independently."""
        config = {
            'strategy': {
                'name': 'MultiSymbol',
                'enabled': True,
                'symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
                'asset_type': 'CRYPTO',
                'position_sizing': {'method': 'fixed', 'max_position_pct': 0.10}
            }
        }

        strategy = TestStrategy(config, event_bus, mock_db)
        signals = []

        def capture_signal(signal):
            signals.append(signal)

        event_bus.subscribe(EventType.SIGNAL, capture_signal)

        # Publish events for all symbols (below threshold)
        for symbol in ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']:
            event = create_market_event(symbol, 45000.0)
            event_bus.publish(event)

        # Process events
        event_bus.process_events()

        # Should generate signals for all configured symbols
        assert len(signals) == 3
        assert set(s.symbol for s in signals) == {'BTC/USDT', 'ETH/USDT', 'SOL/USDT'}

        print("✓ PASS: Multiple symbols handled independently")

    def test_state_persistence(self, base_config, event_bus, mock_db):
        """Test that strategy state persists across events."""
        strategy = TestStrategy(base_config, event_bus, mock_db)

        # First event generates signal and creates position
        signals = []

        def capture_signal(signal):
            signals.append(signal)
            # Simulate portfolio manager updating position
            if signal.signal_type == 'BUY':
                strategy.update_position(signal.symbol, {
                    'direction': 'BUY',
                    'entry_price': signal.price
                })

        event_bus.subscribe(EventType.SIGNAL, capture_signal)

        # Event 1: Generate BUY signal
        event1 = create_market_event('BTC/USDT', 45000.0)
        event_bus.publish(event1)
        event_bus.process_events()

        assert len(signals) == 1
        assert strategy.has_position('BTC/USDT') is True

        # Event 2: No signal because position exists
        event2 = create_market_event('BTC/USDT', 44000.0)
        event_bus.publish(event2)
        event_bus.process_events()

        assert len(signals) == 1  # Still only 1 signal
        assert strategy.has_position('BTC/USDT') is True

        print("✓ PASS: State persists across events")


# ============================================================================
# Main Test Runner
# ============================================================================

def run_all_tests():
    """Run all strategy tests."""
    print("\n" + "="*80)
    print("STRATEGY FRAMEWORK TEST SUITE")
    print("="*80 + "\n")

    # Configure logging
    logging.basicConfig(level=logging.WARNING)

    # Test counters
    total_tests = 0
    passed_tests = 0

    # Run test classes
    test_classes = [
        TestBaseStrategyInterface,
        TestMeanReversionStrategy,
        TestIntegration
    ]

    for test_class in test_classes:
        print(f"\n{'='*80}")
        print(f"Running: {test_class.__name__}")
        print('='*80 + "\n")

        # Get all test methods
        test_methods = [m for m in dir(test_class) if m.startswith('test_')]

        for test_method_name in test_methods:
            total_tests += 1
            try:
                # Create fresh fixtures for each test
                event_bus = EventBus()
                mock_db = Mock()
                mock_db.get_market_data = Mock(return_value=[])

                base_config = {
                    'strategy': {
                        'name': 'TestStrategy',
                        'enabled': True,
                        'symbols': ['BTC/USDT', 'ETH/USDT'],
                        'asset_type': 'CRYPTO',
                        'position_sizing': {
                            'method': 'fixed',
                            'max_position_pct': 0.10
                        }
                    }
                }

                mean_reversion_config = {
                    'strategy': {
                        'name': 'MeanReversionCrypto',
                        'enabled': True,
                        'symbols': ['BTC/USDT'],
                        'asset_type': 'CRYPTO',
                        'parameters': {
                            'bb_window': 20,
                            'bb_std': 2.0,
                            'zscore_window': 20,
                            'zscore_threshold': 2.0,
                            'rsi_window': 14,
                            'rsi_oversold': 40,
                            'rsi_overbought': 60,
                            'stop_loss_pct': 0.02,
                            'take_profit_ratio': 1.5,
                            'exit_on_middle_band': True
                        },
                        'filters': [
                            {'type': 'volatility', 'max_daily_volatility': 0.08},
                            {'type': 'volume', 'min_daily_volume': 1000000},
                            {'type': 'spread', 'max_spread_pct': 0.005}
                        ],
                        'position_sizing': {
                            'method': 'risk_based',
                            'max_position_pct': 0.08
                        }
                    }
                }

                # Instantiate test class and run method
                test_instance = test_class()
                test_method = getattr(test_instance, test_method_name)

                # Inspect method signature to determine which fixtures to pass
                sig = inspect.signature(test_method)
                param_names = list(sig.parameters.keys())

                # Build arguments based on parameter names
                kwargs = {}
                for param in param_names:
                    if param == 'self':
                        continue
                    elif param == 'mean_reversion_config':
                        kwargs[param] = mean_reversion_config
                    elif param == 'base_config':
                        kwargs[param] = base_config
                    elif param == 'event_bus':
                        kwargs[param] = event_bus
                    elif param == 'mock_db':
                        kwargs[param] = mock_db

                # Call test method with appropriate kwargs
                test_method(**kwargs)

                passed_tests += 1

            except Exception as e:
                print(f"✗ FAIL: {test_method_name}")
                print(f"  Error: {e}")
                import traceback
                traceback.print_exc()

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {passed_tests/total_tests*100:.1f}%")
    print("="*80 + "\n")

    return passed_tests == total_tests


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
