"""
Launch the QuantSage Trading Dashboard.

Simple script to start the real-time web dashboard for monitoring
trading activity, positions, and performance.

Usage:
    python scripts/run_dashboard.py [--db PATH] [--port PORT]

Examples:
    # Use default database (data/paper_trading.db)
    python scripts/run_dashboard.py

    # Use custom database
    python scripts/run_dashboard.py --db data/live_trading.db

    # Use custom port
    python scripts/run_dashboard.py --port 8080

    # Custom database and port
    python scripts/run_dashboard.py --db data/backtest.db --port 9000
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.monitoring import create_dashboard


def main():
    """Launch dashboard with command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Launch QuantSage Trading Dashboard',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Default: data/paper_trading.db on port 8050
  %(prog)s --db data/live.db           # Custom database
  %(prog)s --port 9000                 # Custom port
  %(prog)s --db data/live.db --port 9000  # Both custom
        """
    )

    parser.add_argument(
        '--db',
        type=str,
        default='data/paper_trading.db',
        help='Path to trading database (default: data/paper_trading.db)'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=8050,
        help='Port number for dashboard server (default: 8050)'
    )

    parser.add_argument(
        '--refresh',
        type=int,
        default=5,
        help='Auto-refresh interval in seconds (default: 5)'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )

    args = parser.parse_args()

    # Check if database exists
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"\n⚠️  Warning: Database not found: {args.db}")
        print(f"   Creating new database at this location...")
        db_path.parent.mkdir(parents=True, exist_ok=True)

    # Create and run dashboard
    dashboard = create_dashboard(
        db_path=args.db,
        refresh_interval=args.refresh * 1000  # Convert to milliseconds
    )

    print(f"\n{'='*60}")
    print(f"Configuration:")
    print(f"  Database: {args.db}")
    print(f"  Port: {args.port}")
    print(f"  Refresh: Every {args.refresh} seconds")
    print(f"  Debug: {'Enabled' if args.debug else 'Disabled'}")
    print(f"{'='*60}\n")

    dashboard.run(
        host='127.0.0.1',
        port=args.port,
        debug=args.debug
    )


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✋ Dashboard stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
