# QuantSage Dashboard Analysis

## Status: Fixed and Running ✅

The dashboard is now running successfully at **http://127.0.0.1:8050**

---

## Issues Fixed

### 1. SQL Column Name Error (CRITICAL - FIXED)
**Problem**: Dashboard was crashing every 5 seconds with:
```
sqlite3.OperationalError: no such column: direction
```

**Root Cause**: The `_get_signals_data()` method was querying a column called `direction`, but the signals table uses `signal_type` instead.

**Fix Applied**: Changed line 246 in `src/monitoring/dashboard.py`:
```python
# Before (broken)
SELECT timestamp, symbol, direction, price, confidence, strategy_id

# After (fixed)
SELECT timestamp, symbol, signal_type, price, confidence, strategy_id
```

---

## Dashboard Layout Analysis

Based on code inspection (`src/monitoring/dashboard.py`), the dashboard provides:

### Header Section
- Title: "🚀 QuantSage Trading Dashboard"
- Subtitle: "Real-time monitoring of trading system"
- Clean, centered layout with blue theme

### Portfolio Summary Cards (4 metrics)
1. **Portfolio Value** - Total value (cash + positions)
2. **Cash Balance** - Available cash
3. **Total P&L** - Profit/Loss in $ and %
4. **Open Positions** - Count of active positions

### Left Column: Charts & Metrics

#### 📈 Equity Curve Chart
- Line chart showing portfolio value over time
- Filled area under the curve
- Built with Plotly (interactive)
- Currently shows flat line at $100,000 (no trading activity yet)

#### 📉 Performance Metrics Panel
- Total Trades
- Win Rate (% of profitable trades)
- Average Win ($)
- Average Loss ($)
- Profit Factor (ratio of wins to losses)
- Currently all zeros (no trades yet)

### Right Column: Data Tables

#### 💼 Open Positions Table
- Columns: Symbol, Side, Qty, Entry Price, P&L, Strategy
- Currently empty - displays "No open positions"

#### 🎯 Recent Signals Table
- Columns: Time, Symbol, Direction, Price, Confidence
- Shows last 5 signals
- Currently empty - displays "No recent signals"

#### 📝 Recent Trades Table
- Columns: Time, Symbol, Side, Qty, Price, Fee
- Shows last 5 trades
- Currently empty - displays "No recent trades"

### Footer
- Last update timestamp
- Auto-refresh notification (every 5 seconds)

---

## Current State: Empty Dashboard

The dashboard is **running correctly** but displays **no data** because:
- The paper trading database (`data/paper_trading.db`) has:
  - 0 positions
  - 0 trades
  - 0 signals
- No trading activity has been executed yet

---

## Next Steps to Populate Dashboard

### Option 1: Run Paper Trading Demo
```bash
python scripts/paper_trading_demo.py
```
This will generate simulated trading activity and populate the dashboard with real-time data.

### Option 2: Run a Backtest
```bash
# Collect historical data first
python scripts/collect_data_for_backtest.py

# Run backtest
python scripts/run_backtest.py --strategy mean_reversion --symbols BTC/USD ETH/USD
```
Note: Backtests save to separate database files in `data/backtests/`, so you'd need to point the dashboard to a backtest database.

---

## Additional Issues & Improvements Identified

### 1. Hardcoded Initial Capital
**Location**: Line 196, 200 in `src/monitoring/dashboard.py`
```python
cash = 100000.0  # Would come from PortfolioManager
initial_capital = 100000.0
```
**Issue**: These are hardcoded placeholders. In a live system, these should come from:
- PortfolioManager for current cash balance
- Configuration file for initial capital

**Impact**: Medium - Works for demo but needs proper integration

---

### 2. Simplified P&L Calculation
**Location**: Line 189-192 in `_get_portfolio_data()`
```python
total_position_value = sum(
    pos['quantity'] * pos['entry_price']
    for pos in positions
)
```
**Issue**: Uses entry price instead of current market price for position valuation

**Impact**: High - Unrealized P&L will be incorrect

**Fix Needed**: Should fetch current market prices and calculate:
```python
total_position_value = sum(
    pos['quantity'] * current_price[pos['symbol']]
    for pos in positions
)
```

---

### 3. Equity Curve Placeholder Logic
**Location**: Lines 228-236 in `_get_equity_data()`
```python
equity = 100000.0
equity_curve = [{'timestamp': datetime.now() - timedelta(hours=24), 'equity': equity}]

for trade in trades:
    # Simple P&L calculation (would be more sophisticated in live)
    equity_curve.append({
        'timestamp': datetime.fromisoformat(trade[0]),
        'equity': equity  # Not actually updated!
    })
```
**Issue**: The equity value never actually changes in the loop - it just repeats the same value

**Impact**: High - Equity curve will be flat even with trading activity

**Fix Needed**: Should calculate running P&L from trades:
```python
running_pnl = 0
for trade in trades:
    if trade['side'] == 'SELL':
        running_pnl += trade['quantity'] * trade['price']
    else:
        running_pnl -= trade['quantity'] * trade['price']

    equity_curve.append({
        'timestamp': datetime.fromisoformat(trade[0]),
        'equity': initial_capital + running_pnl
    })
```

---

### 4. Database Path Mismatch
**Location**: Line 42 in `TradingDashboard.__init__()`
```python
def __init__(self, db_path: str = 'data/paper_trading.db', ...):
```
**Issue**: Dashboard defaults to `paper_trading.db`, but the main database is `quantsage.db` which has 1500 market data records

**Impact**: Low - Just a configuration issue, but could confuse users

**Suggestion**:
- Either create `paper_trading.db` during init
- Or update QUICKSTART.md to clarify which database to use
- Or add a command-line argument to switch databases

---

### 5. Missing Error Handling for Market Data
**Location**: `_get_equity_data()` and position valuation
**Issue**: No graceful handling if market data is unavailable

**Impact**: Medium - Dashboard could crash if trying to value positions without current prices

---

### 6. No Circuit Breaker Display
**Observation**: The dashboard doesn't show circuit breaker status or risk alerts

**Impact**: Medium - Risk events are tracked in the `risk_events` table but not displayed

**Suggestion**: Add a risk status panel showing:
- Circuit breaker status (active/inactive)
- Current drawdown
- Daily P&L
- Recent risk alerts

---

## UI/UX Observations

### Strengths ✅
1. Clean, professional layout with good color scheme
2. Responsive auto-refresh (every 5 seconds)
3. Well-organized two-column layout
4. Good use of Plotly for interactive charts
5. Color-coded P&L (green/red)
6. Proper table styling with alternating row colors

### Potential Improvements 🔧
1. **Add Loading Indicators**: Show spinner when data is refreshing
2. **Dark Mode**: Add toggle for dark/light theme
3. **Time Range Selector**: Let users choose equity curve time range
4. **Export Functionality**: Export trades/positions to CSV
5. **Alert Notifications**: Visual/audio alerts for new signals or risk events
6. **Symbol Filtering**: Filter views by specific trading pairs
7. **Strategy Performance Comparison**: Compare multiple strategies side-by-side
8. **Mobile Responsiveness**: Current layout may not work well on mobile

---

## Production Readiness

### What's Ready ✅
- Dashboard runs without crashes
- Auto-refresh working
- Database integration functional
- Professional UI design
- Error handling for empty data

### What's Not Ready ❌
- Placeholder calculations (cash, initial capital)
- Equity curve logic incomplete
- Missing current price integration
- No circuit breaker status display
- Development server only (Flask dev server warning)

### For Production Deployment
1. Use production WSGI server (e.g., Gunicorn):
   ```bash
   gunicorn src.monitoring.dashboard:app
   ```
2. Add authentication/authorization
3. Add HTTPS support
4. Implement proper logging and monitoring
5. Add rate limiting and security headers
6. Complete the equity curve calculation logic
7. Integrate real-time price feeds

---

## Testing the Dashboard

### To Verify It's Working:
1. ✅ Dashboard loads at http://127.0.0.1:8050
2. ✅ No SQL errors in console
3. ✅ Auto-refresh every 5 seconds (check network tab)
4. ✅ All sections render (even if empty)

### To See It With Data:
```bash
# Terminal 1: Keep dashboard running
python scripts/run_dashboard.py

# Terminal 2: Run paper trading
python scripts/paper_trading_demo.py
```

Watch the dashboard update in real-time as trades execute!

---

## Summary

**Current Status**: Dashboard is fully functional with one critical fix applied (SQL column name).

**Main Issue**: Dashboard displays correctly but has **no trading data** to show yet. This is expected - you need to run paper trading or load backtest results.

**Critical Fixes Needed** (before production):
1. Fix equity curve calculation logic
2. Integrate real-time price feeds for position valuation
3. Replace hardcoded values with actual PortfolioManager integration
4. Add circuit breaker status display

**Nice-to-Have Improvements**:
1. Risk alerts panel
2. Strategy comparison view
3. Export functionality
4. Better mobile support
5. Dark mode

The dashboard architecture is solid and follows good practices. The main work needed is completing the integration with the actual trading system data sources.
