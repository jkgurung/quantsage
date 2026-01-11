-- QuantSage Database Schema (SQLite)
-- Multi-asset trading system supporting crypto and stocks

-- Market Data Table
CREATE TABLE IF NOT EXISTS market_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    asset_type TEXT NOT NULL CHECK (asset_type IN ('CRYPTO', 'STOCK', 'ETF', 'FOREX')),
    timestamp TEXT NOT NULL,  -- ISO 8601 format
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    quote_volume REAL,
    num_trades INTEGER,
    data_source TEXT NOT NULL,  -- 'coinbase', 'binance', 'alpaca', etc.
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, timestamp, data_source)
);

CREATE INDEX IF NOT EXISTS idx_market_data_symbol_time ON market_data(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_market_data_asset_type ON market_data(asset_type, timestamp DESC);

-- Positions Table
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('LONG', 'SHORT')),
    quantity REAL NOT NULL,
    entry_price REAL NOT NULL,
    entry_time TEXT NOT NULL,
    exit_price REAL,
    exit_time TEXT,
    stop_loss REAL,
    take_profit REAL,
    status TEXT NOT NULL CHECK (status IN ('OPEN', 'CLOSED', 'PARTIAL')) DEFAULT 'OPEN',
    pnl_realized REAL DEFAULT 0,
    pnl_unrealized REAL DEFAULT 0,
    strategy_id TEXT NOT NULL,
    metadata TEXT,  -- JSON string
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_positions_symbol_status ON positions(symbol, status);
CREATE INDEX IF NOT EXISTS idx_positions_strategy ON positions(strategy_id);

-- Orders Table
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT UNIQUE NOT NULL,  -- Exchange order ID
    symbol TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    order_type TEXT NOT NULL CHECK (order_type IN ('MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT')),
    quantity REAL NOT NULL,
    price REAL,
    stop_price REAL,
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'OPEN', 'FILLED', 'PARTIAL', 'CANCELLED', 'REJECTED')) DEFAULT 'PENDING',
    filled_quantity REAL DEFAULT 0,
    avg_fill_price REAL,
    commission REAL DEFAULT 0,
    position_id INTEGER,
    strategy_id TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (position_id) REFERENCES positions(id)
);

CREATE INDEX IF NOT EXISTS idx_orders_symbol_status ON orders(symbol, status);
CREATE INDEX IF NOT EXISTS idx_orders_position ON orders(position_id);

-- Trades (Fills) Table
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT UNIQUE NOT NULL,
    order_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    commission REAL NOT NULL,
    commission_asset TEXT,
    timestamp TEXT NOT NULL,
    metadata TEXT,  -- JSON string
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE INDEX IF NOT EXISTS idx_trades_order ON trades(order_id);
CREATE INDEX IF NOT EXISTS idx_trades_symbol_time ON trades(symbol, timestamp DESC);

-- Signals Table
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    signal_type TEXT NOT NULL CHECK (signal_type IN ('BUY', 'SELL', 'HOLD')),
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    price REAL NOT NULL,
    metadata TEXT,  -- JSON string with strategy-specific details
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, timestamp, strategy_id)
);

CREATE INDEX IF NOT EXISTS idx_signals_symbol_time ON signals(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signals_strategy ON signals(strategy_id);

-- Backtest Results Table
CREATE TABLE IF NOT EXISTS backtest_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backtest_id TEXT UNIQUE NOT NULL,
    strategy_id TEXT NOT NULL,
    symbols TEXT NOT NULL,  -- JSON array
    asset_type TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    initial_capital REAL NOT NULL,
    final_capital REAL NOT NULL,
    total_return REAL NOT NULL,
    sharpe_ratio REAL,
    sortino_ratio REAL,
    max_drawdown REAL,
    win_rate REAL,
    total_trades INTEGER,
    config TEXT NOT NULL,  -- JSON string
    results TEXT NOT NULL,  -- JSON string with detailed results
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_backtest_strategy ON backtest_results(strategy_id);

-- Risk Events Table
CREATE TABLE IF NOT EXISTS risk_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    symbol TEXT,
    asset_type TEXT,
    strategy_id TEXT,
    description TEXT NOT NULL,
    metadata TEXT,  -- JSON string
    resolved INTEGER DEFAULT 0,  -- 0 = false, 1 = true
    resolved_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_risk_events_time ON risk_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_risk_events_severity ON risk_events(severity, resolved);

-- Performance Metrics Table
CREATE TABLE IF NOT EXISTS performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    strategy_id TEXT,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    timeframe TEXT,  -- '1d', '7d', '30d', 'all'
    metadata TEXT,  -- JSON string
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_perf_strategy_metric ON performance_metrics(strategy_id, metric_name, timestamp DESC);
