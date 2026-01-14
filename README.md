# QuantSage - Event-Driven Trading System

A quantitative trading system with production-quality infrastructure for backtesting, risk management, and live trading.

## Honest Status Assessment

| Component | Grade | Status |
|-----------|-------|--------|
| Code Architecture | A+ | Production-quality event-driven design |
| Risk Management | A- | Solid 4-layer protection with circuit breakers |
| Backtesting Engine | A | Realistic simulation with slippage/commissions |
| Dashboard | B+ | Real-time monitoring functional |
| Trading Strategy | D | Basic 1980s technical indicators (Bollinger, RSI) |
| ML/AI Capabilities | F | Zero implementation (empty directories) |
| Stock Trading | F | Not implemented (crypto only via CCXT) |

**Bottom Line**: Excellent infrastructure, but strategy and ML layers need development for competitive edge.

See [docs/HONEST_ASSESSMENT.md](docs/HONEST_ASSESSMENT.md) for detailed analysis and [docs/COMPETITIVE_EDGE_PLAN.md](docs/COMPETITIVE_EDGE_PLAN.md) for the roadmap.

## What Actually Works

- **Cryptocurrency Trading**: Via CCXT (Coinbase) - fully functional
- **Event-Driven Architecture**: Same code runs in backtest, paper, and live modes
- **4-Layer Risk Management**: Position, symbol, portfolio, and system-level protection
- **Backtesting Engine**: Realistic simulation with conservative fills
- **Real-Time Dashboard**: Web interface with live monitoring at http://localhost:8050
- **73 Passing Tests**: Comprehensive test coverage

## What Does NOT Work Yet

- **Stock Trading**: Alpaca integration not implemented (placeholder only)
- **ML/AI Models**: Empty directories despite scikit-learn/xgboost installed
- **Profitable Strategy**: Mean reversion has no proven edge
- **Alternative Data**: No news, sentiment, or on-chain metrics

## Quick Start

### 1. Setup Environment

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python scripts/init_db.py
```

### 2. Run Paper Trading Demo

```bash
# Run paper trading simulation (no real money)
python scripts/paper_trading_demo.py
```

### 3. Run the Dashboard

```bash
# Start real-time monitoring dashboard
python scripts/run_dashboard.py

# Open browser to http://localhost:8050
```

### 4. Run a Backtest

```bash
# Collect historical data
python scripts/collect_data_for_backtest.py

# Run backtest
python scripts/run_backtest.py \
    --strategy mean_reversion \
    --symbols BTC/USD ETH/USD \
    --start 2024-01-01 \
    --end 2024-12-31
```

## Architecture

Event-driven system where the same code runs in all modes:

```
MarketDataEvent → Strategy → SignalEvent → RiskManager → OrderEvent → Executor → FillEvent
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed design.

## Risk Management

4-layer protection system:

1. **Position Risk**: Max 10% per position, stop-loss required
2. **Symbol Risk**: Max 15% aggregate exposure per symbol
3. **Portfolio Risk**: Max 80% invested (20% cash reserve)
4. **System Risk**: Circuit breakers at -5% daily loss or -20% max drawdown

## Testing

```bash
# Run all tests (73 tests)
pytest

# Run with coverage
pytest --cov=src tests/
```

## Documentation

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design
- [HONEST_ASSESSMENT.md](docs/HONEST_ASSESSMENT.md) - Objective evaluation
- [COMPETITIVE_EDGE_PLAN.md](docs/COMPETITIVE_EDGE_PLAN.md) - Enhancement roadmap
- [CLAUDE.md](CLAUDE.md) - Development guide

## Project Structure

```
quantsage/
├── src/
│   ├── core/              # Event system, configuration
│   ├── data/              # Data collection, storage, features
│   ├── strategies/        # Trading strategies (mean reversion)
│   ├── risk/              # 4-layer risk management
│   ├── backtesting/       # Backtest engine
│   ├── portfolio/         # Position management
│   ├── execution/         # Order execution
│   ├── monitoring/        # Dashboard and alerts
│   └── ml/                # ML models (EMPTY - needs implementation)
├── config/                # YAML configuration files
├── scripts/               # Utility scripts
├── tests/                 # Test suite (73 tests)
└── data/                  # Databases and results
```

## Next Steps (From Competitive Edge Plan)

**Phase 1**: Run actual backtests, validate or abandon mean reversion
**Phase 2**: Implement XGBoost + LSTM models
**Phase 3**: Add alternative data (news, sentiment)
**Phase 4**: Build ensemble strategy
**Phase 5**: Production validation

## Disclaimer

This software is for educational purposes. Trading involves substantial risk of loss. The current strategy has NO PROVEN EDGE. Use at your own risk.

## License

MIT License
