"""
Paper Trading Demo Script.

Demonstrates the complete trading system working in paper trading mode:
1. Live event-driven architecture
2. Strategy generates signals from simulated market data
3. PortfolioManager converts signals to orders
4. OrderExecutor simulates fills
5. Real-time position tracking and P&L calculation

This script simulates market data for demonstration purposes.
In a real system, market data would come from live exchange feeds via CCXT.
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.event_bus import EventBus
from src.core.events import EventType, MarketDataEvent
from src.core.config import ConfigManager
from src.data.storage import DatabaseManager
from src.strategies.mean_reversion import MeanReversionStrategy
from src.risk.risk_manager import RiskManager
from src.portfolio import PortfolioManager
from src.execution import OrderExecutor, ExecutionMode


def simulate_market_data(event_bus: EventBus, symbol: str, num_bars: int = 20):
    """
    Simulate market data for demonstration.

    In production, this would be replaced with live data from CCXT.

    Args:
        event_bus: EventBus to publish to
        symbol: Trading symbol
        num_bars: Number of bars to simulate
    """
    print(f"\n{'='*60}")
    print(f"Simulating Market Data: {symbol}")
    print(f"{'='*60}\n")

    # Start with a base price
    base_price = 50000.0 if symbol.startswith('BTC') else 2500.0

    # Simulate price movement with trend and volatility
    current_price = base_price
    timestamp = datetime.now()

    for i in range(num_bars):
        # Add random volatility (±2%)
        import random
        price_change_pct = random.uniform(-0.02, 0.02)
        current_price *= (1 + price_change_pct)

        # Create OHLCV bar
        high = current_price * 1.005
        low = current_price * 0.995
        open_price = current_price * random.uniform(0.995, 1.005)
        close = current_price
        volume = random.uniform(100, 1000)

        # Create MarketDataEvent
        event = MarketDataEvent(
            timestamp=timestamp,
            type=EventType.MARKET_DATA,
            symbol=symbol,
            asset_type='CRYPTO',
            timeframe='1h',
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume
        )

        # Publish event
        event_bus.publish(event)

        # Process events (gives strategy time to react)
        event_bus.process_events()

        # Move to next bar
        timestamp += timedelta(hours=1)

        # Brief pause for realism
        time.sleep(0.5)

        print(f"Bar {i+1}/{num_bars}: {symbol} @ ${close:,.2f}")


def main():
    """Run paper trading demo."""
    print("="*60)
    print("QuantSage - Paper Trading Demo")
    print("="*60)
    print("\nThis demo shows the complete trading system in action:")
    print("  1. Strategy analyzes market data")
    print("  2. Generates trading signals")
    print("  3. Risk manager validates signals")
    print("  4. Portfolio manager creates orders")
    print("  5. Order executor simulates fills")
    print("  6. Real-time P&L tracking")
    print()

    # Initialize components
    print("Initializing trading system components...")

    # 1. Event Bus (live mode)
    event_bus = EventBus(mode='live')

    # 2. Database
    db = DatabaseManager(db_path='data/paper_trading.db')

    # 3. Configuration
    config = ConfigManager()
    risk_config = config.get('risk', {})
    strategy_config = config.get_strategy_config('mean_reversion_crypto')

    if strategy_config is None:
        print("ERROR: Strategy config 'mean_reversion_crypto' not found!")
        print("Make sure config/strategies/mean_reversion_crypto.yaml exists")
        return

    # 4. Strategy
    print("\nInitializing Mean Reversion Strategy...")
    strategy = MeanReversionStrategy(
        event_bus=event_bus,
        db=db,
        config=dict(strategy_config)
    )

    # 5. Risk Manager
    print("Initializing Risk Manager...")
    initial_cash = 100000.0
    risk_manager = RiskManager(
        event_bus=event_bus,
        db=db,
        config=dict(risk_config),
        initial_capital=initial_cash
    )

    # 6. Portfolio Manager (live version)
    print(f"Initializing Portfolio Manager with ${initial_cash:,.2f}...")
    portfolio = PortfolioManager(
        event_bus=event_bus,
        db=db,
        initial_cash=initial_cash,
        config={'default_position_size': 0.05}  # 5% per position
    )

    # 7. Order Executor (paper mode)
    print("Initializing Order Executor (PAPER mode)...")
    executor = OrderExecutor(
        event_bus=event_bus,
        db=db,
        mode=ExecutionMode.PAPER,
        config={
            'slippage_pct': 0.001,  # 0.1%
            'commission_pct': {'CRYPTO': 0.006, 'STOCK': 0.0}
        }
    )

    print("\nAll components initialized successfully!")
    print(f"Initial Cash: ${initial_cash:,.2f}")
    print(f"Position Size: 5% of portfolio per trade")
    print()

    # Run simulation
    input("Press Enter to start paper trading simulation...")

    try:
        # Simulate market data for BTC/USDT
        simulate_market_data(
            event_bus=event_bus,
            symbol='BTC/USDT',
            num_bars=20
        )

        # Show results
        print(f"\n{'='*60}")
        print("Paper Trading Results")
        print(f"{'='*60}\n")

        # Portfolio summary
        portfolio_value = portfolio.get_portfolio_value()
        pnl = portfolio.get_total_pnl()
        positions = portfolio.get_positions_summary()

        print(f"Final Portfolio Value: ${portfolio_value:,.2f}")
        print(f"Cash Balance: ${portfolio.cash:,.2f}")
        print(f"Total P&L: ${pnl['total']:,.2f}")
        print(f"Return: {(pnl['total']/initial_cash)*100:.2f}%")
        print(f"\nOpen Positions: {len(positions)}")

        if positions:
            print("\nPosition Details:")
            for pos in positions:
                print(f"  {pos['side']} {pos['quantity']:.6f} {pos['symbol']} "
                      f"@ ${pos['entry_price']:,.2f} | "
                      f"Unrealized P&L: ${pos['pnl_unrealized']:,.2f} "
                      f"({pos['return_pct']:.2f}%)")

        # Risk Manager stats
        print(f"\nRisk Manager Status:")
        if hasattr(risk_manager, 'circuit_breaker_active'):
            print(f"  Circuit Breaker: {'ACTIVE ⚠️' if risk_manager.circuit_breaker_active else 'OK ✓'}")
        print(f"  Daily Loss Limit: 5% of portfolio")
        print(f"  Max Drawdown Limit: 20%")

        print(f"\n{'='*60}")
        print("Demo Complete!")
        print(f"{'='*60}\n")

        print("Database saved to: data/paper_trading.db")
        print("Review positions and trades in the database for full history.")

    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
    except Exception as e:
        print(f"\nError during demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
