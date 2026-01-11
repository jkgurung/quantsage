"""
Backtest Engine - Main Orchestrator.

Event-driven backtesting engine that replays historical data through
strategies and risk management, simulating execution and calculating metrics.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd

from src.core.events import EventType, MarketDataEvent
from src.core.event_bus import EventBus
from src.core.config import ConfigManager
from src.data.storage import DatabaseManager
from src.strategies.mean_reversion import MeanReversionStrategy
from src.risk.risk_manager import RiskManager
from src.backtesting.execution import ExecutionEngine
from src.backtesting.portfolio import PortfolioManager
from src.backtesting.metrics import PerformanceCalculator
from src.backtesting.report import BacktestReport

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Event-driven backtesting engine.

    Features:
    - Replays historical market data as MarketDataEvents
    - Coordinates all components via EventBus
    - Tracks portfolio state and equity curve
    - Calculates comprehensive performance metrics
    - Generates HTML reports with charts

    Components:
    - Strategy: Generates SignalEvents
    - RiskManager: Validates signals, publishes OrderEvents
    - ExecutionEngine: Simulates fills, publishes FillEvents
    - PortfolioManager: Tracks positions and P&L
    """

    def __init__(self, strategy_config: Dict, symbols: List[str],
                 start_date: datetime, end_date: datetime,
                 initial_capital: float = 100000.0,
                 risk_config: Dict = None,
                 backtest_id: str = None):
        """
        Initialize backtest engine.

        Args:
            strategy_config: Strategy configuration dict
            symbols: List of symbols to trade
            start_date: Backtest start date
            end_date: Backtest end date
            initial_capital: Starting capital (default: $100,000)
            risk_config: Risk configuration dict
            backtest_id: Unique backtest ID (auto-generated if not provided)
        """
        self.strategy_config = strategy_config
        self.symbols = symbols
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.risk_config = risk_config or {}

        # Generate backtest ID
        self.backtest_id = backtest_id or f"bt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Database path (isolated for this backtest)
        self.db_path = f"data/backtests/{self.backtest_id}.db"

        # State tracking
        self.cash = initial_capital
        self.equity_curve = [(start_date, initial_capital)]
        self.current_timestamp = None
        self.current_bars = {}  # symbol -> current bar dict (shared with ExecutionEngine)
        self.current_prices = {}  # symbol -> latest close price

        # Components (initialized in _initialize_components)
        self.event_bus = None
        self.db = None
        self.strategy = None
        self.risk_manager = None
        self.execution_engine = None
        self.portfolio_manager = None

        logger.info(f"BacktestEngine initialized: {self.backtest_id}")
        logger.info(f"Symbols: {symbols}")
        logger.info(f"Period: {start_date.date()} to {end_date.date()}")
        logger.info(f"Initial Capital: ${initial_capital:,.2f}")

    def run(self) -> Dict:
        """
        Execute backtest and return performance metrics.

        Process:
        1. Initialize all components
        2. Load and validate historical data
        3. Create chronologically sorted event stream
        4. For each timestamp:
           a. Check if new trading day → reset daily tracking
           b. Publish MarketDataEvent for all symbols at timestamp
           c. Process event queue (strategy → risk → execution → portfolio)
           d. Update portfolio value and equity curve
           e. Update RiskManager state
        5. Close any open positions at end
        6. Calculate performance metrics
        7. Save results to database
        8. Return metrics dict

        Returns:
            Dict of performance metrics
        """
        logger.info(f"Starting backtest: {self.backtest_id}")

        # 1. Initialize components
        self._initialize_components()

        # 2. Load historical data
        logger.info("Loading historical data...")
        market_data_df = self._load_market_data()

        if market_data_df.empty:
            logger.error("No historical data found!")
            return self._empty_results()

        logger.info(f"Loaded {len(market_data_df)} bars")

        # 3. Group by timestamp for chronological processing
        grouped = market_data_df.groupby('timestamp')
        total_timestamps = len(grouped)

        logger.info(f"Processing {total_timestamps} timestamps...")

        # 4. Process bar-by-bar
        for i, (timestamp, bars_df) in enumerate(grouped, 1):
            self.current_timestamp = timestamp

            # Progress logging
            if i % 100 == 0 or i == total_timestamps:
                logger.info(f"Progress: {i}/{total_timestamps} ({i/total_timestamps*100:.1f}%)")

            # Check for new trading day
            if self._is_new_trading_day(timestamp):
                self._reset_daily_tracking()

            # Create dict of bars {symbol: {open, high, low, close, volume}}
            for _, row in bars_df.iterrows():
                symbol = row['symbol']
                self.current_bars[symbol] = {
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'volume': row['volume']
                }
                self.current_prices[symbol] = row['close']

            # Publish MarketDataEvents for all symbols
            for symbol in self.current_bars:
                bar = self.current_bars[symbol]
                event = MarketDataEvent(
                    timestamp=timestamp,
                    type=EventType.MARKET_DATA,
                    symbol=symbol,
                    asset_type='CRYPTO',  # TODO: Get from config
                    ohlcv=bar,
                    data_source='backtest'
                )
                self.event_bus.publish(event)

            # Process event queue (strategy → risk → execution → portfolio)
            self.event_bus.process_events()

            # Update portfolio state
            self._update_portfolio_state()

        # 5. Close open positions
        logger.info("Closing open positions...")
        self._close_open_positions()

        # 6. Calculate metrics
        logger.info("Calculating performance metrics...")
        metrics = self._calculate_metrics()

        # 7. Save results
        logger.info("Saving results to database...")
        self._save_results(metrics)

        logger.info(f"Backtest complete: {self.backtest_id}")
        logger.info(f"Total Return: {metrics['returns']['total_return_pct']*100:.2f}%")
        logger.info(f"Sharpe Ratio: {metrics['risk_adjusted']['sharpe_ratio']:.2f}")
        logger.info(f"Max Drawdown: {metrics['drawdown']['max_drawdown_pct']*100:.2f}%")
        logger.info(f"Total Trades: {metrics['trades']['total_trades']}")

        return metrics

    def _initialize_components(self):
        """Initialize all backtest components."""
        logger.info("Initializing components...")

        # Create database directory
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # EventBus in backtest mode (enables event_history)
        self.event_bus = EventBus(mode='backtest')

        # Database (isolated)
        self.db = DatabaseManager(self.db_path)

        # Strategy
        self.strategy = MeanReversionStrategy(
            config=self.strategy_config,
            event_bus=self.event_bus,
            db=self.db
        )

        # RiskManager
        self.risk_manager = RiskManager(
            config=self.risk_config,
            event_bus=self.event_bus,
            db=self.db,
            initial_capital=self.initial_capital
        )

        # ExecutionEngine
        self.execution_engine = ExecutionEngine(
            event_bus=self.event_bus,
            db=self.db,
            current_bars=self.current_bars,  # Shared reference
            config=self.risk_config
        )

        # PortfolioManager
        self.portfolio_manager = PortfolioManager(
            event_bus=self.event_bus,
            db=self.db,
            initial_cash=self.initial_capital
        )

        logger.info("Components initialized successfully")

    def _load_market_data(self) -> pd.DataFrame:
        """
        Load and sort historical data chronologically.

        Returns:
            DataFrame with columns: timestamp, symbol, open, high, low, close, volume
        """
        # Query database for historical data
        data_rows = []

        for symbol in self.symbols:
            rows = self.db.get_market_data(
                symbol=symbol,
                start_date=self.start_date,
                end_date=self.end_date
            )
            data_rows.extend(rows)

        if not data_rows:
            logger.warning(f"No data found for symbols {self.symbols}")
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.DataFrame(data_rows)

        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Sort chronologically (CRITICAL for no look-ahead bias)
        df = df.sort_values('timestamp')

        return df

    def _update_portfolio_state(self):
        """
        Update portfolio value and RiskManager state.

        Called after each timestamp is processed.
        """
        # Get current portfolio value from PortfolioManager
        portfolio_value = self.portfolio_manager.get_portfolio_value(self.current_prices)

        # Update equity curve
        self.equity_curve.append((self.current_timestamp, portfolio_value))

        # Update RiskManager state
        self.risk_manager.portfolio_value = portfolio_value

        # Update peak equity if new high
        if portfolio_value > self.risk_manager.peak_equity:
            self.risk_manager.peak_equity = portfolio_value

    def _is_new_trading_day(self, timestamp: datetime) -> bool:
        """
        Check if we've crossed into a new trading day.

        Args:
            timestamp: Current timestamp

        Returns:
            True if new trading day
        """
        if not hasattr(self, '_last_trading_day'):
            self._last_trading_day = timestamp.date()
            return True

        current_day = timestamp.date()
        if current_day > self._last_trading_day:
            self._last_trading_day = current_day
            return True

        return False

    def _reset_daily_tracking(self):
        """Reset daily tracking at start of new day."""
        portfolio_value = self.portfolio_manager.get_portfolio_value(self.current_prices)
        self.risk_manager.daily_start_equity = portfolio_value
        logger.debug(f"New trading day - Starting equity: ${portfolio_value:,.2f}")

    def _close_open_positions(self):
        """Force close all open positions at backtest end."""
        open_positions = self.db.get_open_positions()

        if not open_positions:
            return

        logger.info(f"Closing {len(open_positions)} open positions")

        for position in open_positions:
            symbol = position['symbol']
            current_price = self.current_prices.get(symbol, position['entry_price'])

            # Update position as closed
            # Calculate realized P&L
            if position['side'] == 'LONG':
                pnl = (current_price - position['entry_price']) * position['quantity']
            else:  # SHORT
                pnl = (position['entry_price'] - current_price) * position['quantity']

            self.db.update_position(
                position_id=position['id'],
                exit_price=current_price,
                exit_time=self.current_timestamp,
                pnl_realized=pnl,
                status='CLOSED'
            )

            logger.debug(f"Closed {symbol}: P&L ${pnl:+,.2f}")

    def _calculate_metrics(self) -> Dict:
        """
        Calculate performance metrics using PerformanceCalculator.

        Returns:
            Dict of metrics
        """
        # Get all closed trades
        trades = self.db.query(
            "SELECT * FROM positions WHERE status = 'CLOSED' ORDER BY exit_time"
        )

        # Create PerformanceCalculator
        calculator = PerformanceCalculator(
            equity_curve=self.equity_curve,
            trades=trades,
            initial_capital=self.initial_capital,
            start_date=self.start_date,
            end_date=self.end_date,
            risk_free_rate=0.03
        )

        # Calculate all metrics
        metrics = calculator.calculate_all()

        return metrics

    def _save_results(self, metrics: Dict):
        """
        Persist results to database.

        Args:
            metrics: Metrics dict from PerformanceCalculator
        """
        import json

        final_value = self.equity_curve[-1][1] if self.equity_curve else self.initial_capital

        self.db.save_backtest_results(
            backtest_id=self.backtest_id,
            strategy_id=self.strategy_config.get('name', 'unknown'),
            symbols=json.dumps(self.symbols),
            asset_type='CRYPTO',
            start_date=self.start_date.isoformat(),
            end_date=self.end_date.isoformat(),
            initial_capital=self.initial_capital,
            final_capital=final_value,
            metrics=metrics,
            config=json.dumps({
                'strategy': self.strategy_config,
                'risk': self.risk_config
            }),
            results=json.dumps({
                'equity_curve_length': len(self.equity_curve),
                'total_bars': len(self.equity_curve) - 1
            })
        )

    def generate_report(self, output_dir: str = "reports/") -> str:
        """
        Generate HTML report with charts and exports.

        Args:
            output_dir: Directory for report files

        Returns:
            Path to HTML report
        """
        logger.info("Generating backtest report...")

        # Get trades
        trades = self.db.query(
            "SELECT * FROM positions WHERE status = 'CLOSED' ORDER BY exit_time"
        )

        # Calculate metrics
        metrics = self._calculate_metrics()

        # Create report generator
        report = BacktestReport(
            backtest_id=self.backtest_id,
            metrics=metrics,
            equity_curve=self.equity_curve,
            trades=trades,
            initial_capital=self.initial_capital
        )

        # Generate report
        html_path = report.generate(output_dir=output_dir)

        logger.info(f"Report generated: {html_path}")

        return html_path

    def _empty_results(self) -> Dict:
        """Return empty results dict when no data."""
        return {
            'returns': {
                'total_return': 0.0,
                'total_return_pct': 0.0,
                'cagr': 0.0,
                'annualized_return': 0.0
            },
            'risk_adjusted': {
                'sharpe_ratio': 0.0,
                'sortino_ratio': 0.0,
                'calmar_ratio': 0.0,
                'volatility': 0.0
            },
            'drawdown': {
                'max_drawdown': 0.0,
                'max_drawdown_pct': 0.0,
                'avg_drawdown': 0.0,
                'max_dd_duration_days': 0
            },
            'trades': {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'expectancy': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'max_win': 0.0,
                'max_loss': 0.0,
                'avg_trade_duration_hours': 0.0
            },
            'monthly': {
                'best_month': 0.0,
                'worst_month': 0.0,
                'avg_month': 0.0,
                'positive_months_pct': 0.0
            }
        }
