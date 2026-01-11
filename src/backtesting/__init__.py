"""
Backtesting package.

Provides:
- BacktestEngine: Event-driven backtesting orchestrator
- ExecutionEngine: Order fill simulator
- PortfolioManager: Position and P&L tracker
- PerformanceCalculator: Metrics calculator
- BacktestReport: Report generator
"""

from .engine import BacktestEngine
from .execution import ExecutionEngine
from .portfolio import PortfolioManager
from .metrics import PerformanceCalculator
from .report import BacktestReport

__all__ = [
    'BacktestEngine',
    'ExecutionEngine',
    'PortfolioManager',
    'PerformanceCalculator',
    'BacktestReport'
]
