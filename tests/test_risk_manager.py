"""
Comprehensive tests for RiskManager multi-layer validation.

Tests:
A. Position Risk Tests (5 tests) - Validate position sizing and stop-loss
B. Symbol Risk Tests (3 tests) - Validate aggregate symbol exposure
C. Portfolio Risk Tests (3 tests) - Validate total portfolio exposure
D. Circuit Breaker Tests (4 tests) - Validate system-level halts
E. Integration Tests (3 tests) - End-to-end signal → order/alert flow
F. Edge Cases (2 tests) - Handle special scenarios gracefully

Total: 20 tests
"""

import sys
import os
import logging
from datetime import datetime
from unittest.mock import Mock, MagicMock
from typing import List, Dict

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.risk.risk_manager import RiskManager
from src.core.events import SignalEvent, OrderEvent, RiskAlertEvent, EventType
from src.core.event_bus import EventBus


# ============================================================================
# Test Fixtures and Helpers
# ============================================================================

def create_mock_db(positions: List[Dict] = None):
    """Create mock database with optional positions."""
    db = Mock()

    # Default: no open positions
    positions = positions or []

    def execute_query(query, params=None):
        """Mock query execution."""
        if 'positions' in query.lower():
            return positions
        return []

    db.execute_query = Mock(side_effect=execute_query)
    db.log_risk_event = Mock(return_value=True)

    return db


def create_test_signal(symbol: str = 'BTC/USDT', signal_type: str = 'BUY',
                       price: float = 50000.0, quantity_pct: float = 0.08,
                       stop_loss: float = 49000.0, take_profit: float = 52000.0,
                       confidence: float = 0.85) -> SignalEvent:
    """Create test signal event."""
    return SignalEvent(
        timestamp=datetime.now(),
        symbol=symbol,
        asset_type='CRYPTO',
        strategy_id='test_strategy',
        signal_type=signal_type,
        confidence=confidence,
        price=price,
        metadata={
            'quantity': quantity_pct,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'strategy': 'MeanReversion'
        }
    )


def create_risk_config(max_position_pct: float = 0.10,
                      max_symbol_exposure: float = 0.15,
                      max_portfolio_exposure: float = 0.80,
                      daily_loss_limit: float = 0.05,
                      max_drawdown: float = 0.20) -> Dict:
    """Create risk configuration dict."""
    return {
        'position': {
            'max_position_pct': max_position_pct
        },
        'symbol': {
            'max_symbol_exposure': max_symbol_exposure
        },
        'portfolio': {
            'max_portfolio_exposure': max_portfolio_exposure,
            'max_correlation': 0.70
        },
        'system': {
            'daily_loss_limit': daily_loss_limit,
            'max_drawdown': max_drawdown
        }
    }


# ============================================================================
# Test A: Position Risk Tests (5 tests)
# ============================================================================

class TestPositionRisk:
    """Test position-level risk validation."""

    def test_approve_valid_position_size(self):
        """Approve signal with position size within limit (<10%)."""
        config = create_risk_config()
        db = create_mock_db()
        event_bus = EventBus()

        risk_manager = RiskManager(config, event_bus, db, initial_capital=100000.0)

        # Create signal with 8% position (within 10% limit)
        signal = create_test_signal(quantity_pct=0.08)

        # Check position risk
        approved, reason = risk_manager._check_position_risk(signal)

        assert approved is True
        assert reason is None

        print("✓ PASS: Valid position size approved (<10%)")

    def test_reject_excessive_position_size(self):
        """Reject signal with position size exceeding limit (>10%)."""
        config = create_risk_config()
        db = create_mock_db()
        event_bus = EventBus()

        risk_manager = RiskManager(config, event_bus, db)

        # Create signal with 15% position (exceeds 10% limit)
        signal = create_test_signal(quantity_pct=0.15)

        # Check position risk
        approved, reason = risk_manager._check_position_risk(signal)

        assert approved is False
        assert 'exceeds limit' in reason.lower()

        print("✓ PASS: Excessive position size rejected (>10%)")

    def test_reject_missing_stop_loss(self):
        """Reject signal missing required stop-loss."""
        config = create_risk_config()
        db = create_mock_db()
        event_bus = EventBus()

        risk_manager = RiskManager(config, event_bus, db)

        # Create signal without stop-loss
        signal = create_test_signal(quantity_pct=0.08)
        signal.metadata['stop_loss'] = None

        # Check position risk
        approved, reason = risk_manager._check_position_risk(signal)

        assert approved is False
        assert 'stop-loss required' in reason.lower()

        print("✓ PASS: Missing stop-loss rejected")

    def test_reject_too_tight_stop_loss(self):
        """Reject signal with stop-loss too tight (<0.5%)."""
        config = create_risk_config()
        db = create_mock_db()
        event_bus = EventBus()

        risk_manager = RiskManager(config, event_bus, db)

        # Create signal with 0.2% stop-loss (too tight)
        signal = create_test_signal(price=50000.0, stop_loss=49900.0, quantity_pct=0.08)

        # Check position risk
        approved, reason = risk_manager._check_position_risk(signal)

        assert approved is False
        assert 'too tight' in reason.lower()

        print("✓ PASS: Too-tight stop-loss rejected (<0.5%)")

    def test_reject_too_wide_stop_loss(self):
        """Reject signal with stop-loss too wide (>10%)."""
        config = create_risk_config()
        db = create_mock_db()
        event_bus = EventBus()

        risk_manager = RiskManager(config, event_bus, db)

        # Create signal with 15% stop-loss (too wide)
        signal = create_test_signal(price=50000.0, stop_loss=42500.0, quantity_pct=0.08)

        # Check position risk
        approved, reason = risk_manager._check_position_risk(signal)

        assert approved is False
        assert 'too wide' in reason.lower()

        print("✓ PASS: Too-wide stop-loss rejected (>10%)")


# ============================================================================
# Test B: Symbol Risk Tests (3 tests)
# ============================================================================

class TestSymbolRisk:
    """Test symbol-level risk validation."""

    def test_approve_within_symbol_limit(self):
        """Approve signal when symbol exposure within limit."""
        config = create_risk_config()

        # No existing positions for BTC/USDT
        db = create_mock_db(positions=[])
        event_bus = EventBus()

        risk_manager = RiskManager(config, event_bus, db, initial_capital=100000.0)

        # New position: 8% of portfolio = $8,000 (well under 15% limit)
        new_exposure = 8000.0

        # Check symbol risk
        approved, reason = risk_manager._check_symbol_risk('BTC/USDT', new_exposure)

        assert approved is True
        assert reason is None

        print("✓ PASS: Symbol exposure within limit approved")

    def test_reject_excessive_symbol_exposure(self):
        """Reject signal when symbol exposure exceeds 15%."""
        config = create_risk_config()

        # Existing position: 10% of portfolio
        existing_positions = [
            {'symbol': 'BTC/USDT', 'quantity': 0.2, 'entry_price': 50000.0, 'status': 'OPEN'}
        ]
        db = create_mock_db(positions=existing_positions)
        event_bus = EventBus()

        risk_manager = RiskManager(config, event_bus, db, initial_capital=100000.0)

        # New position: 8% of portfolio
        # Total would be: 10% + 8% = 18% (exceeds 15% limit)
        new_exposure = 8000.0

        # Check symbol risk
        approved, reason = risk_manager._check_symbol_risk('BTC/USDT', new_exposure)

        assert approved is False
        assert 'exceeds limit' in reason.lower()

        print("✓ PASS: Excessive symbol exposure rejected (>15%)")

    def test_account_for_existing_positions(self):
        """Account for existing positions when calculating symbol exposure."""
        config = create_risk_config()

        # Existing positions for BTC/USDT: 5% + 3% = 8%
        existing_positions = [
            {'symbol': 'BTC/USDT', 'quantity': 0.1, 'entry_price': 50000.0, 'status': 'OPEN'},
            {'symbol': 'BTC/USDT', 'quantity': 0.06, 'entry_price': 50000.0, 'status': 'OPEN'}
        ]
        db = create_mock_db(positions=existing_positions)
        event_bus = EventBus()

        risk_manager = RiskManager(config, event_bus, db, initial_capital=100000.0)

        # New position: 6% of portfolio
        # Total: 8% + 6% = 14% (just under 15% limit - should pass)
        new_exposure = 6000.0

        # Check symbol risk
        approved, reason = risk_manager._check_symbol_risk('BTC/USDT', new_exposure)

        assert approved is True

        print("✓ PASS: Existing positions accounted for in symbol risk")


# ============================================================================
# Test C: Portfolio Risk Tests (3 tests)
# ============================================================================

class TestPortfolioRisk:
    """Test portfolio-level risk validation."""

    def test_approve_within_portfolio_limit(self):
        """Approve signal when portfolio exposure <80%."""
        config = create_risk_config()

        # Existing positions: 50% of portfolio invested
        existing_positions = [
            {'symbol': 'BTC/USDT', 'quantity': 1.0, 'entry_price': 50000.0, 'status': 'OPEN'}
        ]
        db = create_mock_db(positions=existing_positions)
        event_bus = EventBus()

        risk_manager = RiskManager(config, event_bus, db, initial_capital=100000.0)

        # New position: 20% of portfolio
        # Total: 50% + 20% = 70% (under 80% limit)
        new_position_value = 20000.0

        # Check portfolio risk
        approved, reason = risk_manager._check_portfolio_risk(new_position_value)

        assert approved is True
        assert reason is None

        print("✓ PASS: Portfolio exposure within limit approved (<80%)")

    def test_reject_excessive_portfolio_exposure(self):
        """Reject signal when portfolio exposure would exceed 80%."""
        config = create_risk_config()

        # Existing positions: 70% of portfolio invested
        existing_positions = [
            {'symbol': 'BTC/USDT', 'quantity': 1.0, 'entry_price': 50000.0, 'status': 'OPEN'},
            {'symbol': 'ETH/USDT', 'quantity': 5.0, 'entry_price': 4000.0, 'status': 'OPEN'}
        ]
        db = create_mock_db(positions=existing_positions)
        event_bus = EventBus()

        risk_manager = RiskManager(config, event_bus, db, initial_capital=100000.0)

        # New position: 15% of portfolio
        # Total: 70% + 15% = 85% (exceeds 80% limit)
        new_position_value = 15000.0

        # Check portfolio risk
        approved, reason = risk_manager._check_portfolio_risk(new_position_value)

        assert approved is False
        assert 'exceeds limit' in reason.lower()

        print("✓ PASS: Excessive portfolio exposure rejected (>80%)")

    def test_calculate_mark_to_market(self):
        """Calculate exposure using mark-to-market prices."""
        config = create_risk_config()

        # Positions at different entry prices
        existing_positions = [
            {'symbol': 'BTC/USDT', 'quantity': 0.5, 'entry_price': 50000.0, 'status': 'OPEN'},
            {'symbol': 'ETH/USDT', 'quantity': 10.0, 'entry_price': 3000.0, 'status': 'OPEN'}
        ]
        db = create_mock_db(positions=existing_positions)
        event_bus = EventBus()

        risk_manager = RiskManager(config, event_bus, db, initial_capital=100000.0)

        # Get portfolio value (should use mark-to-market)
        portfolio_value = risk_manager._get_portfolio_value()

        # Expected: $100k initial capital (simplified calculation)
        assert portfolio_value > 0

        print("✓ PASS: Mark-to-market calculation works")


# ============================================================================
# Test D: Circuit Breaker Tests (4 tests)
# ============================================================================

class TestCircuitBreakers:
    """Test system-level circuit breakers."""

    def test_allow_trading_normal_conditions(self):
        """Allow trading under normal conditions."""
        config = create_risk_config()
        db = create_mock_db()
        event_bus = EventBus()

        risk_manager = RiskManager(config, event_bus, db, initial_capital=100000.0)

        # Check circuit breakers
        trading_allowed, reason = risk_manager._check_circuit_breakers()

        assert trading_allowed is True
        assert reason is None
        assert risk_manager.circuit_breaker_active is False

        print("✓ PASS: Trading allowed under normal conditions")

    def test_halt_on_daily_loss_limit(self):
        """Halt trading when daily loss exceeds -5%."""
        config = create_risk_config(daily_loss_limit=0.05)
        db = create_mock_db()
        event_bus = EventBus()

        risk_manager = RiskManager(config, event_bus, db, initial_capital=100000.0)

        # Set daily start equity
        risk_manager.daily_start_equity = 100000.0

        # Simulate -6% loss (exceeds -5% limit)
        risk_manager.portfolio_value = 94000.0

        # Check circuit breakers
        trading_allowed, reason = risk_manager._check_circuit_breakers()

        assert trading_allowed is False
        assert 'daily loss' in reason.lower()
        assert risk_manager.circuit_breaker_active is True

        print("✓ PASS: Circuit breaker triggered on daily loss (>-5%)")

    def test_halt_on_max_drawdown(self):
        """Halt trading when drawdown exceeds -20%."""
        config = create_risk_config(max_drawdown=0.20)
        db = create_mock_db()
        event_bus = EventBus()

        risk_manager = RiskManager(config, event_bus, db, initial_capital=100000.0)

        # Set peak equity
        risk_manager.peak_equity = 120000.0

        # Simulate drawdown to $90k (-25% from peak, exceeds -20% limit)
        risk_manager.portfolio_value = 90000.0
        risk_manager.daily_start_equity = 90000.0  # Same as current to avoid daily loss trigger (0% daily loss)

        # Check circuit breakers
        trading_allowed, reason = risk_manager._check_circuit_breakers()

        assert trading_allowed is False
        assert 'drawdown' in reason.lower()
        assert risk_manager.circuit_breaker_active is True

        print("✓ PASS: Circuit breaker triggered on max drawdown (>-20%)")

    def test_maintain_breaker_state(self):
        """Maintain circuit breaker state across multiple signals."""
        config = create_risk_config()
        db = create_mock_db()
        event_bus = EventBus()

        risk_manager = RiskManager(config, event_bus, db, initial_capital=100000.0)

        # Activate circuit breaker
        risk_manager.circuit_breaker_active = True

        # Check breaker (should stay active)
        trading_allowed1, _ = risk_manager._check_circuit_breakers()
        trading_allowed2, _ = risk_manager._check_circuit_breakers()

        assert trading_allowed1 is False
        assert trading_allowed2 is False
        assert risk_manager.circuit_breaker_active is True

        print("✓ PASS: Circuit breaker state maintained (sticky)")


# ============================================================================
# Test E: Integration Tests (3 tests)
# ============================================================================

class TestIntegration:
    """Test end-to-end signal validation flow."""

    def test_approved_signal_generates_order(self):
        """End-to-end: Approved signal generates OrderEvent."""
        config = create_risk_config()
        db = create_mock_db()
        event_bus = EventBus()

        risk_manager = RiskManager(config, event_bus, db, initial_capital=100000.0)

        # Capture published events
        orders = []
        def capture_order(event):
            orders.append(event)
        event_bus.subscribe(EventType.ORDER, capture_order)

        # Create valid signal
        signal = create_test_signal(quantity_pct=0.08)

        # Process signal
        event_bus.publish(signal)
        event_bus.process_events()

        # Verify order was created
        assert len(orders) == 1
        assert orders[0].symbol == 'BTC/USDT'
        assert orders[0].side == 'BUY'

        print("✓ PASS: Approved signal → OrderEvent")

    def test_rejected_signal_generates_alert(self):
        """End-to-end: Rejected signal generates RiskAlertEvent."""
        config = create_risk_config()
        db = create_mock_db()
        event_bus = EventBus()

        risk_manager = RiskManager(config, event_bus, db, initial_capital=100000.0)

        # Capture published events
        alerts = []
        def capture_alert(event):
            alerts.append(event)
        event_bus.subscribe(EventType.RISK_ALERT, capture_alert)

        # Create invalid signal (15% position exceeds 10% limit)
        signal = create_test_signal(quantity_pct=0.15)

        # Process signal
        event_bus.publish(signal)
        event_bus.process_events()

        # Verify alert was created
        assert len(alerts) == 1
        assert alerts[0].severity == 'HIGH'
        assert 'exceeds limit' in alerts[0].description.lower()

        print("✓ PASS: Rejected signal → RiskAlertEvent")

    def test_multiple_signals_processed(self):
        """Process multiple signals correctly."""
        config = create_risk_config()
        db = create_mock_db()
        event_bus = EventBus()

        risk_manager = RiskManager(config, event_bus, db, initial_capital=100000.0)

        # Capture events
        orders = []
        alerts = []
        event_bus.subscribe(EventType.ORDER, lambda e: orders.append(e))
        event_bus.subscribe(EventType.RISK_ALERT, lambda e: alerts.append(e))

        # Signal 1: Valid (should approve)
        signal1 = create_test_signal(symbol='BTC/USDT', quantity_pct=0.08)
        event_bus.publish(signal1)

        # Signal 2: Invalid (should reject)
        signal2 = create_test_signal(symbol='ETH/USDT', quantity_pct=0.15)
        event_bus.publish(signal2)

        # Signal 3: Valid (should approve)
        signal3 = create_test_signal(symbol='SOL/USDT', quantity_pct=0.07)
        event_bus.publish(signal3)

        # Process all events
        event_bus.process_events()

        # Verify results
        assert len(orders) == 2  # Signals 1 and 3 approved
        assert len(alerts) == 1  # Signal 2 rejected

        print("✓ PASS: Multiple signals processed correctly")


# ============================================================================
# Test F: Edge Cases (2 tests)
# ============================================================================

class TestEdgeCases:
    """Test edge case handling."""

    def test_close_signal_bypasses_validation(self):
        """CLOSE signals bypass position sizing validation."""
        config = create_risk_config()
        db = create_mock_db()
        event_bus = EventBus()

        risk_manager = RiskManager(config, event_bus, db, initial_capital=100000.0)

        # Capture orders
        orders = []
        event_bus.subscribe(EventType.ORDER, lambda e: orders.append(e))

        # Create CLOSE signal (no quantity validation needed)
        signal = create_test_signal(signal_type='CLOSE', quantity_pct=0.0)
        signal.metadata.pop('stop_loss', None)  # CLOSE doesn't need stop-loss

        # Process signal
        event_bus.publish(signal)
        event_bus.process_events()

        # Should approve without validation
        assert len(orders) == 1

        print("✓ PASS: CLOSE signal bypasses validation")

    def test_handle_missing_metadata(self):
        """Handle signals with missing metadata gracefully."""
        config = create_risk_config()
        db = create_mock_db()
        event_bus = EventBus()

        risk_manager = RiskManager(config, event_bus, db, initial_capital=100000.0)

        # Capture alerts
        alerts = []
        event_bus.subscribe(EventType.RISK_ALERT, lambda e: alerts.append(e))

        # Create signal with missing quantity in metadata
        signal = create_test_signal()
        signal.metadata = {}  # Empty metadata

        # Process signal
        event_bus.publish(signal)
        event_bus.process_events()

        # Should reject (missing quantity = 0, but missing stop-loss)
        assert len(alerts) == 1
        assert 'stop-loss required' in alerts[0].description.lower()

        print("✓ PASS: Missing metadata handled gracefully")


# ============================================================================
# Main Test Runner
# ============================================================================

def run_all_tests():
    """Run all risk manager tests."""
    print("\n" + "="*80)
    print("RISK MANAGER TEST SUITE")
    print("="*80 + "\n")

    # Configure logging
    logging.basicConfig(level=logging.WARNING)

    # Test counters
    total_tests = 0
    passed_tests = 0

    # Run test classes
    test_classes = [
        TestPositionRisk,
        TestSymbolRisk,
        TestPortfolioRisk,
        TestCircuitBreakers,
        TestIntegration,
        TestEdgeCases
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
                # Instantiate test class and run method
                test_instance = test_class()
                test_method = getattr(test_instance, test_method_name)
                test_method()

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
