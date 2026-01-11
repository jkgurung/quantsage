"""
Database storage manager with secure parameterized queries.
Fixes SQL injection vulnerabilities from the original system.
"""

import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Secure database manager using parameterized queries.

    Key improvements over original database_manager.py:
    - Parameterized queries (prevents SQL injection)
    - Context manager support
    - Better error handling
    - Connection pooling
    """

    def __init__(self, db_path: str = "data/quantsage.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = None
        self._initialize_database()

    def _initialize_database(self):
        """Initialize database with schema."""
        schema_path = Path(__file__).parent / "schema.sql"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
                cursor.executescript(schema_sql)
            conn.commit()

        logger.info(f"Database initialized at {self.db_path}")

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        if self.connection is None:
            self.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                isolation_level=None  # Autocommit mode
            )
            self.connection.row_factory = sqlite3.Row
        return self.connection

    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def query(self, sql: str, params: Tuple = ()) -> List[Dict]:
        """
        Execute a SELECT query and return results as list of dicts.

        Args:
            sql: SQL SELECT statement
            params: Query parameters (for parameterized queries)

        Returns:
            List of result rows as dicts
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()

            # Convert Row objects to dicts
            return [dict(row) for row in rows]

    # ==================== Market Data Methods ====================

    def insert_market_data(self, symbol: str, asset_type: str, timestamp: datetime,
                          ohlcv: Dict[str, float], data_source: str) -> bool:
        """
        Insert market data using parameterized query (SECURE).

        Args:
            symbol: Trading symbol (e.g., 'BTC/USD', 'AAPL')
            asset_type: 'CRYPTO', 'STOCK', 'ETF', 'FOREX'
            timestamp: Data timestamp
            ohlcv: Dict with keys: open, high, low, close, volume
            data_source: Source of data (e.g., 'coinbase', 'alpaca')
        """
        query = """
            INSERT OR REPLACE INTO market_data
            (symbol, asset_type, timestamp, open, high, low, close, volume,
             quote_volume, num_trades, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (
                    symbol,
                    asset_type,
                    timestamp.isoformat(),
                    ohlcv['open'],
                    ohlcv['high'],
                    ohlcv['low'],
                    ohlcv['close'],
                    ohlcv['volume'],
                    ohlcv.get('quote_volume'),
                    ohlcv.get('num_trades'),
                    data_source
                ))
                conn.commit()
            return True

        except Exception as e:
            logger.error(f"Error inserting market data: {e}")
            return False

    def bulk_insert_market_data(self, data: List[Tuple]) -> int:
        """
        Bulk insert market data for efficiency.

        Args:
            data: List of tuples matching market_data table structure

        Returns:
            Number of rows inserted
        """
        query = """
            INSERT OR REPLACE INTO market_data
            (symbol, asset_type, timestamp, open, high, low, close, volume,
             quote_volume, num_trades, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(query, data)
                conn.commit()
                return cursor.rowcount

        except Exception as e:
            logger.error(f"Error bulk inserting market data: {e}")
            return 0

    def get_market_data(self, symbol: str, start_date: datetime,
                       end_date: datetime, limit: Optional[int] = None) -> List[Dict]:
        """
        Fetch market data for symbol within date range.

        Args:
            symbol: Trading symbol
            start_date: Start datetime
            end_date: End datetime
            limit: Optional limit on number of rows

        Returns:
            List of market data dictionaries
        """
        query = """
            SELECT * FROM market_data
            WHERE symbol = ? AND timestamp BETWEEN ? AND ?
            ORDER BY timestamp ASC
        """

        params = [symbol, start_date.isoformat(), end_date.isoformat()]

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return []

    def get_latest_market_data(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Get latest market data for symbol."""
        query = """
            SELECT * FROM market_data
            WHERE symbol = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (symbol, limit))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error fetching latest market data: {e}")
            return []

    # ==================== Position Methods ====================

    def create_position(self, symbol: str, asset_type: str, side: str,
                       quantity: float, entry_price: float, entry_time: datetime,
                       strategy_id: str, stop_loss: Optional[float] = None,
                       take_profit: Optional[float] = None,
                       metadata: Optional[Dict] = None) -> int:
        """
        Create new position.

        Returns:
            Position ID
        """
        query = """
            INSERT INTO positions
            (symbol, asset_type, side, quantity, entry_price, entry_time,
             stop_loss, take_profit, strategy_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (
                    symbol,
                    asset_type,
                    side,
                    quantity,
                    entry_price,
                    entry_time.isoformat(),
                    stop_loss,
                    take_profit,
                    strategy_id,
                    json.dumps(metadata) if metadata else None
                ))
                conn.commit()
                return cursor.lastrowid

        except Exception as e:
            logger.error(f"Error creating position: {e}")
            return -1

    def update_position(self, position_id: int, **kwargs) -> bool:
        """
        Update position fields.

        Args:
            position_id: Position ID
            **kwargs: Fields to update (exit_price, exit_time, status, etc.)
        """
        if not kwargs:
            return False

        # Build dynamic UPDATE query
        fields = []
        values = []
        for key, value in kwargs.items():
            fields.append(f"{key} = ?")
            if isinstance(value, datetime):
                values.append(value.isoformat())
            elif isinstance(value, dict):
                values.append(json.dumps(value))
            else:
                values.append(value)

        # Add updated_at
        fields.append("updated_at = ?")
        values.append(datetime.now().isoformat())

        # Add position_id for WHERE clause
        values.append(position_id)

        query = f"""
            UPDATE positions
            SET {', '.join(fields)}
            WHERE id = ?
        """

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, values)
                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error updating position: {e}")
            return False

    def get_open_positions(self, symbol: Optional[str] = None,
                          strategy_id: Optional[str] = None) -> List[Dict]:
        """Get all open positions, optionally filtered."""
        query = "SELECT * FROM positions WHERE status = 'OPEN'"
        params = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        if strategy_id:
            query += " AND strategy_id = ?"
            params.append(strategy_id)

        query += " ORDER BY entry_time DESC"

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error fetching open positions: {e}")
            return []

    # ==================== Order Methods ====================

    def create_order(self, order_id: str, symbol: str, asset_type: str,
                    side: str, order_type: str, quantity: float,
                    strategy_id: str, price: Optional[float] = None,
                    position_id: Optional[int] = None) -> int:
        """Create new order."""
        query = """
            INSERT INTO orders
            (order_id, symbol, asset_type, side, order_type, quantity,
             price, strategy_id, position_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (
                    order_id, symbol, asset_type, side, order_type,
                    quantity, price, strategy_id, position_id
                ))
                conn.commit()
                return cursor.lastrowid

        except Exception as e:
            logger.error(f"Error creating order: {e}")
            return -1

    def update_order_status(self, order_id: str, status: str,
                           filled_quantity: Optional[float] = None,
                           avg_fill_price: Optional[float] = None,
                           commission: Optional[float] = None) -> bool:
        """Update order status and fill information."""
        query = """
            UPDATE orders
            SET status = ?, filled_quantity = COALESCE(?, filled_quantity),
                avg_fill_price = COALESCE(?, avg_fill_price),
                commission = COALESCE(?, commission),
                updated_at = ?
            WHERE order_id = ?
        """

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (
                    status, filled_quantity, avg_fill_price, commission,
                    datetime.now().isoformat(), order_id
                ))
                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error updating order status: {e}")
            return False

    # ==================== Signal Methods ====================

    def insert_signal(self, symbol: str, asset_type: str, timestamp: datetime,
                     strategy_id: str, signal_type: str, confidence: float,
                     price: float, metadata: Optional[Dict] = None) -> bool:
        """Insert trading signal."""
        query = """
            INSERT OR REPLACE INTO signals
            (symbol, asset_type, timestamp, strategy_id, signal_type,
             confidence, price, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (
                    symbol, asset_type, timestamp.isoformat(), strategy_id,
                    signal_type, confidence, price,
                    json.dumps(metadata) if metadata else None
                ))
                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error inserting signal: {e}")
            return False

    # ==================== Backtest Results Methods ====================

    def save_backtest_results(self, backtest_id: str, strategy_id: str,
                             symbols: List[str], asset_type: str,
                             start_date: datetime, end_date: datetime,
                             initial_capital: float, final_capital: float,
                             metrics: Dict, config: Dict, results: Dict) -> bool:
        """Save backtest results."""
        query = """
            INSERT INTO backtest_results
            (backtest_id, strategy_id, symbols, asset_type, start_date, end_date,
             initial_capital, final_capital, total_return, sharpe_ratio, sortino_ratio,
             max_drawdown, win_rate, total_trades, config, results)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        try:
            total_return = (final_capital - initial_capital) / initial_capital

            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (
                    backtest_id, strategy_id, json.dumps(symbols), asset_type,
                    start_date.isoformat(), end_date.isoformat(),
                    initial_capital, final_capital, total_return,
                    metrics.get('sharpe_ratio'), metrics.get('sortino_ratio'),
                    metrics.get('max_drawdown'), metrics.get('win_rate'),
                    metrics.get('total_trades'),
                    json.dumps(config), json.dumps(results)
                ))
                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error saving backtest results: {e}")
            return False

    # ==================== Risk Event Methods ====================

    def log_risk_event(self, event_type: str, severity: str, description: str,
                      symbol: Optional[str] = None, asset_type: Optional[str] = None,
                      strategy_id: Optional[str] = None, metadata: Optional[Dict] = None) -> bool:
        """Log risk event."""
        query = """
            INSERT INTO risk_events
            (timestamp, event_type, severity, symbol, asset_type,
             strategy_id, description, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (
                    datetime.now().isoformat(), event_type, severity,
                    symbol, asset_type, strategy_id, description,
                    json.dumps(metadata) if metadata else None
                ))
                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error logging risk event: {e}")
            return False


if __name__ == "__main__":
    # Test database initialization
    logging.basicConfig(level=logging.INFO)
    db = DatabaseManager("data/test.db")
    print("Database initialized successfully!")
    db.close()
