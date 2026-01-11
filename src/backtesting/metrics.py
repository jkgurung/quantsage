"""
Performance Calculator for Backtesting.

Calculates comprehensive performance metrics from backtest results.
"""

import logging
from datetime import datetime
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PerformanceCalculator:
    """
    Performance calculator for backtest metrics.

    Calculates:
    - Returns: Total return, CAGR, annualized return
    - Risk-adjusted: Sharpe, Sortino, Calmar ratios
    - Drawdown: Max DD, average DD, duration
    - Trade stats: Win rate, profit factor, expectancy
    - Monthly analysis: Best/worst/average month
    """

    def __init__(self, equity_curve: List[Tuple[datetime, float]],
                 trades: List[Dict], initial_capital: float,
                 start_date: datetime, end_date: datetime,
                 risk_free_rate: float = 0.03):
        """
        Initialize performance calculator.

        Args:
            equity_curve: List of (timestamp, portfolio_value) tuples
            trades: List of trade dicts from database
            initial_capital: Starting capital
            start_date: Backtest start date
            end_date: Backtest end date
            risk_free_rate: Annual risk-free rate (default: 3%)
        """
        self.equity_curve = equity_curve
        self.trades = trades
        self.initial_capital = initial_capital
        self.start_date = start_date
        self.end_date = end_date
        self.risk_free_rate = risk_free_rate

        logger.info(f"PerformanceCalculator initialized with {len(equity_curve)} equity points")

    def calculate_all(self) -> Dict:
        """
        Calculate comprehensive performance metrics.

        Returns:
            Dict with keys:
            - returns: {total_return, total_return_pct, cagr, annualized_return}
            - risk_adjusted: {sharpe_ratio, sortino_ratio, calmar_ratio, volatility}
            - drawdown: {max_drawdown, max_drawdown_pct, avg_drawdown, max_dd_duration_days}
            - trades: {total_trades, win_rate, profit_factor, expectancy, avg_win, avg_loss}
            - monthly: {best_month, worst_month, avg_month, positive_months_pct}
        """
        if len(self.equity_curve) < 2:
            logger.warning("Insufficient data points in equity curve")
            return self._empty_metrics()

        # Convert equity curve to pandas series
        timestamps, equity_values = zip(*self.equity_curve)
        equity_series = pd.Series(equity_values, index=pd.DatetimeIndex(timestamps))

        # Calculate all metrics
        returns_metrics = self._calculate_returns(equity_series)
        risk_metrics = self._calculate_risk_adjusted(equity_series)
        drawdown_metrics = self._calculate_drawdown(equity_series)
        trade_metrics = self._calculate_trade_stats()
        monthly_metrics = self._calculate_monthly_returns(equity_series)

        return {
            'returns': returns_metrics,
            'risk_adjusted': risk_metrics,
            'drawdown': drawdown_metrics,
            'trades': trade_metrics,
            'monthly': monthly_metrics
        }

    def _calculate_returns(self, equity_series: pd.Series) -> Dict:
        """
        Calculate return metrics.

        Total return: (final - initial) / initial
        CAGR: (final/initial)^(1/years) - 1
        Annualized return: mean(daily_returns) * 252

        Args:
            equity_series: Pandas series of equity values

        Returns:
            Dict of return metrics
        """
        final_value = equity_series.iloc[-1]
        total_return = final_value - self.initial_capital
        total_return_pct = total_return / self.initial_capital

        # Calculate CAGR
        days = (self.end_date - self.start_date).days
        years = days / 365.25
        if years > 0:
            cagr = (final_value / self.initial_capital) ** (1 / years) - 1
        else:
            cagr = 0.0

        # Calculate annualized return from daily returns
        daily_returns = equity_series.pct_change().dropna()
        if len(daily_returns) > 0:
            annualized_return = daily_returns.mean() * 252
        else:
            annualized_return = 0.0

        return {
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'cagr': cagr,
            'annualized_return': annualized_return
        }

    def _calculate_risk_adjusted(self, equity_series: pd.Series) -> Dict:
        """
        Calculate risk-adjusted metrics.

        Args:
            equity_series: Pandas series of equity values

        Returns:
            Dict of risk-adjusted metrics
        """
        # Calculate daily returns
        daily_returns = equity_series.pct_change().dropna()

        if len(daily_returns) < 2:
            return {
                'sharpe_ratio': 0.0,
                'sortino_ratio': 0.0,
                'calmar_ratio': 0.0,
                'volatility': 0.0
            }

        # Volatility (annualized)
        volatility = daily_returns.std() * np.sqrt(252)

        # Sharpe ratio
        sharpe = self._calculate_sharpe_ratio(daily_returns)

        # Sortino ratio
        sortino = self._calculate_sortino_ratio(daily_returns)

        # Calmar ratio
        calmar = self._calculate_calmar_ratio(equity_series)

        return {
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'calmar_ratio': calmar,
            'volatility': volatility
        }

    def _calculate_sharpe_ratio(self, daily_returns: pd.Series) -> float:
        """
        Calculate annualized Sharpe ratio.

        Sharpe = (mean(excess_returns) / std(returns)) * sqrt(252)

        Args:
            daily_returns: Pandas series of daily returns

        Returns:
            Sharpe ratio
        """
        # Calculate excess returns (subtract risk-free rate)
        daily_rf_rate = self.risk_free_rate / 252
        excess_returns = daily_returns - daily_rf_rate

        # Calculate Sharpe
        if excess_returns.std() == 0 or len(excess_returns) == 0:
            return 0.0

        sharpe = (excess_returns.mean() / excess_returns.std()) * np.sqrt(252)
        return sharpe

    def _calculate_sortino_ratio(self, daily_returns: pd.Series) -> float:
        """
        Calculate annualized Sortino ratio.

        Sortino = (mean(excess_returns) / downside_std) * sqrt(252)
        Downside std = std of negative returns only

        Args:
            daily_returns: Pandas series of daily returns

        Returns:
            Sortino ratio
        """
        # Calculate excess returns
        daily_rf_rate = self.risk_free_rate / 252
        excess_returns = daily_returns - daily_rf_rate

        # Calculate downside deviation (only negative returns)
        downside_returns = excess_returns[excess_returns < 0]

        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0

        sortino = (excess_returns.mean() / downside_returns.std()) * np.sqrt(252)
        return sortino

    def _calculate_calmar_ratio(self, equity_series: pd.Series) -> float:
        """
        Calculate Calmar ratio.

        Calmar = CAGR / abs(max_drawdown)

        Args:
            equity_series: Pandas series of equity values

        Returns:
            Calmar ratio
        """
        # Calculate CAGR
        days = (self.end_date - self.start_date).days
        years = days / 365.25
        if years > 0:
            cagr = (equity_series.iloc[-1] / self.initial_capital) ** (1 / years) - 1
        else:
            return 0.0

        # Calculate max drawdown
        max_dd_pct, _, _ = self._calculate_max_drawdown(equity_series)

        if max_dd_pct == 0:
            return 0.0

        calmar = cagr / abs(max_dd_pct)
        return calmar

    def _calculate_drawdown(self, equity_series: pd.Series) -> Dict:
        """
        Calculate drawdown metrics.

        Args:
            equity_series: Pandas series of equity values

        Returns:
            Dict of drawdown metrics
        """
        max_dd_pct, max_dd_dollars, duration = self._calculate_max_drawdown(equity_series)

        # Calculate average drawdown
        running_max = equity_series.expanding().max()
        drawdown = equity_series - running_max
        drawdown_pct = drawdown / running_max

        # Average of all drawdown periods (negative values)
        negative_drawdowns = drawdown_pct[drawdown_pct < 0]
        avg_drawdown = negative_drawdowns.mean() if len(negative_drawdowns) > 0 else 0.0

        return {
            'max_drawdown': max_dd_dollars,
            'max_drawdown_pct': max_dd_pct,
            'avg_drawdown': avg_drawdown,
            'max_dd_duration_days': duration
        }

    def _calculate_max_drawdown(self, equity_series: pd.Series) -> Tuple[float, float, int]:
        """
        Calculate maximum drawdown and duration.

        Returns:
            (max_dd_pct, max_dd_dollars, duration_days)
        """
        # Calculate running maximum
        running_max = equity_series.expanding().max()

        # Calculate drawdown at each point
        drawdown = equity_series - running_max
        drawdown_pct = drawdown / running_max

        # Find maximum drawdown
        max_dd_pct = drawdown_pct.min()
        max_dd_dollars = drawdown.min()

        # Calculate duration (from peak to trough to recovery)
        if max_dd_pct == 0:
            return (0.0, 0.0, 0)

        # Find the index of max drawdown
        max_dd_idx = drawdown_pct.idxmin()

        # Find previous peak
        peak_idx = running_max.loc[:max_dd_idx].idxmax()

        # Find recovery point (when equity exceeds previous peak)
        recovery_series = equity_series.loc[max_dd_idx:]
        recovery_idx = recovery_series[recovery_series >= running_max.loc[max_dd_idx]].index

        if len(recovery_idx) > 0:
            duration = (recovery_idx[0] - peak_idx).days
        else:
            # Still in drawdown
            duration = (equity_series.index[-1] - peak_idx).days

        return (max_dd_pct, max_dd_dollars, duration)

    def _calculate_trade_stats(self) -> Dict:
        """
        Calculate trade statistics from closed trades.

        Returns:
            Dict of trade stats
        """
        # Filter to closed positions only
        closed_trades = [t for t in self.trades if t.get('status') == 'CLOSED']

        if not closed_trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'expectancy': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'max_win': 0.0,
                'max_loss': 0.0,
                'avg_trade_duration_hours': 0.0
            }

        # Extract P&L values
        pnls = [t.get('pnl_realized', 0) for t in closed_trades]

        # Separate winners and losers
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p < 0]

        # Calculate metrics
        total_trades = len(closed_trades)
        winning_trades = len(winners)
        losing_trades = len(losers)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        avg_win = np.mean(winners) if winners else 0
        avg_loss = np.mean(losers) if losers else 0
        max_win = max(winners) if winners else 0
        max_loss = min(losers) if losers else 0

        # Profit factor
        total_wins = sum(winners)
        total_losses = abs(sum(losers))
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

        # Expectancy
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * abs(avg_loss))

        # Average trade duration
        durations = []
        for trade in closed_trades:
            entry_time = trade.get('entry_time')
            exit_time = trade.get('exit_time')
            if entry_time and exit_time:
                try:
                    entry = pd.Timestamp(entry_time)
                    exit = pd.Timestamp(exit_time)
                    duration_hours = (exit - entry).total_seconds() / 3600
                    durations.append(duration_hours)
                except:
                    pass

        avg_duration = np.mean(durations) if durations else 0

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'expectancy': expectancy,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'max_win': max_win,
            'max_loss': max_loss,
            'avg_trade_duration_hours': avg_duration
        }

    def _calculate_monthly_returns(self, equity_series: pd.Series) -> Dict:
        """
        Calculate monthly return statistics.

        Args:
            equity_series: Pandas series of equity values

        Returns:
            Dict of monthly metrics
        """
        # Resample to monthly returns
        monthly_equity = equity_series.resample('M').last()
        monthly_returns = monthly_equity.pct_change().dropna()

        if len(monthly_returns) == 0:
            return {
                'best_month': 0.0,
                'worst_month': 0.0,
                'avg_month': 0.0,
                'positive_months_pct': 0.0
            }

        best_month = monthly_returns.max()
        worst_month = monthly_returns.min()
        avg_month = monthly_returns.mean()

        positive_months = len(monthly_returns[monthly_returns > 0])
        positive_months_pct = positive_months / len(monthly_returns)

        return {
            'best_month': best_month,
            'worst_month': worst_month,
            'avg_month': avg_month,
            'positive_months_pct': positive_months_pct,
            'monthly_returns': monthly_returns.to_dict()  # For heatmap
        }

    def _empty_metrics(self) -> Dict:
        """Return empty metrics dict when insufficient data."""
        return {
            'returns': {
                'total_return': 0.0,
                'total_return_pct': 0.0,
                'cagr': 0.0,
                'annualized_return': 0.0
            },
            'risk_adjusted': {
                'sharpe_ratio': 0.0,
                'sortino_ratio': 0.0,
                'calmar_ratio': 0.0,
                'volatility': 0.0
            },
            'drawdown': {
                'max_drawdown': 0.0,
                'max_drawdown_pct': 0.0,
                'avg_drawdown': 0.0,
                'max_dd_duration_days': 0
            },
            'trades': {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'expectancy': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'max_win': 0.0,
                'max_loss': 0.0,
                'avg_trade_duration_hours': 0.0
            },
            'monthly': {
                'best_month': 0.0,
                'worst_month': 0.0,
                'avg_month': 0.0,
                'positive_months_pct': 0.0
            }
        }
