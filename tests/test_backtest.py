"""
Comprehensive Test Suite for Backtesting Engine.

Tests all backtesting components:
- ExecutionEngine: Fill simulation, slippage, commission
- PortfolioManager: Position tracking, P&L calculation
- PerformanceCalculator: Metrics calculation
- BacktestEngine: Integration and orchestration
- BacktestReport: Report generation
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import json

import pandas as pd
import numpy as np

from src.core.events import EventType, OrderEvent, FillEvent, MarketDataEvent
from src.core.event_bus import EventBus
from src.data.storage import DatabaseManager
from src.backtesting.execution import ExecutionEngine
from src.backtesting.portfolio import PortfolioManager
from src.backtesting.metrics import PerformanceCalculator
from src.backtesting.report import BacktestReport
from src.backtesting.engine import BacktestEngine


class TestExecutionEngine(unittest.TestCase):
    """Test ExecutionEngine order fill simulation."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = f"{self.temp_dir}/test.db"
        self.db = DatabaseManager(self.db_path)
        self.event_bus = EventBus(mode='backtest')

        # Config with slippage/commission settings
        self.config = {
            'transaction_costs': {
                'crypto': {
                    'taker_fee': 0.006
                },
                'stocks': {
                    'sec_fee': 0.0000278,
                    'finra_taf': 0.000166
                },
                'slippage_params': {
                    'base_slippage': 0.001,
                    'volume_impact': 0.00001
                }
            }
        }

        # Current bars dict
        self.current_bars = {}

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)

    def test_execution_market_buy_fills_at_high(self):
        """Test that market BUY orders fill at bar high (worst price for buyer)."""
        # Set up current bar
        self.current_bars['BTC/USDT'] = {
            'open': 40000,
            'high': 40500,
            'low': 39500,
            'close': 40200,
            'volume': 100
        }

        # Create execution engine
        engine = ExecutionEngine(self.event_bus, self.db, self.current_bars, self.config)

        # Track fills
        fills = []
        def on_fill(fill):
            fills.append(fill)
        self.event_bus.subscribe(EventType.FILL, on_fill)

        # Create BUY order
        order = OrderEvent(
            timestamp=datetime.now(),
            type=EventType.ORDER,
            order_id='TEST-BUY-001',
            symbol='BTC/USDT',
            asset_type='CRYPTO',
            side='BUY',
            order_type='MARKET',
            quantity=1.0,
            price=None,
            metadata={'strategy_id': 'test'}
        )

        # Publish order
        self.event_bus.publish(order)
        self.event_bus.process_events()

        # Verify fill
        self.assertEqual(len(fills), 1)
        fill = fills[0]

        # Fill price should be high + slippage (worse for buyer)
        self.assertGreater(fill.price, 40500)  # Higher than bar high
        self.assertLess(fill.price, 41000)     # But reasonable

    def test_execution_market_sell_fills_at_low(self):
        """Test that market SELL orders fill at bar low (worst price for seller)."""
        self.current_bars['ETH/USDT'] = {
            'open': 2000,
            'high': 2050,
            'low': 1950,
            'close': 2020,
            'volume': 500
        }

        engine = ExecutionEngine(self.event_bus, self.db, self.current_bars, self.config)

        fills = []
        def on_fill(fill):
            fills.append(fill)
        self.event_bus.subscribe(EventType.FILL, on_fill)

        # Create SELL order
        order = OrderEvent(
            timestamp=datetime.now(),
            type=EventType.ORDER,
            order_id='TEST-SELL-001',
            symbol='ETH/USDT',
            asset_type='CRYPTO',
            side='SELL',
            order_type='MARKET',
            quantity=10.0,
            price=None,
            metadata={'strategy_id': 'test'}
        )

        self.event_bus.publish(order)
        self.event_bus.process_events()

        # Verify fill
        self.assertEqual(len(fills), 1)
        fill = fills[0]

        # Fill price should be low - slippage (worse for seller)
        self.assertLess(fill.price, 1950)   # Lower than bar low
        self.assertGreater(fill.price, 1900)  # But reasonable

    def test_execution_slippage_increases_with_volume(self):
        """Test that slippage increases with order size relative to bar volume."""
        self.current_bars['BTC/USDT'] = {
            'open': 50000,
            'high': 50500,
            'low': 49500,
            'close': 50000,
            'volume': 10  # Small volume
        }

        engine = ExecutionEngine(self.event_bus, self.db, self.current_bars, self.config)

        fills = []
        def on_fill(fill):
            fills.append(fill)
        self.event_bus.subscribe(EventType.FILL, on_fill)

        # Small order
        small_order = OrderEvent(
            timestamp=datetime.now(),
            type=EventType.ORDER,
            order_id='SMALL-001',
            symbol='BTC/USDT',
            asset_type='CRYPTO',
            side='BUY',
            order_type='MARKET',
            quantity=0.1,  # Small relative to volume
            price=None,
            metadata={'strategy_id': 'test'}
        )

        self.event_bus.publish(small_order)
        self.event_bus.process_events()

        small_fill_price = fills[0].price
        fills.clear()

        # Large order
        large_order = OrderEvent(
            timestamp=datetime.now(),
            type=EventType.ORDER,
            order_id='LARGE-001',
            symbol='BTC/USDT',
            asset_type='CRYPTO',
            side='BUY',
            order_type='MARKET',
            quantity=5.0,  # Large relative to volume
            price=None,
            metadata={'strategy_id': 'test'}
        )

        self.event_bus.publish(large_order)
        self.event_bus.process_events()

        large_fill_price = fills[0].price

        # Large order should have worse fill (higher price for BUY)
        self.assertGreater(large_fill_price, small_fill_price)

    def test_execution_crypto_commission_correct(self):
        """Test that crypto commission is calculated correctly (0.6% taker fee)."""
        self.current_bars['BTC/USDT'] = {
            'open': 50000,
            'high': 50000,
            'low': 50000,
            'close': 50000,
            'volume': 100
        }

        engine = ExecutionEngine(self.event_bus, self.db, self.current_bars, self.config)

        fills = []
        def on_fill(fill):
            fills.append(fill)
        self.event_bus.subscribe(EventType.FILL, on_fill)

        order = OrderEvent(
            timestamp=datetime.now(),
            type=EventType.ORDER,
            order_id='CRYPTO-001',
            symbol='BTC/USDT',
            asset_type='CRYPTO',
            side='BUY',
            order_type='MARKET',
            quantity=1.0,
            price=None,
            metadata={'strategy_id': 'test'}
        )

        self.event_bus.publish(order)
        self.event_bus.process_events()

        fill = fills[0]

        # Commission should be ~0.6% of order value
        expected_commission = fill.quantity * fill.price * 0.006
        self.assertAlmostEqual(fill.commission, expected_commission, places=2)

    def test_execution_stock_commission_correct(self):
        """Test that stock commission includes SEC/FINRA fees on sells."""
        self.current_bars['AAPL'] = {
            'open': 150,
            'high': 151,
            'low': 149,
            'close': 150,
            'volume': 1000000
        }

        engine = ExecutionEngine(self.event_bus, self.db, self.current_bars, self.config)

        fills = []
        def on_fill(fill):
            fills.append(fill)
        self.event_bus.subscribe(EventType.FILL, on_fill)

        # SELL order (should have fees)
        sell_order = OrderEvent(
            timestamp=datetime.now(),
            type=EventType.ORDER,
            order_id='STOCK-SELL-001',
            symbol='AAPL',
            asset_type='STOCK',
            side='SELL',
            order_type='MARKET',
            quantity=100,
            price=None,
            metadata={'strategy_id': 'test'}
        )

        self.event_bus.publish(sell_order)
        self.event_bus.process_events()

        sell_fill = fills[0]

        # Should have SEC + FINRA fees
        self.assertGreater(sell_fill.commission, 0)

        fills.clear()

        # BUY order (should have no fees)
        buy_order = OrderEvent(
            timestamp=datetime.now(),
            type=EventType.ORDER,
            order_id='STOCK-BUY-001',
            symbol='AAPL',
            asset_type='STOCK',
            side='BUY',
            order_type='MARKET',
            quantity=100,
            price=None,
            metadata={'strategy_id': 'test'}
        )

        self.event_bus.publish(buy_order)
        self.event_bus.process_events()

        buy_fill = fills[0]

        # BUY should have no commission
        self.assertEqual(buy_fill.commission, 0.0)


class TestPortfolioManager(unittest.TestCase):
    """Test PortfolioManager position tracking and P&L calculation."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = f"{self.temp_dir}/test.db"
        self.db = DatabaseManager(self.db_path)
        self.event_bus = EventBus(mode='backtest')
        self.initial_cash = 100000.0

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)

    def test_portfolio_open_long_position(self):
        """Test opening a LONG position."""
        portfolio = PortfolioManager(self.event_bus, self.db, self.initial_cash)

        # Create BUY fill
        fill = FillEvent(
            timestamp=datetime.now(),
            type=EventType.FILL,
            trade_id='TRADE-001',
            order_id='ORDER-001',
            symbol='BTC/USDT',
            asset_type='CRYPTO',
            side='BUY',
            quantity=1.0,
            price=50000.0,
            commission=300.0,
            metadata={'strategy_id': 'test'}
        )

        self.event_bus.publish(fill)
        self.event_bus.process_events()

        # Check position created
        positions = self.db.get_open_positions()
        self.assertEqual(len(positions), 1)

        pos = positions[0]
        self.assertEqual(pos['symbol'], 'BTC/USDT')
        self.assertEqual(pos['side'], 'LONG')
        self.assertEqual(pos['quantity'], 1.0)
        self.assertEqual(pos['entry_price'], 50000.0)

        # Check cash deducted
        expected_cash = self.initial_cash - (50000.0 + 300.0)
        self.assertAlmostEqual(portfolio.cash, expected_cash, places=2)

    def test_portfolio_close_long_position_correct_pnl(self):
        """Test closing LONG position calculates correct P&L."""
        portfolio = PortfolioManager(self.event_bus, self.db, self.initial_cash)

        # Open position
        buy_fill = FillEvent(
            timestamp=datetime.now(),
            type=EventType.FILL,
            trade_id='TRADE-001',
            order_id='ORDER-001',
            symbol='BTC/USDT',
            asset_type='CRYPTO',
            side='BUY',
            quantity=1.0,
            price=50000.0,
            commission=300.0,
            metadata={'strategy_id': 'test'}
        )

        self.event_bus.publish(buy_fill)
        self.event_bus.process_events()

        # Close position (profitable)
        sell_fill = FillEvent(
            timestamp=datetime.now() + timedelta(hours=1),
            type=EventType.FILL,
            trade_id='TRADE-002',
            order_id='ORDER-002',
            symbol='BTC/USDT',
            asset_type='CRYPTO',
            side='SELL',
            quantity=1.0,
            price=52000.0,  # +$2000 profit
            commission=312.0,
            metadata={'strategy_id': 'test'}
        )

        self.event_bus.publish(sell_fill)
        self.event_bus.process_events()

        # Check position closed
        open_positions = self.db.get_open_positions()
        self.assertEqual(len(open_positions), 0)

        # Check P&L
        closed_positions = self.db.query(
            "SELECT * FROM positions WHERE status = 'CLOSED'"
        )
        self.assertEqual(len(closed_positions), 1)

        pos = closed_positions[0]

        # P&L = (exit - entry) * qty - total_commission
        expected_pnl = (52000.0 - 50000.0) * 1.0 - (300.0 + 312.0)
        self.assertAlmostEqual(pos['pnl_realized'], expected_pnl, places=2)

        # Check cash returned
        expected_cash = self.initial_cash - (50000.0 + 300.0) + (52000.0 - 312.0)
        self.assertAlmostEqual(portfolio.cash, expected_cash, places=2)

    def test_portfolio_open_short_position(self):
        """Test opening a SHORT position."""
        portfolio = PortfolioManager(self.event_bus, self.db, self.initial_cash)

        # Create SHORT sell fill
        fill = FillEvent(
            timestamp=datetime.now(),
            type=EventType.FILL,
            trade_id='TRADE-001',
            order_id='ORDER-001',
            symbol='BTC/USDT',
            asset_type='CRYPTO',
            side='SELL',  # SHORT
            quantity=1.0,
            price=50000.0,
            commission=300.0,
            metadata={'strategy_id': 'test'}
        )

        self.event_bus.publish(fill)
        self.event_bus.process_events()

        # Check position created
        positions = self.db.get_open_positions()
        self.assertEqual(len(positions), 1)

        pos = positions[0]
        self.assertEqual(pos['side'], 'SHORT')

        # Check cash increased (short sale proceeds)
        expected_cash = self.initial_cash + (50000.0 - 300.0)
        self.assertAlmostEqual(portfolio.cash, expected_cash, places=2)

    def test_portfolio_close_short_position_correct_pnl(self):
        """Test closing SHORT position calculates correct P&L."""
        portfolio = PortfolioManager(self.event_bus, self.db, self.initial_cash)

        # Open SHORT position
        sell_fill = FillEvent(
            timestamp=datetime.now(),
            type=EventType.FILL,
            trade_id='TRADE-001',
            order_id='ORDER-001',
            symbol='BTC/USDT',
            asset_type='CRYPTO',
            side='SELL',
            quantity=1.0,
            price=50000.0,
            commission=300.0,
            metadata={'strategy_id': 'test'}
        )

        self.event_bus.publish(sell_fill)
        self.event_bus.process_events()

        # Cover SHORT (profitable - price dropped)
        buy_fill = FillEvent(
            timestamp=datetime.now() + timedelta(hours=1),
            type=EventType.FILL,
            trade_id='TRADE-002',
            order_id='ORDER-002',
            symbol='BTC/USDT',
            asset_type='CRYPTO',
            side='BUY',  # Cover short
            quantity=1.0,
            price=48000.0,  # Price dropped, profit
            commission=288.0,
            metadata={'strategy_id': 'test'}
        )

        self.event_bus.publish(buy_fill)
        self.event_bus.process_events()

        # Check P&L
        closed_positions = self.db.query(
            "SELECT * FROM positions WHERE status = 'CLOSED'"
        )
        pos = closed_positions[0]

        # SHORT P&L = (entry - exit) * qty - total_commission
        expected_pnl = (50000.0 - 48000.0) * 1.0 - (300.0 + 288.0)
        self.assertAlmostEqual(pos['pnl_realized'], expected_pnl, places=2)

    def test_portfolio_unrealized_pnl_calculation(self):
        """Test unrealized P&L calculation for open positions."""
        portfolio = PortfolioManager(self.event_bus, self.db, self.initial_cash)

        # Open LONG position
        buy_fill = FillEvent(
            timestamp=datetime.now(),
            type=EventType.FILL,
            trade_id='TRADE-001',
            order_id='ORDER-001',
            symbol='BTC/USDT',
            asset_type='CRYPTO',
            side='BUY',
            quantity=1.0,
            price=50000.0,
            commission=300.0,
            metadata={'strategy_id': 'test'}
        )

        self.event_bus.publish(buy_fill)
        self.event_bus.process_events()

        # Get portfolio value with price increase
        current_prices = {'BTC/USDT': 52000.0}
        portfolio_value = portfolio.get_portfolio_value(current_prices)

        # Expected: cash + (current_price * quantity)
        expected_cash = self.initial_cash - (50000.0 + 300.0)
        expected_value = expected_cash + (52000.0 * 1.0)

        self.assertAlmostEqual(portfolio_value, expected_value, places=2)

    def test_portfolio_cash_balance_updates(self):
        """Test that cash balance updates correctly through position lifecycle."""
        portfolio = PortfolioManager(self.event_bus, self.db, self.initial_cash)

        starting_cash = portfolio.cash
        self.assertEqual(starting_cash, self.initial_cash)

        # BUY
        buy_fill = FillEvent(
            timestamp=datetime.now(),
            type=EventType.FILL,
            trade_id='TRADE-001',
            order_id='ORDER-001',
            symbol='ETH/USDT',
            asset_type='CRYPTO',
            side='BUY',
            quantity=10.0,
            price=2000.0,
            commission=120.0,
            metadata={'strategy_id': 'test'}
        )

        self.event_bus.publish(buy_fill)
        self.event_bus.process_events()

        after_buy_cash = portfolio.cash
        expected_after_buy = starting_cash - (10.0 * 2000.0 + 120.0)
        self.assertAlmostEqual(after_buy_cash, expected_after_buy, places=2)

        # SELL
        sell_fill = FillEvent(
            timestamp=datetime.now() + timedelta(hours=1),
            type=EventType.FILL,
            trade_id='TRADE-002',
            order_id='ORDER-002',
            symbol='ETH/USDT',
            asset_type='CRYPTO',
            side='SELL',
            quantity=10.0,
            price=2100.0,
            commission=126.0,
            metadata={'strategy_id': 'test'}
        )

        self.event_bus.publish(sell_fill)
        self.event_bus.process_events()

        final_cash = portfolio.cash
        expected_final = after_buy_cash + (10.0 * 2100.0 - 126.0)
        self.assertAlmostEqual(final_cash, expected_final, places=2)


class TestPerformanceCalculator(unittest.TestCase):
    """Test PerformanceCalculator metrics calculation."""

    def test_metrics_total_return(self):
        """Test total return calculation."""
        initial_capital = 100000.0

        # Create simple equity curve: $100k → $120k
        equity_curve = [
            (datetime(2023, 1, 1), 100000.0),
            (datetime(2023, 6, 1), 110000.0),
            (datetime(2023, 12, 31), 120000.0)
        ]

        calculator = PerformanceCalculator(
            equity_curve=equity_curve,
            trades=[],
            initial_capital=initial_capital,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            risk_free_rate=0.03
        )

        metrics = calculator.calculate_all()

        # Total return should be 20%
        self.assertAlmostEqual(metrics['returns']['total_return'], 20000.0, places=2)
        self.assertAlmostEqual(metrics['returns']['total_return_pct'], 0.20, places=4)

    def test_metrics_sharpe_ratio_known_returns(self):
        """Test Sharpe ratio with known returns."""
        initial_capital = 100000.0

        # Create equity curve with consistent positive returns
        base_date = datetime(2023, 1, 1)
        equity_curve = []
        equity = initial_capital

        for i in range(252):  # 1 year of daily data
            equity_curve.append((base_date + timedelta(days=i), equity))
            equity *= 1.001  # 0.1% daily return

        calculator = PerformanceCalculator(
            equity_curve=equity_curve,
            trades=[],
            initial_capital=initial_capital,
            start_date=base_date,
            end_date=base_date + timedelta(days=251),
            risk_free_rate=0.03
        )

        metrics = calculator.calculate_all()

        # Sharpe should be positive and reasonable
        self.assertGreater(metrics['risk_adjusted']['sharpe_ratio'], 0)
        self.assertLess(metrics['risk_adjusted']['sharpe_ratio'], 10)  # Sanity check

    def test_metrics_sortino_ratio(self):
        """Test Sortino ratio calculation."""
        initial_capital = 100000.0

        # Create equity curve with some volatility
        base_date = datetime(2023, 1, 1)
        equity_curve = []
        equity = initial_capital

        returns = [0.01, -0.005, 0.015, -0.002, 0.01] * 50  # Mixed returns

        for i, ret in enumerate(returns):
            equity_curve.append((base_date + timedelta(days=i), equity))
            equity *= (1 + ret)

        calculator = PerformanceCalculator(
            equity_curve=equity_curve,
            trades=[],
            initial_capital=initial_capital,
            start_date=base_date,
            end_date=base_date + timedelta(days=len(returns)-1),
            risk_free_rate=0.03
        )

        metrics = calculator.calculate_all()

        # Sortino should be calculated (uses downside deviation)
        self.assertIsNotNone(metrics['risk_adjusted']['sortino_ratio'])
        self.assertGreater(metrics['risk_adjusted']['sortino_ratio'], 0)

    def test_metrics_max_drawdown(self):
        """Test max drawdown calculation."""
        initial_capital = 100000.0

        # Create equity curve with known drawdown
        equity_curve = [
            (datetime(2023, 1, 1), 100000.0),   # Peak
            (datetime(2023, 2, 1), 95000.0),    # -5%
            (datetime(2023, 3, 1), 90000.0),    # -10% (max DD)
            (datetime(2023, 4, 1), 95000.0),    # Recovery
            (datetime(2023, 5, 1), 100000.0),   # Full recovery
            (datetime(2023, 6, 1), 105000.0)    # New high
        ]

        calculator = PerformanceCalculator(
            equity_curve=equity_curve,
            trades=[],
            initial_capital=initial_capital,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 6, 1),
            risk_free_rate=0.03
        )

        metrics = calculator.calculate_all()

        # Max drawdown should be -10%
        self.assertAlmostEqual(metrics['drawdown']['max_drawdown_pct'], -0.10, places=4)
        self.assertAlmostEqual(metrics['drawdown']['max_drawdown'], -10000.0, places=2)

    def test_metrics_win_rate(self):
        """Test win rate calculation."""
        # Create trade list with known win rate
        trades = [
            {'status': 'CLOSED', 'pnl_realized': 1000.0, 'entry_time': '2023-01-01', 'exit_time': '2023-01-02'},
            {'status': 'CLOSED', 'pnl_realized': -500.0, 'entry_time': '2023-01-03', 'exit_time': '2023-01-04'},
            {'status': 'CLOSED', 'pnl_realized': 2000.0, 'entry_time': '2023-01-05', 'exit_time': '2023-01-06'},
            {'status': 'CLOSED', 'pnl_realized': 1500.0, 'entry_time': '2023-01-07', 'exit_time': '2023-01-08'},
            {'status': 'CLOSED', 'pnl_realized': -800.0, 'entry_time': '2023-01-09', 'exit_time': '2023-01-10'}
        ]
        # 3 winners, 2 losers = 60% win rate

        equity_curve = [
            (datetime(2023, 1, 1), 100000.0),
            (datetime(2023, 1, 10), 103200.0)
        ]

        calculator = PerformanceCalculator(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=100000.0,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 10),
            risk_free_rate=0.03
        )

        metrics = calculator.calculate_all()

        # Win rate should be 60%
        self.assertAlmostEqual(metrics['trades']['win_rate'], 0.60, places=4)
        self.assertEqual(metrics['trades']['winning_trades'], 3)
        self.assertEqual(metrics['trades']['losing_trades'], 2)

    def test_metrics_profit_factor(self):
        """Test profit factor calculation."""
        trades = [
            {'status': 'CLOSED', 'pnl_realized': 1000.0, 'entry_time': '2023-01-01', 'exit_time': '2023-01-02'},
            {'status': 'CLOSED', 'pnl_realized': 2000.0, 'entry_time': '2023-01-03', 'exit_time': '2023-01-04'},
            {'status': 'CLOSED', 'pnl_realized': -500.0, 'entry_time': '2023-01-05', 'exit_time': '2023-01-06'},
            {'status': 'CLOSED', 'pnl_realized': -500.0, 'entry_time': '2023-01-07', 'exit_time': '2023-01-08'}
        ]
        # Total wins: $3000, Total losses: $1000 → Profit factor = 3.0

        equity_curve = [
            (datetime(2023, 1, 1), 100000.0),
            (datetime(2023, 1, 8), 102000.0)
        ]

        calculator = PerformanceCalculator(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=100000.0,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 8),
            risk_free_rate=0.03
        )

        metrics = calculator.calculate_all()

        # Profit factor should be 3.0
        self.assertAlmostEqual(metrics['trades']['profit_factor'], 3.0, places=2)

    def test_metrics_expectancy(self):
        """Test expectancy calculation."""
        trades = [
            {'status': 'CLOSED', 'pnl_realized': 1000.0, 'entry_time': '2023-01-01', 'exit_time': '2023-01-02'},
            {'status': 'CLOSED', 'pnl_realized': 1000.0, 'entry_time': '2023-01-03', 'exit_time': '2023-01-04'},
            {'status': 'CLOSED', 'pnl_realized': -400.0, 'entry_time': '2023-01-05', 'exit_time': '2023-01-06'},
            {'status': 'CLOSED', 'pnl_realized': -400.0, 'entry_time': '2023-01-07', 'exit_time': '2023-01-08'},
            {'status': 'CLOSED', 'pnl_realized': -400.0, 'entry_time': '2023-01-09', 'exit_time': '2023-01-10'}
        ]
        # Win rate: 40%, Avg win: $1000, Avg loss: $400
        # Expectancy = (0.4 * 1000) - (0.6 * 400) = 400 - 240 = $160

        equity_curve = [
            (datetime(2023, 1, 1), 100000.0),
            (datetime(2023, 1, 10), 100800.0)
        ]

        calculator = PerformanceCalculator(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=100000.0,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 10),
            risk_free_rate=0.03
        )

        metrics = calculator.calculate_all()

        # Expectancy should be ~$160
        self.assertAlmostEqual(metrics['trades']['expectancy'], 160.0, places=1)

    def test_metrics_cagr(self):
        """Test CAGR calculation."""
        initial_capital = 100000.0

        # 1 year: $100k → $110k = 10% CAGR
        equity_curve = [
            (datetime(2023, 1, 1), 100000.0),
            (datetime(2024, 1, 1), 110000.0)
        ]

        calculator = PerformanceCalculator(
            equity_curve=equity_curve,
            trades=[],
            initial_capital=initial_capital,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2024, 1, 1),
            risk_free_rate=0.03
        )

        metrics = calculator.calculate_all()

        # CAGR should be ~10%
        self.assertAlmostEqual(metrics['returns']['cagr'], 0.10, places=3)


class TestBacktestReport(unittest.TestCase):
    """Test BacktestReport generation."""

    def test_report_generates_all_files(self):
        """Test that report generates all expected files."""
        temp_dir = tempfile.mkdtemp()

        try:
            # Create sample data
            equity_curve = [
                (datetime(2023, 1, 1), 100000.0),
                (datetime(2023, 6, 1), 110000.0),
                (datetime(2023, 12, 31), 120000.0)
            ]

            trades = [
                {
                    'symbol': 'BTC/USDT',
                    'side': 'LONG',
                    'quantity': 1.0,
                    'entry_price': 40000.0,
                    'entry_time': '2023-01-01',
                    'exit_price': 42000.0,
                    'exit_time': '2023-01-02',
                    'pnl_realized': 2000.0,
                    'status': 'CLOSED'
                }
            ]

            metrics = {
                'returns': {
                    'total_return': 20000.0,
                    'total_return_pct': 0.20,
                    'cagr': 0.20,
                    'annualized_return': 0.20
                },
                'risk_adjusted': {
                    'sharpe_ratio': 1.5,
                    'sortino_ratio': 2.0,
                    'calmar_ratio': 1.0,
                    'volatility': 0.15
                },
                'drawdown': {
                    'max_drawdown': -5000.0,
                    'max_drawdown_pct': -0.05,
                    'avg_drawdown': -2000.0,
                    'max_dd_duration_days': 30
                },
                'trades': {
                    'total_trades': 1,
                    'winning_trades': 1,
                    'losing_trades': 0,
                    'win_rate': 1.0,
                    'profit_factor': float('inf'),
                    'expectancy': 2000.0,
                    'avg_win': 2000.0,
                    'avg_loss': 0.0,
                    'max_win': 2000.0,
                    'max_loss': 0.0,
                    'avg_trade_duration_hours': 24.0
                },
                'monthly': {
                    'best_month': 0.10,
                    'worst_month': 0.0,
                    'avg_month': 0.05,
                    'positive_months_pct': 1.0,
                    'monthly_returns': {}
                }
            }

            report = BacktestReport(
                backtest_id='test_bt_001',
                metrics=metrics,
                equity_curve=equity_curve,
                trades=trades,
                initial_capital=100000.0
            )

            html_path = report.generate(output_dir=temp_dir)

            # Check HTML report exists
            self.assertTrue(Path(html_path).exists())

            # Check charts exist
            self.assertTrue(Path(temp_dir, 'test_bt_001_equity_curve.png').exists())
            self.assertTrue(Path(temp_dir, 'test_bt_001_drawdown.png').exists())

            # Check exports exist
            self.assertTrue(Path(temp_dir, 'test_bt_001_trades.csv').exists())
            self.assertTrue(Path(temp_dir, 'test_bt_001_results.json').exists())

        finally:
            shutil.rmtree(temp_dir)

    def test_report_json_structure(self):
        """Test that JSON export has correct structure."""
        temp_dir = tempfile.mkdtemp()

        try:
            equity_curve = [(datetime(2023, 1, 1), 100000.0)]
            trades = []

            metrics = {
                'returns': {'total_return': 0.0},
                'risk_adjusted': {'sharpe_ratio': 0.0},
                'drawdown': {'max_drawdown': 0.0},
                'trades': {'total_trades': 0},
                'monthly': {'best_month': 0.0}
            }

            report = BacktestReport(
                backtest_id='test_json',
                metrics=metrics,
                equity_curve=equity_curve,
                trades=trades,
                initial_capital=100000.0
            )

            report.generate(output_dir=temp_dir)

            # Load and verify JSON
            json_path = Path(temp_dir, 'test_json_results.json')
            with open(json_path, 'r') as f:
                results = json.load(f)

            # Check structure
            self.assertIn('backtest_id', results)
            self.assertIn('initial_capital', results)
            self.assertIn('final_value', results)
            self.assertIn('metrics', results)
            self.assertIn('num_trades', results)

        finally:
            shutil.rmtree(temp_dir)


if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)
