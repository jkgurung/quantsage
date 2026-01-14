#!/usr/bin/env python3
"""
Initialize QuantSage database with schema.

This script creates the main database and all required tables.
Safe to run multiple times (won't overwrite existing data).

Usage:
    python scripts/init_db.py
    python scripts/init_db.py --db data/custom.db
"""

import sys
import os
from pathlib import Path
import argparse
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.storage import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_database(db_path: str):
    """
    Initialize database with schema.

    Args:
        db_path: Path to database file
    """
    logger.info(f"Initializing database: {db_path}")

    # Create data directory if it doesn't exist
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        logger.info(f"Created directory: {db_dir}")

    # Check if database already exists
    db_exists = os.path.exists(db_path)
    if db_exists:
        logger.info(f"Database already exists: {db_path}")
        logger.info("Schema will be updated if needed (existing data preserved)")

    # Initialize database (creates tables if they don't exist)
    try:
        db = DatabaseManager(db_path)
        logger.info("✅ Database initialized successfully!")

        # Show table count
        tables_query = "SELECT name FROM sqlite_master WHERE type='table'"
        tables = db.query(tables_query)
        logger.info(f"Tables created: {len(tables)}")
        for table in tables:
            logger.info(f"  - {table['name']}")

        # Show record counts for main tables
        for table_name in ['market_data', 'positions', 'orders', 'trades', 'signals']:
            try:
                count_query = f"SELECT COUNT(*) as count FROM {table_name}"
                result = db.query(count_query)
                count = result[0]['count'] if result else 0
                logger.info(f"  {table_name}: {count} records")
            except Exception as e:
                logger.warning(f"  {table_name}: Could not count records ({e})")

        return True

    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Initialize QuantSage database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize default database
  python scripts/init_db.py

  # Initialize custom database
  python scripts/init_db.py --db data/custom.db

  # Initialize paper trading database
  python scripts/init_db.py --db data/paper_trading.db
        """
    )

    parser.add_argument(
        '--db',
        type=str,
        default='data/quantsage.db',
        help='Database path (default: data/quantsage.db)'
    )

    args = parser.parse_args()

    # Initialize database
    success = init_database(args.db)

    if success:
        logger.info(f"\n✅ Database ready at: {args.db}")
        logger.info("\nNext steps:")
        logger.info("  1. Run paper trading: python scripts/paper_trading_demo.py")
        logger.info("  2. View dashboard: python scripts/run_dashboard.py")
        logger.info("  3. Run backtest: python scripts/run_backtest.py")
        sys.exit(0)
    else:
        logger.error("\n❌ Database initialization failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
