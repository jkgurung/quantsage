"""
Run a backtest with MeanReversionStrategy on historical crypto data.

This script demonstrates the complete backtesting workflow:
1. Load historical market data
2. Initialize strategy and risk management
3. Run event-driven backtest
4. Calculate performance metrics
5. Generate HTML report
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import ConfigManager
from src.backtesting import BacktestEngine
from src.data.storage import DatabaseManager

def main():
    print("=" * 60)
    print("QuantSage Backtesting Engine - Demo")
    print("=" * 60)
    print()

    # Load configurations
    print("Loading configurations...")
    config = ConfigManager()
    strategy_config = config.get_strategy_config('mean_reversion_crypto')

    if strategy_config is None:
        print("ERROR: Strategy config 'mean_reversion_crypto' not found!")
        return

    # Convert OmegaConf to dict for compatibility
    strategy_config = dict(strategy_config)
    risk_config = dict(config.get('risk', {}))

    print(f"Strategy: {strategy_config.get('name', 'MeanReversion')}")
    print(f"Symbols: {strategy_config.get('symbols', [])}")
    print()

    # Check if we have data
    print("Checking for historical data...")
    db = DatabaseManager()

    # Query for available data
    symbols = strategy_config.get('symbols', ['BTC/USDT'])
    available_data = []

    for symbol in symbols:
        data = db.get_market_data(
            symbol=symbol,
            start_date=datetime.now() - timedelta(days=365),
            end_date=datetime.now()
        )
        if data:
            available_data.append((symbol, len(data)))
            print(f"  ✓ {symbol}: {len(data)} bars available")
        else:
            print(f"  ✗ {symbol}: No data found")

    if not available_data:
        print()
        print("ERROR: No historical data found!")
        print()
        print("To collect data, run:")
        print("  python scripts/collect_crypto_data.py")
        return

    print()

    # Set backtest parameters
    # Use last 30 days of available data for demo
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    initial_capital = 100000.0

    print("Backtest Parameters:")
    print(f"  Period: {start_date.date()} to {end_date.date()}")
    print(f"  Initial Capital: ${initial_capital:,.2f}")
    print(f"  Symbols: {symbols}")
    print()

    # Initialize backtest engine
    print("Initializing backtest engine...")
    engine = BacktestEngine(
        strategy_config=strategy_config,
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        risk_config=risk_config
    )

    print(f"Backtest ID: {engine.backtest_id}")
    print()

    # Run backtest
    print("=" * 60)
    print("Running backtest...")
    print("=" * 60)
    print()

    try:
        results = engine.run()

        print()
        print("=" * 60)
        print("Backtest Complete!")
        print("=" * 60)
        print()

        # Display results
        print("PERFORMANCE SUMMARY")
        print("-" * 60)

        returns = results.get('returns', {})
        print(f"Total Return:        {returns.get('total_return_pct', 0)*100:>10.2f}%")
        print(f"CAGR:                {returns.get('cagr', 0)*100:>10.2f}%")
        print(f"Annualized Return:   {returns.get('annualized_return', 0)*100:>10.2f}%")
        print()

        risk = results.get('risk_adjusted', {})
        print(f"Sharpe Ratio:        {risk.get('sharpe_ratio', 0):>10.2f}")
        print(f"Sortino Ratio:       {risk.get('sortino_ratio', 0):>10.2f}")
        print(f"Calmar Ratio:        {risk.get('calmar_ratio', 0):>10.2f}")
        print(f"Volatility:          {risk.get('volatility', 0)*100:>10.2f}%")
        print()

        dd = results.get('drawdown', {})
        print(f"Max Drawdown:        {dd.get('max_drawdown_pct', 0)*100:>10.2f}%")
        print(f"Max DD Duration:     {dd.get('max_dd_duration_days', 0):>10.0f} days")
        print(f"Avg Drawdown:        {dd.get('avg_drawdown', 0)*100:>10.2f}%")
        print()

        trades = results.get('trades', {})
        print(f"Total Trades:        {trades.get('total_trades', 0):>10.0f}")
        print(f"Winning Trades:      {trades.get('winning_trades', 0):>10.0f}")
        print(f"Losing Trades:       {trades.get('losing_trades', 0):>10.0f}")
        print(f"Win Rate:            {trades.get('win_rate', 0)*100:>10.2f}%")
        print(f"Profit Factor:       {trades.get('profit_factor', 0):>10.2f}")
        print(f"Expectancy:          ${trades.get('expectancy', 0):>10.2f}")
        print(f"Avg Win:             ${trades.get('avg_win', 0):>10.2f}")
        print(f"Avg Loss:            ${trades.get('avg_loss', 0):>10.2f}")
        print()

        monthly = results.get('monthly', {})
        print(f"Best Month:          {monthly.get('best_month', 0)*100:>10.2f}%")
        print(f"Worst Month:         {monthly.get('worst_month', 0)*100:>10.2f}%")
        print(f"Avg Month:           {monthly.get('avg_month', 0)*100:>10.2f}%")
        print(f"Positive Months:     {monthly.get('positive_months_pct', 0)*100:>10.2f}%")
        print()

        # Generate report
        print("=" * 60)
        print("Generating HTML report...")
        print("=" * 60)
        print()

        report_path = engine.generate_report()

        print(f"✓ Report generated: {report_path}")
        print()
        print(f"Open in browser: file://{Path(report_path).absolute()}")
        print()

    except Exception as e:
        print()
        print(f"ERROR: Backtest failed!")
        print(f"  {type(e).__name__}: {e}")
        print()
        import traceback
        traceback.print_exc()
        return

    print("=" * 60)
    print("Backtest session complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
