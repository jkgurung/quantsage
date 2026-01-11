# QuantSage - Production-Ready Multi-Asset Trading System

A quantitative trading system for cryptocurrencies and stocks with comprehensive backtesting, risk management, and execution capabilities.

## Features

- **Multi-Asset Support**: Trade cryptocurrencies (via CCXT) and stocks (via Alpaca)
- **Event-Driven Architecture**: Same code runs in backtest and live modes
- **Multiple Strategies**: Mean reversion, momentum, and ML-based strategies
- **Risk Management**: Multi-layer protection (position, symbol, portfolio, system levels)
- **Backtesting Engine**: Realistic simulation with transaction costs and slippage
- **Paper Trading**: Validate strategies without risking capital

## Project Status

🚧 **Under Development** - Week 1: Core Infrastructure

Currently implementing:
- Database schema and storage layer
- Event system
- Configuration management
- Data collection pipeline

## Quick Start

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 4. Initialize database
python scripts/init_db.py

# 5. Run backtest (coming soon)
python scripts/run_backtest.py --strategy mean_reversion
```

## Architecture

```
Event-Driven System:
Data → Events → Strategies → Signals → Risk Check → Orders → Execution
```

See `/docs/architecture.md` for detailed design documentation.

## Development Timeline

- **Week 1-2**: Core infrastructure (database, events, config) ✅ In Progress
- **Week 3-4**: Strategy framework and risk management
- **Week 5**: Backtesting engine
- **Week 6**: Portfolio management and execution
- **Week 7**: Monitoring and dashboard
- **Week 8**: Production hardening

## Trading Approach

**Initial Focus: Cryptocurrency (via Coinbase)**
- Backtesting and paper trading only (no real money initially)
- Validate strategies on historical data
- Realistic fee modeling (0.4-0.6%)

**Future Expansion: Stocks**
- Add after crypto system is validated
- Commission-free trading via Alpaca

## License

MIT License - See LICENSE file for details

## Disclaimer

This software is for educational purposes. Trading cryptocurrencies and stocks involves substantial risk of loss. Past performance does not guarantee future results. Use at your own risk.
