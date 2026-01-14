# QuantSage - Complete Project Plan

## Project Overview

**QuantSage** is a production-ready quantitative trading system for cryptocurrencies and stocks. It uses event-driven architecture, machine learning, and comprehensive risk management to generate and execute trading signals.

**Current Status:** Week 6-7 Complete (Live Trading & Monitoring) - 87% Complete
**Timeline:** 6-8 weeks total
**Repository:** `/Users/jkgurung/workspace/quantsage`

---

## Table of Contents

1. [Project Goals](#project-goals)
2. [Architecture](#architecture)
3. [Technology Stack](#technology-stack)
4. [Development Timeline](#development-timeline)
5. [Component Details](#component-details)
6. [Testing Strategy](#testing-strategy)
7. [Deployment Plan](#deployment-plan)
8. [Migration from Old System](#migration-from-old-system)

---

## Project Goals

### Primary Objective
Build a **validated, risk-managed trading system** that can:
- Backtest strategies on historical data
- Paper trade for validation
- Execute live trades (after thorough validation)

### Key Requirements
1. **Multi-Asset Support** - Trade both crypto (via CCXT) and stocks (via Alpaca)
2. **Event-Driven Architecture** - Same code runs in backtest and live modes
3. **Risk Management** - Multi-layer protection against catastrophic losses
4. **Backtesting First** - Never deploy untested strategies
5. **Realistic Modeling** - Include transaction costs, slippage, market hours

### Success Criteria
- Sharpe Ratio > 1.5 in backtests
- Max Drawdown < -15%
- Win Rate > 50%
- System runs reliably for months
- Risk controls prevent large losses

---

## Architecture

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA LAYER                                │
│  CRYPTO: CCXT (Coinbase, Binance, etc.)                     │
│  STOCKS: Alpaca API / IBKR / Polygon                         │
│            ↓                                                 │
│  Unified Data Interface → SQLite → Validators               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                   EVENT BUS (asyncio)                        │
│  Events: MarketData, Signal, Order, Fill, RiskAlert         │
└─────────────────────────────────────────────────────────────┘
                          ↓
        ┌─────────────────┴─────────────────┐
        ↓                 ↓                  ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  STRATEGIES  │  │  PORTFOLIO   │  │  EXECUTION   │
│              │  │  & RISK MGR  │  │   ENGINE     │
├──────────────┤  ├──────────────┤  ├──────────────┤
│• Mean Rev    │  │• Position    │  │• Order Exec  │
│• Momentum    │  │  Sizing      │  │• Slippage    │
│• ML (XGBoost)│  │• Stop-Loss   │  │  Modeling    │
│              │  │• Drawdown    │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              BACKTESTING ENGINE (OFFLINE)                    │
│  Historical Replay → Strategy → Performance Metrics          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│         MONITORING (Dashboard, Alerts, Analytics)            │
└─────────────────────────────────────────────────────────────┘
```

### Event Flow

```
Market Data Arrives
    ↓
MarketDataEvent Published
    ↓
Strategies Process → Generate Signals
    ↓
SignalEvent Published
    ↓
Portfolio Manager → Creates Orders
    ↓
Risk Manager → Validates Orders
    ↓
OrderEvent Published (if approved)
    ↓
Execution Engine → Fills Orders
    ↓
FillEvent Published
    ↓
Portfolio Updated
```

### Key Architectural Decisions

#### 1. Event-Driven vs. Batch Processing
**Decision:** Event-driven
**Rationale:**
- Same code runs in backtest and live modes
- Real-time trading requires event-driven
- Better testability
- Clean separation of concerns

#### 2. SQLite vs. PostgreSQL
**Decision:** Start with SQLite, migrate to PostgreSQL later
**Rationale:**
- SQLite: Easier setup, good for development
- PostgreSQL: Better for production (concurrency, performance)
- Migration path designed from day one

#### 3. XGBoost vs. LSTM for ML
**Decision:** XGBoost
**Rationale:**
- Better for tabular financial data
- Faster training
- Feature importance analysis
- Less prone to overfitting
- Easier to debug

#### 4. Synchronous vs. Asynchronous
**Decision:** Support both
**Rationale:**
- Sync for backtesting (simpler)
- Async for live trading (better performance)
- EventBus supports both modes

---

## Technology Stack

### Core Technologies

**Language:** Python 3.9+

**Database:**
- Development: SQLite 3
- Production: PostgreSQL 14+ with TimescaleDB extension

**Data Collection:**
- Crypto: CCXT 4.1.0 (Coinbase, Binance, Kraken, etc.)
- Stocks: Alpaca API (commission-free trading + data)

**Machine Learning:**
- scikit-learn 1.3.0
- XGBoost 2.0.0
- pandas 2.0.3, numpy 1.24.3

**Configuration:**
- OmegaConf 2.3.0 (YAML management)
- python-dotenv 1.0.0 (environment variables)

**Visualization:**
- Plotly 5.15.0
- Dash 2.14.0 (web dashboard)
- matplotlib 3.7.2

**Testing:**
- pytest 7.4.3
- pytest-asyncio 0.21.1
- pytest-cov 4.1.0

### Dependencies

See `requirements.txt` for complete list.

---

## Development Timeline

### Week 1: Core Infrastructure ✅ COMPLETED

**Goals:** Build foundation components
**Status:** ✅ All tests passing

**Deliverables:**
- [x] Project structure
- [x] Database schema (8 tables)
- [x] Secure storage layer (parameterized queries)
- [x] Event system (7 event types)
- [x] Configuration management (YAML-based)
- [x] Foundation tests

**Key Files:**
- `src/data/schema.sql` - Database schema
- `src/data/storage.py` - Secure database manager
- `src/core/events.py` - Event classes
- `src/core/event_bus.py` - Event distribution
- `src/core/config.py` - Configuration manager
- `config/*.yaml` - Configuration files

---

### Week 2: Data Collection & Validation ✅ COMPLETED

**Goals:** Build data pipeline with proper validation
**Status:** 100% Complete

**Tasks:**
- [x] Implement CCXT wrapper for crypto exchanges
  - File: `src/data/collectors/crypto_collector.py`
  - Features: Rate limiting, retry logic, error handling
  - Support: Coinbase (primary), Binance, Kraken

- [x] Create unified data collector interface
  - File: `src/data/collectors/unified_collector.py`
  - Abstract class for multi-asset support
  - Handles both crypto and stocks

- [x] Implement data validators
  - File: `src/data/validators.py`
  - Validate: Price consistency, outliers, gaps, data types
  - Clean: Handle missing data, interpolate gaps

- [x] Fix feature engineering (data leakage)
  - File: `src/data/features.py`
  - **CRITICAL FIX:** Proper train/test split in normalization
  - Fit scaler on training data only
  - Technical indicators: RSI, MACD, Bollinger Bands, etc.

- [x] Create data collection scripts
  - File: `scripts/collect_historical_data.py`
  - Fetch 1-2 years of historical data
  - Store in database with validation

**Testing:**
- Unit tests for collectors
- Integration tests for data pipeline
- Validate data quality metrics

**Deliverable:** Working data collection pipeline with clean, validated data

---

### Week 3: Strategy Framework ✅ COMPLETED

**Goals:** Build flexible strategy system
**Status:** 100% Complete

**Tasks:**
- [x] Implement BaseStrategy abstract class
  - File: `src/strategies/base.py`
  - Interface: `on_market_data()`, `calculate_position_size()`
  - State management, configuration validation
  - Ensures same code runs in backtest/live

- [x] Implement Mean Reversion Strategy (Priority 1)
  - File: `src/strategies/mean_reversion.py`
  - Logic: Bollinger Bands + Z-score + RSI filter
  - Entry: Price < lower band AND z-score < -2 AND RSI < 40
  - Exit: Price returns to middle band OR stop-loss/take-profit
  - Config: `config/strategies/mean_reversion_crypto.yaml`

- [x] Create strategy testing framework
  - File: `tests/test_strategies.py`
  - Test signal generation
  - Test position sizing
  - Test state management

- [ ] Implement Momentum Strategy (Priority 2)
  - File: `src/strategies/momentum.py`
  - Logic: EMA crossover + ADX filter + volume confirmation
  - Trailing stop using ATR

**Testing:**
- Unit tests for each strategy
- Test signal generation on synthetic data
- Validate position sizing logic

**Deliverable:** Working mean reversion strategy with tests

---

### Week 4: Risk Management ✅ COMPLETED

**Goals:** Multi-layer risk protection
**Status:** 100% Complete

**Tasks:**
- [x] Implement RiskManager
  - File: `src/portfolio/risk.py`
  - **Layer 1:** Position-level (10% max per position)
  - **Layer 2:** Symbol-level (15% max per symbol)
  - **Layer 3:** Portfolio-level (80% max invested, 20% cash)
  - **Layer 4:** System-level (-5% daily loss, -20% max drawdown)

- [x] Implement position sizing algorithms
  - Risk-based sizing: Size = (Account Risk / Trade Risk) × Confidence
  - Volatility-adjusted sizing
  - Kelly Criterion (optional)

- [x] Implement stop-loss and take-profit logic
  - Fixed percentage stops
  - Trailing stops using ATR
  - Time-based exits

- [x] Create risk validation tests
  - Test each risk layer
  - Test edge cases (max drawdown, daily loss limit)
  - Test position sizing calculations

**Testing:**
- Unit tests for risk checks
- Integration tests with portfolio
- Stress tests (simulated losses)

**Deliverable:** Comprehensive risk management system

---

### Week 5: Backtesting Engine ✅ COMPLETED

**Goals:** Event-driven backtesting with realistic modeling
**Status:** 100% Complete (21/21 tests passing)

**Tasks:**
- [x] Implement BacktestEngine
  - File: `src/backtesting/engine.py`
  - Event-driven (not vectorized)
  - Historical data replay
  - Order filling simulation

- [x] Implement performance metrics
  - File: `src/backtesting/metrics.py`
  - Calculate: Sharpe, Sortino, Max Drawdown, Win Rate, Profit Factor
  - Trade analysis: Average win, average loss, holding periods

- [x] Implement slippage modeling
  - File: `src/execution/slippage.py`
  - Volume-based slippage
  - Realistic fill prices

- [x] Create backtest visualizations
  - File: `src/backtesting/visualizer.py`
  - Equity curve, drawdown chart
  - Trade distribution
  - Returns histogram

- [x] Run strategy validation
  - Backtest mean reversion on 1-2 years data
  - Generate performance report
  - Validate metrics meet targets

**Testing:**
- Test backtesting engine accuracy
- Compare with known results
- Validate no look-ahead bias

**Deliverable:** Validated backtesting engine with strategy results

---

### Week 6-7: Live Trading & Monitoring ✅ COMPLETED

**Goals:** Real-time monitoring and paper trading validation
**Status:** 100% Complete (Dashboard operational, paper trading verified)

**Tasks:**
- [x] Implement real-time web dashboard
  - File: `src/monitoring/dashboard.py`
  - Real-time portfolio monitoring
  - Interactive equity curve
  - Position and trade tables
  - Performance metrics display
  - Auto-refresh every 5 seconds

- [x] Implement paper trading demo
  - File: `scripts/paper_trading_demo.py`
  - Simulated market data
  - Full trading loop integration
  - Real-time database updates
  - Works with dashboard

- [x] Create database initialization
  - File: `scripts/init_db.py`
  - Schema creation
  - Validation

- [x] Create dashboard launcher
  - File: `scripts/run_dashboard.py`
  - Command-line options
  - Port configuration

- [x] Create user documentation
  - QUICKSTART.md - 5-minute setup guide
  - VERIFICATION_RESULTS.md - Testing verification
  - DASHBOARD_ANALYSIS.md - Technical details

**Testing:**
- All scripts verified and tested
- QuickStart instructions validated
- Dashboard errors fixed
- Paper trading integration confirmed

**Deliverable:** Operational monitoring dashboard + paper trading demo

---

---

### Week 8: Production Hardening ⏳ IN PROGRESS

**Goals:** Prepare for live deployment
**Status:** Partial - Dashboard integration and security audit pending

**Tasks:**
- [x] Dashboard implementation (with known limitations - see DASHBOARD_ANALYSIS.md)

- [ ] Complete dashboard integration
  - Replace placeholder calculations
  - Integrate real-time price feeds
  - Add circuit breaker status display
  - Add risk alerts panel

- [ ] Implement ML strategy (optional)
  - File: `src/strategies/ml_strategy.py`
  - XGBoost classifier
  - Walk-forward validation
  - Feature importance tracking

- [ ] Security audit
  - Review all API key handling
  - Check for vulnerabilities
  - Secure credential storage

- [ ] Error recovery mechanisms
  - Graceful degradation
  - Automatic retry logic
  - State persistence

- [ ] Documentation
  - API documentation
  - Deployment guide
  - User manual
  - Architecture diagrams

- [ ] Final integration tests
  - End-to-end system test
  - Load testing
  - Failure recovery tests

**Testing:**
- Full system integration tests
- Security testing
- Performance testing

**Deliverable:** Production-ready system

---

## Component Details

### 1. Database Schema

**File:** `src/data/schema.sql`

**Tables:**

```sql
market_data        -- OHLCV data for all assets
positions          -- Position tracking
orders             -- Order management
trades             -- Trade execution records
signals            -- Strategy signals
backtest_results   -- Backtest performance
risk_events        -- Risk violations
performance_metrics -- System metrics
```

**Key Features:**
- Multi-asset support via `asset_type` field
- Proper indexes for fast queries
- JSON metadata for flexibility
- Foreign key relationships

### 2. Event System

**File:** `src/core/events.py`

**Event Types:**
1. `MarketDataEvent` - Price/volume updates
2. `SignalEvent` - Trading signals from strategies
3. `OrderEvent` - Order requests
4. `FillEvent` - Order executions
5. `PositionUpdateEvent` - Position changes
6. `RiskAlertEvent` - Risk violations
7. `PerformanceMetricEvent` - Performance metrics
8. `SystemEvent` - System-level events

**Event Bus:** `src/core/event_bus.py`
- Pub/sub pattern
- Event history (for backtesting)
- Async support

### 3. Configuration System

**File:** `src/core/config.py`

**Configuration Files:**
- `config/config.yaml` - Main system configuration
- `config/risk.yaml` - Risk management parameters
- `config/strategies/*.yaml` - Strategy configurations

**Features:**
- YAML-based (human-readable)
- Environment variable substitution
- Validation
- Hot-reload support (future)

### 4. Risk Management

**File:** `src/portfolio/risk.py`

**Risk Layers:**

**Layer 1: Position-level**
- Max position size: 10% of portfolio
- Stop-loss: 2% (crypto), 3% (stocks)
- Take-profit: 2:1 reward/risk ratio

**Layer 2: Symbol-level**
- Max exposure per symbol: 15%

**Layer 3: Portfolio-level**
- Max total exposure: 80% (20% cash reserve)
- Correlation limits between positions

**Layer 4: System-level**
- Daily loss limit: -5% → Stop trading for day
- Max drawdown: -20% → Halt all trading

### 5. Strategy Framework

**Base Class:** `src/strategies/base.py`

**Interface:**
```python
class BaseStrategy(ABC):
    @abstractmethod
    def on_market_data(self, event: MarketDataEvent) -> Optional[SignalEvent]:
        """Process market data, return signal"""
        pass

    @abstractmethod
    def calculate_position_size(self, symbol: str, price: float) -> float:
        """Calculate position size based on risk"""
        pass
```

**Strategies:**
1. **Mean Reversion** (Priority 1)
   - Bollinger Bands + Z-score + RSI
   - Best for ranging markets
   - Clear statistical edge

2. **Momentum** (Priority 2)
   - EMA crossover + ADX filter
   - Best for trending markets
   - Complements mean reversion

3. **ML Strategy** (Priority 3)
   - XGBoost classifier
   - Walk-forward validation
   - Feature importance

### 6. Backtesting Engine

**File:** `src/backtesting/engine.py`

**Features:**
- Event-driven (same code as live)
- Realistic order filling
- Transaction costs modeling
- Slippage modeling
- No look-ahead bias

**Performance Metrics:**
- Total return
- Sharpe ratio
- Sortino ratio
- Max drawdown
- Win rate
- Profit factor
- Average holding period

---

## Testing Strategy

### Unit Tests

**Coverage Target:** > 80%

**Test Files:**
- `tests/unit/test_events.py`
- `tests/unit/test_strategies.py`
- `tests/unit/test_risk.py`
- `tests/unit/test_portfolio.py`

**What to Test:**
- Each component in isolation
- Edge cases
- Error handling
- Data validation

### Integration Tests

**Test Files:**
- `tests/integration/test_data_pipeline.py`
- `tests/integration/test_backtest.py`
- `tests/integration/test_execution.py`

**What to Test:**
- Component interactions
- Event flow
- End-to-end workflows

### Backtest Validation

**Requirements:**
- Test on 3+ years of data
- Multiple market regimes (bull, bear, sideways)
- Validate metrics:
  - Sharpe ratio > 1.5
  - Max drawdown < -15%
  - Win rate > 50%

### Paper Trading

**Duration:** Minimum 2-4 weeks

**What to Validate:**
- Real-time execution
- Risk controls work
- Order accuracy
- System stability

---

## Deployment Plan

### Development Environment

```bash
# 1. Clone repository
git clone <repo-url>
cd quantsage

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with API keys

# 5. Initialize database
python scripts/init_db.py

# 6. Run tests
pytest tests/

# 7. Run backtest
python scripts/run_backtest.py --strategy mean_reversion

# 8. Start paper trading
python scripts/paper_trading.py

# 9. View dashboard (optional)
python -m src.monitoring.dashboard
# Open http://localhost:8050
```

### Production Deployment (Future)

**Option 1: Docker**
```bash
docker-compose up -d
```

**Option 2: Systemd Service**
```bash
sudo systemctl start quantsage
sudo systemctl enable quantsage
```

### Going Live Checklist

- [ ] All strategies pass 6-month backtest (Sharpe > 1.0)
- [ ] Paper trading successful for 4+ weeks
- [ ] Risk limits tested and validated
- [ ] Monitoring alerts working
- [ ] Database backup configured
- [ ] Error recovery tested
- [ ] Start with small capital ($500-1000)
- [ ] Monitor daily for first month

---

## Migration from Old System

### What to Salvage from CryptoSage

**70% Reusable:**
- `data_collector.py` - Coinbase API integration
  - Keep: JWT generation, API calls
  - Fix: Add CCXT wrapper, parameterized queries
  - Enhance: Rate limiting, error handling

**50% Reusable:**
- `feature_engineering.py` - Technical indicators
  - Keep: Indicator calculations (RSI, MACD, etc.)
  - Fix: Data leakage in normalization
  - Enhance: Proper train/test split

**100% Reusable:**
- `logger_config.py` - Logging setup
  - Keep as-is

**30% Reusable:**
- `database_manager.py` - Database operations
  - Keep: Basic connection logic
  - Replace: SQLite → parameterized queries
  - Fix: SQL injection vulnerabilities

### What to Rebuild

❌ **Complete Rebuild:**
- `signal_generator.py` - Strategy framework
- `ml_predictor.py` - ML models
- `lstm_predictor.py` - ML models
- `monitor_signals.py` - Main orchestrator

**Why?** These have fundamental architectural issues that are easier to rebuild than fix.

### Migration Steps

1. **Week 1** ✅ - Build new foundation
2. **Week 2** - Copy and fix `data_collector.py`
3. **Week 3** - Copy and fix `feature_engineering.py`
4. **Week 4-8** - Build new components
5. **Final** - Retire old system after validation

---

## Critical Success Factors

1. **Backtest Before Live** - Never deploy untested strategies
2. **Risk Management First** - Protect capital above all
3. **Start Simple** - One strategy, few symbols
4. **Validate Constantly** - Monitor performance metrics
5. **Iterate Carefully** - Make changes based on data
6. **Stay Disciplined** - Follow the system rules

---

## Known Issues & Limitations

### Current Limitations

1. **SQLite** - Using SQLite for development, will migrate to PostgreSQL for production
2. **No Live Trading Yet** - System is backtest/paper trading only
3. **Limited Strategies** - Starting with mean reversion, will add more
4. **No Options/Futures** - Only spot crypto and stocks for now

### Future Enhancements

1. **PostgreSQL Migration** - Better concurrency and performance
2. **More Strategies** - Add momentum, ML, arbitrage strategies
3. **Options Support** - Add options trading capabilities
4. **Multi-Exchange** - Trade on multiple exchanges simultaneously
5. **Advanced ML** - Ensemble methods, deep learning
6. **Social Trading** - Follow other traders' signals

---

## Support & Resources

### Documentation
- `/docs/PROGRESS.md` - Development progress
- `/docs/ARCHITECTURE.md` - System architecture (to be created)
- `/docs/API.md` - API documentation (to be created)

### Key Files to Understand
1. `src/core/events.py` - Event system
2. `src/core/config.py` - Configuration
3. `src/data/storage.py` - Database operations
4. `src/strategies/base.py` - Strategy interface
5. `config/*.yaml` - All configuration

### Getting Help
- Check `/docs/` directory for documentation
- Review test files for usage examples
- See `scripts/` for example workflows

---

**Last Updated:** 2026-01-12
**Version:** 1.7 (Week 6-7 Complete)
**Status:** Live Trading & Monitoring Complete, Starting Week 8
