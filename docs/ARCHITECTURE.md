# QuantSage System Architecture

## Overview

QuantSage uses an **event-driven architecture** where all system components communicate through events. This design ensures the same code runs in both backtesting and live trading modes, eliminating the risk of backtest-to-live discrepancies.

---

## Core Architectural Principles

### 1. Event-Driven Communication

**Why:** Decouples components, enables same code for backtest/live

```
Component A → Publishes Event → Event Bus → Distributes → Component B receives
```

**Benefits:**
- Components don't know about each other
- Easy to add new components
- Replay events for backtesting
- Async support for performance

### 2. Separation of Concerns

**Data Layer** → Fetches and validates data
**Strategy Layer** → Generates trading signals
**Risk Layer** → Validates against risk limits
**Execution Layer** → Places orders
**Portfolio Layer** → Tracks positions and PnL

Each layer has one responsibility and communicates via events.

### 3. Configuration Over Code

**No magic numbers in code**
- All parameters in YAML files
- Easy to test different configurations
- Version control for parameters
- A/B testing support

### 4. Defensive Programming

**Validate everything:**
- Database inputs (parameterized queries)
- User inputs (type checking)
- API responses (schema validation)
- Event data (required fields)

**Fail fast:**
- Catch errors early
- Log detailed error information
- Raise exceptions for invalid states
- Never silently fail

---

## System Components

### 1. Data Layer

**Responsibility:** Fetch, validate, and store market data

```
┌─────────────────────────────────────────────────────┐
│                   DATA LAYER                         │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────┐     ┌──────────────┐             │
│  │   Crypto     │     │    Stock     │             │
│  │  Collector   │     │  Collector   │             │
│  │   (CCXT)     │     │  (Alpaca)    │             │
│  └──────┬───────┘     └──────┬───────┘             │
│         │                    │                      │
│         └────────┬───────────┘                      │
│                  ▼                                   │
│         ┌──────────────┐                            │
│         │  Validators  │                            │
│         └──────┬───────┘                            │
│                ▼                                     │
│         ┌──────────────┐                            │
│         │   Storage    │                            │
│         │  (SQLite)    │                            │
│         └──────────────┘                            │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**Key Files:**
- `src/data/collectors/crypto_collector.py` - CCXT wrapper
- `src/data/collectors/stock_collector.py` - Alpaca API
- `src/data/collectors/unified_collector.py` - Abstract interface
- `src/data/validators.py` - Data validation
- `src/data/storage.py` - Database operations
- `src/data/features.py` - Feature engineering

**Data Flow:**
1. Collector fetches data from exchange/API
2. Validator checks data quality
3. Storage saves to database
4. MarketDataEvent published

**Validation Rules:**
- Price consistency (low ≤ open/close ≤ high)
- No negative values
- Outlier detection (5-sigma rule)
- Timestamp continuity
- Required fields present

---

### 2. Event System

**Responsibility:** Distribute events between components

```
┌─────────────────────────────────────────────────────┐
│                   EVENT BUS                          │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Publishers                    Subscribers          │
│      │                              ▲               │
│      │                              │               │
│      ▼                              │               │
│  ┌──────────────────────────────────────┐          │
│  │         Event Queue                   │          │
│  │  - MarketDataEvent                    │          │
│  │  - SignalEvent                        │          │
│  │  - OrderEvent                         │          │
│  │  - FillEvent                          │          │
│  │  - PositionUpdateEvent                │          │
│  │  - RiskAlertEvent                     │          │
│  └──────────────────────────────────────┘          │
│                                                      │
│  Mode: Backtest                                     │
│  └─ Event History: [all events stored]             │
│                                                      │
│  Mode: Live                                         │
│  └─ Event History: None (real-time only)           │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**Key Files:**
- `src/core/events.py` - Event class definitions
- `src/core/event_bus.py` - Event distribution

**Event Types:**

| Event | Publisher | Subscribers | Purpose |
|-------|-----------|-------------|---------|
| MarketDataEvent | Data Layer | Strategies | New price data |
| SignalEvent | Strategies | Portfolio Mgr | Trading signal |
| OrderEvent | Portfolio Mgr | Risk Mgr, Execution | Order request |
| FillEvent | Execution | Portfolio Mgr | Order filled |
| PositionUpdateEvent | Portfolio Mgr | Monitoring | Position changed |
| RiskAlertEvent | Risk Mgr | Monitoring | Risk violation |
| PerformanceMetricEvent | Portfolio Mgr | Monitoring | Performance update |

**Event Flow Example:**

```
1. Data Collector fetches BTC price
2. Publishes MarketDataEvent(BTC/USD, $50,500)
3. Event Bus distributes to all strategy subscribers
4. Mean Reversion Strategy processes:
   - Calculates indicators
   - Detects oversold condition
   - Publishes SignalEvent(BUY, confidence=0.85)
5. Portfolio Manager receives signal:
   - Calculates position size
   - Creates OrderEvent(BUY 0.1 BTC)
6. Risk Manager validates:
   - Checks position limits
   - Checks portfolio exposure
   - Approves order
7. Execution Engine fills:
   - Simulates slippage
   - Calculates commission
   - Publishes FillEvent
8. Portfolio Manager updates:
   - Creates/updates position
   - Calculates PnL
   - Publishes PositionUpdateEvent
```

---

### 3. Strategy Layer

**Responsibility:** Generate trading signals

```
┌─────────────────────────────────────────────────────┐
│                 STRATEGY LAYER                       │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌───────────────────────────────┐                  │
│  │    BaseStrategy (Abstract)    │                  │
│  │  - on_market_data()           │                  │
│  │  - calculate_position_size()  │                  │
│  │  - validate_config()          │                  │
│  └───────────────┬───────────────┘                  │
│                  │                                   │
│      ┌───────────┼───────────┐                      │
│      │           │           │                      │
│      ▼           ▼           ▼                      │
│  ┌───────┐  ┌───────┐  ┌────────┐                  │
│  │ Mean  │  │Moment-│  │   ML   │                  │
│  │Revers │  │  um   │  │Strategy│                  │
│  └───────┘  └───────┘  └────────┘                  │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**Key Files:**
- `src/strategies/base.py` - Abstract base class
- `src/strategies/mean_reversion.py` - Bollinger Bands strategy
- `src/strategies/momentum.py` - EMA crossover strategy
- `src/strategies/ml_strategy.py` - XGBoost classifier

**Base Strategy Interface:**

```python
class BaseStrategy(ABC):
    def __init__(self, config: Dict, event_bus: EventBus):
        self.config = config
        self.event_bus = event_bus
        self.name = config['name']
        self.symbols = config['symbols']

    @abstractmethod
    def on_market_data(self, event: MarketDataEvent) -> Optional[SignalEvent]:
        """Process market data, return signal if generated"""
        pass

    @abstractmethod
    def calculate_position_size(self, symbol: str, price: float) -> float:
        """Calculate position size based on risk"""
        pass

    def validate_config(self) -> bool:
        """Validate strategy configuration"""
        pass
```

**Strategy Lifecycle:**

```
1. Initialize (load config, subscribe to events)
2. On MarketData Event:
   a. Calculate indicators
   b. Check entry conditions
   c. If met, generate SignalEvent
3. Publish signal to event bus
```

**Mean Reversion Strategy Logic:**

```python
# Entry Conditions (ALL must be true)
BUY_CONDITIONS = [
    price < bollinger_lower_band,
    z_score < -2.0,
    rsi < 40,
    volume > avg_volume * 1.2
]

SELL_CONDITIONS = [
    price > bollinger_upper_band,
    z_score > 2.0,
    rsi > 60,
    volume > avg_volume * 1.2
]

# Exit Conditions (ANY can trigger)
EXIT_CONDITIONS = [
    price_returns_to_middle_band,
    stop_loss_hit (2%),
    take_profit_hit (1.5x distance to middle),
    opposite_signal_generated
]
```

---

### 4. Risk Management Layer

**Responsibility:** Validate all orders against risk limits

```
┌─────────────────────────────────────────────────────┐
│              RISK MANAGEMENT LAYER                   │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Order Request                                       │
│       ↓                                              │
│  ┌─────────────────────────────────────────┐        │
│  │ Layer 1: Position-Level Risk            │        │
│  │ - Max 10% of portfolio per position     │        │
│  │ - Stop-loss: 2% (crypto), 3% (stocks)   │        │
│  │ - Take-profit: 2:1 reward/risk          │        │
│  └─────────────┬───────────────────────────┘        │
│                ↓ PASS                                │
│  ┌─────────────────────────────────────────┐        │
│  │ Layer 2: Symbol-Level Risk              │        │
│  │ - Max 15% exposure per symbol            │        │
│  └─────────────┬───────────────────────────┘        │
│                ↓ PASS                                │
│  ┌─────────────────────────────────────────┐        │
│  │ Layer 3: Portfolio-Level Risk           │        │
│  │ - Max 80% total invested (20% cash)     │        │
│  │ - Correlation limits between positions  │        │
│  └─────────────┬───────────────────────────┘        │
│                ↓ PASS                                │
│  ┌─────────────────────────────────────────┐        │
│  │ Layer 4: System-Level Risk              │        │
│  │ - Daily loss limit: -5%                 │        │
│  │ - Max drawdown: -20%                    │        │
│  └─────────────┬───────────────────────────┘        │
│                ↓ PASS                                │
│  Order Approved ✓                                   │
│                ↓ FAIL                                │
│  Risk Alert Published ✗                             │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**Key Files:**
- `src/portfolio/risk.py` - Risk manager
- `config/risk.yaml` - Risk parameters

**Risk Check Flow:**

```python
def validate_order(order, portfolio_state):
    """Validate order against all risk layers"""

    # Layer 1: Position level
    if not check_position_size(order):
        return False, "Position size too large"

    # Layer 2: Symbol level
    if not check_symbol_exposure(order):
        return False, "Symbol exposure too high"

    # Layer 3: Portfolio level
    if not check_portfolio_exposure(order):
        return False, "Portfolio fully invested"

    # Layer 4: System level
    if not check_daily_loss_limit():
        return False, "Daily loss limit hit"
    if not check_max_drawdown():
        return False, "Max drawdown exceeded"

    return True, "OK"
```

**Position Sizing:**

```python
# Risk-Based Sizing
account_risk = portfolio_equity * 0.01  # Risk 1% per trade
trade_risk = price * stop_loss_pct      # Distance to stop
position_size = (account_risk / trade_risk) * confidence

# Constraints
position_size = min(position_size, portfolio_equity * 0.10)  # Max 10%
position_size = min(position_size, cash_available / price)    # Max affordable
```

---

### 5. Portfolio Management Layer

**Responsibility:** Track positions and manage portfolio

```
┌─────────────────────────────────────────────────────┐
│           PORTFOLIO MANAGEMENT LAYER                 │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Portfolio State:                                    │
│  ├─ Cash: $8,000                                    │
│  ├─ Positions:                                      │
│  │   ├─ BTC/USD: 0.1 BTC @ $50,000 (LONG)          │
│  │   │   └─ Unrealized PnL: +$50                   │
│  │   └─ ETH/USD: 1.0 ETH @ $3,000 (LONG)           │
│  │       └─ Unrealized PnL: +$100                  │
│  ├─ Total Equity: $10,150                          │
│  ├─ Invested: $8,000 (79%)                         │
│  └─ Exposure by Symbol:                            │
│      ├─ BTC/USD: 49%                               │
│      └─ ETH/USD: 30%                               │
│                                                      │
│  Operations:                                        │
│  - Convert signals to orders                        │
│  - Track position lifecycle                         │
│  - Calculate PnL (realized/unrealized)             │
│  - Manage stop-loss and take-profit                │
│  - Coordinate multiple strategies                  │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**Key Files:**
- `src/portfolio/manager.py` - Portfolio manager
- `src/portfolio/position.py` - Position class

**Portfolio Manager Responsibilities:**

1. **Signal to Order Conversion**
```python
def signal_to_order(signal: SignalEvent) -> OrderEvent:
    # Calculate position size
    size = calculate_position_size(signal)

    # Create order
    return OrderEvent(
        symbol=signal.symbol,
        side='BUY' if signal.signal_type == 'BUY' else 'SELL',
        quantity=size,
        order_type='MARKET'
    )
```

2. **Position Tracking**
```python
class Position:
    symbol: str
    side: str  # LONG or SHORT
    quantity: float
    entry_price: float
    entry_time: datetime
    stop_loss: float
    take_profit: float

    def calculate_pnl(self, current_price: float) -> float:
        if self.side == 'LONG':
            return (current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - current_price) * self.quantity
```

3. **PnL Calculation**
```python
def update_portfolio_value(current_prices):
    """Update portfolio value with current prices"""
    unrealized_pnl = 0

    for position in open_positions:
        current_price = current_prices[position.symbol]
        position.pnl_unrealized = position.calculate_pnl(current_price)
        unrealized_pnl += position.pnl_unrealized

    total_equity = cash + sum(p.market_value for p in open_positions)
    return total_equity
```

---

### 6. Execution Layer

**Responsibility:** Execute orders (simulated or live)

```
┌─────────────────────────────────────────────────────┐
│               EXECUTION LAYER                        │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Order Request                                       │
│       ↓                                              │
│  ┌─────────────────────────────────────────┐        │
│  │ Mode Check                               │        │
│  │ - Backtest: Simulated execution         │        │
│  │ - Paper: Simulated with live prices     │        │
│  │ - Live: Real execution via CCXT         │        │
│  └─────────────┬───────────────────────────┘        │
│                ↓                                     │
│  ┌─────────────────────────────────────────┐        │
│  │ Apply Slippage                           │        │
│  │ - Volume-based model                     │        │
│  │ - Base slippage: 0.1%                   │        │
│  │ - Fill price = price ± slippage         │        │
│  └─────────────┬───────────────────────────┘        │
│                ↓                                     │
│  ┌─────────────────────────────────────────┐        │
│  │ Calculate Commission                     │        │
│  │ - Crypto: 0.4-0.6% (Coinbase)           │        │
│  │ - Stocks: $0 (Alpaca)                   │        │
│  └─────────────┬───────────────────────────┘        │
│                ↓                                     │
│  Publish FillEvent                                  │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**Key Files:**
- `src/execution/executor.py` - Order executor
- `src/execution/slippage.py` - Slippage modeling

**Execution Modes:**

1. **Backtest Mode**
```python
def execute_order_backtest(order, market_price):
    # Apply slippage
    fill_price = apply_slippage(market_price, order.side, order.quantity)

    # Calculate commission
    commission = fill_price * order.quantity * 0.006  # 0.6% taker fee

    # Create fill
    return FillEvent(
        order_id=order.id,
        quantity=order.quantity,
        price=fill_price,
        commission=commission
    )
```

2. **Live Mode**
```python
async def execute_order_live(order):
    # Submit to exchange via CCXT
    exchange_order = await exchange.create_market_order(
        symbol=order.symbol,
        side=order.side,
        amount=order.quantity
    )

    # Wait for fill
    while exchange_order['status'] != 'closed':
        await asyncio.sleep(0.1)
        exchange_order = await exchange.fetch_order(exchange_order['id'])

    # Create fill event
    return FillEvent(
        order_id=order.id,
        quantity=exchange_order['filled'],
        price=exchange_order['average'],
        commission=exchange_order['fee']['cost']
    )
```

**Slippage Models:**

```python
class VolumeBasedSlippage:
    """Slippage increases with order size"""

    def apply_slippage(self, price, side, quantity):
        order_value = price * quantity

        # Base slippage + volume impact
        slippage_pct = 0.001 + (order_value / 1000) * 0.00001
        slippage = price * slippage_pct

        # Apply direction
        if side == 'BUY':
            return price + slippage  # Pay more
        else:
            return price - slippage  # Receive less
```

---

### 7. Backtesting Engine

**Responsibility:** Simulate historical trading

```
┌─────────────────────────────────────────────────────┐
│             BACKTESTING ENGINE                       │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Historical Data (2023-01-01 to 2024-01-01)        │
│       ↓                                              │
│  ┌─────────────────────────────────────────┐        │
│  │ For each timestamp:                      │        │
│  │   1. Publish MarketDataEvent            │        │
│  │   2. Strategies generate signals        │        │
│  │   3. Portfolio creates orders           │        │
│  │   4. Risk validates orders              │        │
│  │   5. Execution fills orders             │        │
│  │   6. Portfolio updates positions        │        │
│  │   7. Track performance                  │        │
│  └─────────────┬───────────────────────────┘        │
│                ↓                                     │
│  ┌─────────────────────────────────────────┐        │
│  │ Calculate Metrics                        │        │
│  │ - Total return: 25%                     │        │
│  │ - Sharpe ratio: 1.8                     │        │
│  │ - Max drawdown: -12%                    │        │
│  │ - Win rate: 58%                         │        │
│  │ - Total trades: 156                     │        │
│  └─────────────┬───────────────────────────┘        │
│                ↓                                     │
│  Generate Report & Visualizations                   │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**Key Files:**
- `src/backtesting/engine.py` - Backtesting engine
- `src/backtesting/metrics.py` - Performance metrics
- `src/backtesting/visualizer.py` - Charts and reports

**Backtesting Flow:**

```python
def run_backtest(strategy, start_date, end_date):
    # Initialize
    event_bus = EventBus(mode='backtest')
    portfolio = Portfolio(initial_capital=10000)
    risk_mgr = RiskManager(config)
    executor = SimulatedExecutor()

    # Load historical data
    data = load_historical_data(strategy.symbols, start_date, end_date)

    # Event loop
    for timestamp, bars in data.iterrows():
        # Publish market data
        for symbol, bar in bars.items():
            event = MarketDataEvent(timestamp, symbol, bar)
            event_bus.publish(event)

        # Process events (strategies, portfolio, risk, execution)
        event_bus.process_events()

        # Update portfolio value
        portfolio.update_value(bars)

    # Calculate metrics
    metrics = calculate_metrics(portfolio.equity_curve, portfolio.trades)

    # Generate report
    return BacktestReport(metrics, portfolio, event_bus.event_history)
```

**Performance Metrics:**

```python
class PerformanceMetrics:
    @staticmethod
    def calculate(trades, equity_curve, initial_capital):
        returns = equity_curve.pct_change()

        return {
            'total_return': (equity_curve[-1] / initial_capital) - 1,
            'sharpe_ratio': sharpe_ratio(returns),
            'sortino_ratio': sortino_ratio(returns),
            'max_drawdown': max_drawdown(equity_curve),
            'win_rate': len([t for t in trades if t.pnl > 0]) / len(trades),
            'profit_factor': profit_factor(trades),
            'avg_win': avg([t.pnl for t in trades if t.pnl > 0]),
            'avg_loss': avg([t.pnl for t in trades if t.pnl < 0]),
            'total_trades': len(trades)
        }
```

---

## Data Flow Diagrams

### Complete System Data Flow

```
┌──────────────┐
│   Exchange   │ (Coinbase, Binance, Alpaca)
└──────┬───────┘
       │ REST API / WebSocket
       ↓
┌──────────────────────────────────────────────┐
│           Data Collector                      │
│  - Fetch OHLCV data                          │
│  - Handle rate limits                        │
│  - Retry on errors                           │
└──────┬───────────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────────┐
│           Validators                          │
│  - Check price consistency                   │
│  - Detect outliers                           │
│  - Validate timestamps                       │
└──────┬───────────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────────┐
│           Database (SQLite)                   │
│  - Store market_data                         │
│  - Index for fast queries                    │
└──────┬───────────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────────┐
│           Event Bus                           │
│  - Publish MarketDataEvent                   │
└──────┬───────────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────────┐
│           Strategies                          │
│  - Calculate indicators                      │
│  - Check entry conditions                    │
│  - Generate SignalEvent                      │
└──────┬───────────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────────┐
│           Portfolio Manager                   │
│  - Convert signal to order                   │
│  - Calculate position size                   │
│  - Publish OrderEvent                        │
└──────┬───────────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────────┐
│           Risk Manager                        │
│  - Validate order                            │
│  - Check all risk layers                     │
│  - Approve or reject                         │
└──────┬───────────────────────────────────────┘
       │ (if approved)
       ↓
┌──────────────────────────────────────────────┐
│           Execution Engine                    │
│  - Apply slippage                            │
│  - Calculate commission                      │
│  - Publish FillEvent                         │
└──────┬───────────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────────┐
│           Portfolio Manager                   │
│  - Update position                           │
│  - Calculate PnL                             │
│  - Publish PositionUpdateEvent               │
└──────┬───────────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────────┐
│           Monitoring                          │
│  - Display on dashboard                      │
│  - Send alerts                               │
│  - Log to database                           │
└──────────────────────────────────────────────┘
```

---

## Configuration Architecture

```
config/
├── config.yaml              # Main configuration
│   ├── system               # Mode (backtest/paper/live)
│   ├── database             # Database settings
│   ├── data                 # Data sources & symbols
│   ├── portfolio            # Initial capital
│   └── monitoring           # Dashboard settings
│
├── risk.yaml                # Risk management
│   ├── risk_limits          # All risk parameters
│   ├── transaction_costs    # Fees & slippage
│   └── position_sizing      # Sizing algorithms
│
└── strategies/              # Strategy configs
    ├── mean_reversion_crypto.yaml
    ├── momentum_crypto.yaml
    └── ml_strategy.yaml
```

**Configuration Loading:**

```python
config = ConfigManager('config/config.yaml')
config.load()  # Loads all YAML files
config.validate()  # Validates required fields

# Access nested values
mode = config.get('system.mode')
symbols = config.get_enabled_symbols('CRYPTO')
strategies = config.get_enabled_strategies()
```

---

## Database Schema Details

### Tables and Relationships

```
market_data ────────┐
                    │
                    ↓
signals ──────> strategies
                    │
                    ↓
                positions ←──── orders ←──── trades
                    │
                    ↓
            performance_metrics
                    │
                    ↓
            risk_events
```

### Key Relationships:

- **positions** → **orders**: One position can have multiple orders (entry + exit)
- **orders** → **trades**: One order can result in multiple trades (partial fills)
- **signals** → **positions**: Signals lead to positions (via orders)
- **market_data** → All: Foundation data for everything

---

## Deployment Architecture

### Development Setup

```
Developer Machine
├── quantsage/              # Source code
├── venv/                   # Virtual environment
├── data/quantsage.db       # SQLite database
└── logs/                   # Log files
```

### Production Setup (Future)

```
Production Server
├── Docker Container
│   ├── QuantSage App
│   ├── PostgreSQL + TimescaleDB
│   └── Monitoring Dashboard
│
├── Volume Mounts
│   ├── /data (persistent storage)
│   ├── /logs (log files)
│   └── /config (configurations)
│
└── External Services
    ├── Coinbase API
    ├── Alpaca API
    └── Email SMTP (alerts)
```

---

## Security Architecture

### API Key Management

```
.env file (NOT in git)
├── COINBASE_API_KEY
├── COINBASE_API_SECRET
├── ALPACA_API_KEY
└── ALPACA_API_SECRET

↓ Loaded by python-dotenv

Environment Variables
↓ Used by ConfigManager

Application
```

### Database Security

- ✅ Parameterized queries (no SQL injection)
- ✅ No sensitive data in logs
- ✅ Database file permissions (read/write owner only)

### Network Security

- ✅ HTTPS for all API calls
- ✅ API key encryption in transit
- ✅ Rate limiting to prevent abuse

---

## Error Handling Architecture

### Error Flow

```
Error Occurs
    ↓
Caught by try/except
    ↓
Logged with details
    ↓
┌─────────────┐
│ Critical?   │
└──┬──────┬───┘
   │ Yes  │ No
   ↓      ↓
 Stop   Continue
Trading  with
        Degraded
        Mode
```

### Error Categories:

1. **Data Errors** - Invalid/missing data → Skip bar, log warning
2. **API Errors** - Exchange down → Retry with backoff
3. **Risk Errors** - Limit exceeded → Reject order, alert
4. **System Errors** - Critical failure → Stop trading, alert

---

## Testing Architecture

```
tests/
├── unit/                    # Test individual components
│   ├── test_events.py
│   ├── test_strategies.py
│   ├── test_risk.py
│   └── test_portfolio.py
│
├── integration/             # Test component interactions
│   ├── test_data_pipeline.py
│   ├── test_event_flow.py
│   └── test_backtest.py
│
└── fixtures/                # Test data
    └── sample_market_data.py
```

**Test Pyramid:**

```
    ┌────┐
    │ E2E│ (Few, slow, comprehensive)
    ├────┤
   /  Int  \ (Some, medium speed)
  /────────\
 / Unit Tests \ (Many, fast, focused)
/──────────────\
```

---

## Monitoring Architecture

```
┌──────────────────────────────────────────────┐
│           Monitoring Dashboard                │
│  (Plotly Dash on http://localhost:8050)     │
├──────────────────────────────────────────────┤
│                                              │
│  ┌────────────────┐  ┌─────────────────┐   │
│  │ Equity Curve   │  │ Open Positions  │   │
│  └────────────────┘  └─────────────────┘   │
│                                              │
│  ┌────────────────┐  ┌─────────────────┐   │
│  │ Recent Signals │  │ Risk Metrics    │   │
│  └────────────────┘  └─────────────────┘   │
│                                              │
│  ┌────────────────┐  ┌─────────────────┐   │
│  │ Performance    │  │ System Health   │   │
│  └────────────────┘  └─────────────────┘   │
│                                              │
└──────────────────────────────────────────────┘
        ↑
        │ WebSocket updates
        │
┌───────┴──────────────────────────────────────┐
│           Event Bus                           │
│  - PositionUpdateEvent                       │
│  - PerformanceMetricEvent                    │
│  - RiskAlertEvent                            │
└──────────────────────────────────────────────┘
```

---

**Last Updated:** 2026-01-04
**Version:** 1.0
**Status:** Foundation Complete
