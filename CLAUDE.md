# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QuantSage is a **trading system framework** with excellent infrastructure but requiring significant enhancement to be competitive.

### Honest Status Assessment

| Component | Grade | Reality |
|-----------|-------|---------|
| **Architecture** | A+ | Event-driven, production-quality |
| **Risk Management** | A- | 4-layer protection, well-tested |
| **Backtesting** | A | Realistic simulation engine |
| **Dashboard** | B+ | Real-time monitoring |
| **Strategy** | D | Basic 1980s technical indicators |
| **ML/AI** | F | Zero implementation (empty directories) |
| **Stock Trading** | F | Not implemented (crypto only) |

### Current Capabilities
- ✅ Crypto trading via CCXT (Coinbase)
- ✅ Event-driven backtesting
- ✅ Paper trading simulation
- ✅ Real-time dashboard
- ✅ 4-layer risk management
- ✅ 73 passing tests

### What's Missing
- ❌ ML/AI models (directories empty)
- ❌ Stock trading (Alpaca not implemented)
- ❌ Alternative data (news, sentiment, on-chain)
- ❌ Proven profitable strategy
- ❌ No backtest results proving profitability

### Development Roadmap
See `docs/COMPETITIVE_EDGE_PLAN.md` for 15-week enhancement plan.

---

## Development Commands

### Environment Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with API keys
```

### Testing
```bash
pytest                           # Run all 73 tests
pytest tests/test_strategies.py  # Specific file
pytest --cov=src tests/          # With coverage
```

### Backtesting
```bash
python scripts/collect_data_for_backtest.py
python scripts/run_backtest.py --strategy mean_reversion --symbols BTC/USD ETH/USD
```

### Dashboard
```bash
python scripts/run_dashboard.py
# Open http://localhost:8050
```

### Paper Trading
```bash
# Terminal 1
python scripts/run_dashboard.py

# Terminal 2
python scripts/paper_trading_demo.py
```

---

## Architecture

### Event-Driven System (A+ Grade)
The architecture is genuinely excellent - same code runs in backtest and live modes.

```
Data Collector → MarketDataEvent → Strategy → SignalEvent →
RiskManager → OrderEvent → ExecutionEngine → FillEvent →
PortfolioManager → PositionUpdateEvent
```

### Core Components

| Component | Location | Status |
|-----------|----------|--------|
| Event System | `src/core/` | ✅ Complete |
| Data Layer | `src/data/` | ✅ Complete (crypto) |
| Strategies | `src/strategies/` | ⚠️ Basic only |
| Risk Management | `src/risk/` | ✅ Complete |
| Backtesting | `src/backtesting/` | ✅ Complete |
| Portfolio | `src/portfolio/` | ✅ Complete |
| Execution | `src/execution/` | ✅ Complete |
| Dashboard | `src/monitoring/` | ✅ Complete |
| ML/AI | `src/ml/` | ❌ Empty |

### Strategy Layer - NEEDS WORK

**Current**: Only MeanReversionStrategy exists
- Bollinger Bands (1980s indicator)
- RSI (1970s indicator)
- Z-score threshold
- 2% stop-loss (too tight for crypto)

**Problem**: No proven edge, basic retail-level strategy

**Planned Enhancements** (see `docs/COMPETITIVE_EDGE_PLAN.md`):
- XGBoost classification model
- LSTM price prediction
- Momentum strategy
- Ensemble strategy
- Alternative data integration

### ML/AI Layer - EMPTY

```
src/ml/
├── __init__.py      # Empty
├── features/        # Empty directory
├── models/          # Empty directory
└── training/        # Empty directory
```

Libraries installed but NOT USED:
- scikit-learn
- xgboost

---

## File Organization

```
quantsage/
├── src/
│   ├── core/              # Event system, config ✅
│   ├── data/              # Data collection ✅ (crypto only)
│   ├── strategies/        # Trading strategies ⚠️ (basic)
│   ├── risk/              # Risk management ✅
│   ├── backtesting/       # Backtest engine ✅
│   ├── portfolio/         # Portfolio management ✅
│   ├── execution/         # Order execution ✅
│   ├── monitoring/        # Dashboard ✅
│   └── ml/                # ML models ❌ (empty)
├── config/                # YAML configurations
├── scripts/               # Utility scripts
├── tests/                 # 73 tests
├── data/                  # Databases
└── docs/
    ├── ARCHITECTURE.md         # System design
    ├── HONEST_ASSESSMENT.md    # Current state evaluation
    └── COMPETITIVE_EDGE_PLAN.md # 15-week roadmap
```

---

## Key Documentation

| Document | Purpose |
|----------|---------|
| `docs/HONEST_ASSESSMENT.md` | Objective evaluation of capabilities |
| `docs/COMPETITIVE_EDGE_PLAN.md` | 15-week enhancement roadmap |
| `docs/ARCHITECTURE.md` | System architecture details |

---

## Code Patterns

### Event-Driven Pattern
```python
# Good - use events
signal = SignalEvent(...)
self.event_bus.publish(signal)

# Bad - direct coupling
order = risk_manager.validate_signal(signal)  # NEVER DO THIS
```

### New Strategy Template
```python
class MyStrategy(BaseStrategy):
    def on_market_data(self, event: MarketDataEvent) -> Optional[SignalEvent]:
        # Calculate indicators
        # Check conditions
        if conditions_met:
            return self._create_signal(...)
        return None
```

### Database Access (Secure)
```python
# Always parameterized queries
query = "SELECT * FROM positions WHERE symbol = ?"
results = db.execute_query(query, (symbol,))
```

---

## Testing

```bash
# All tests (73 total)
pytest tests/

# By component
pytest tests/test_risk_manager.py    # 20 tests
pytest tests/test_backtest.py        # 21 tests
pytest tests/test_strategies.py      # 20 tests
pytest tests/test_validators.py      # 12 tests
```

---

## Critical Reminders

1. **Strategy is weak** - Don't assume profitability without backtesting
2. **ML is empty** - `src/ml/` directories have no code
3. **Crypto only** - Stock trading (Alpaca) NOT implemented
4. **No proven results** - Zero backtest results exist
5. **Infrastructure is solid** - Architecture is production-quality

---

## Next Development Phase

**Phase 1 (Weeks 1-2)**: Foundation
- Run actual backtests on historical data
- Implement Alpaca stock collector
- Validate or abandon mean reversion strategy

**Phase 2 (Weeks 3-5)**: ML Foundation
- Implement XGBoost classifier
- Add LSTM price prediction
- Enhanced feature engineering

See `docs/COMPETITIVE_EDGE_PLAN.md` for full 15-week plan.
