"""
Backtest Report Generator.

Generates comprehensive HTML reports with charts and exports.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import pandas as pd

logger = logging.getLogger(__name__)


class BacktestReport:
    """
    Backtest report generator.

    Generates:
    - Equity curve chart (PNG)
    - Drawdown chart (PNG)
    - Returns distribution histogram (PNG)
    - Monthly returns heatmap (PNG)
    - Trade log (CSV)
    - Full results (JSON)
    - HTML summary report
    """

    def __init__(self, backtest_id: str, metrics: Dict,
                 equity_curve: List[Tuple[datetime, float]],
                 trades: List[Dict], initial_capital: float):
        """
        Initialize report generator.

        Args:
            backtest_id: Unique backtest ID
            metrics: Metrics dict from PerformanceCalculator
            equity_curve: List of (timestamp, portfolio_value) tuples
            trades: List of trade dicts
            initial_capital: Starting capital
        """
        self.backtest_id = backtest_id
        self.metrics = metrics
        self.equity_curve = equity_curve
        self.trades = trades
        self.initial_capital = initial_capital

        logger.info(f"BacktestReport initialized for {backtest_id}")

    def generate(self, output_dir: str = "reports/") -> str:
        """
        Generate all report artifacts.

        Creates:
        1. Equity curve chart (PNG)
        2. Drawdown chart (PNG)
        3. Returns distribution histogram (PNG)
        4. Monthly returns heatmap (PNG)
        5. Trade log (CSV)
        6. Full results (JSON)
        7. HTML summary report (embeds all charts)

        Args:
            output_dir: Directory for output files

        Returns:
            Path to HTML report
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Generating report in {output_path}")

        # Generate charts
        equity_chart_path = self._plot_equity_curve(output_path)
        drawdown_chart_path = self._plot_drawdown(output_path)
        returns_dist_path = self._plot_returns_distribution(output_path)
        monthly_heatmap_path = self._plot_monthly_heatmap(output_path)

        # Generate data exports
        trade_csv_path = self._export_trades_csv(output_path)
        results_json_path = self._export_results_json(output_path)

        # Generate HTML summary
        html_path = self._generate_html_report(
            output_path,
            charts={
                'equity': equity_chart_path,
                'drawdown': drawdown_chart_path,
                'returns': returns_dist_path,
                'monthly': monthly_heatmap_path
            },
            exports={
                'trades_csv': trade_csv_path,
                'results_json': results_json_path
            }
        )

        logger.info(f"Report generated: {html_path}")
        return html_path

    def _plot_equity_curve(self, output_path: Path) -> str:
        """
        Plot equity curve with matplotlib.

        Args:
            output_path: Output directory

        Returns:
            Path to chart file
        """
        if len(self.equity_curve) < 2:
            logger.warning("Insufficient data for equity curve")
            return ""

        timestamps, equity = zip(*self.equity_curve)

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(timestamps, equity, linewidth=2, color='#2E86AB')
        ax.fill_between(timestamps, self.initial_capital, equity,
                        alpha=0.3, color='#2E86AB')

        ax.set_title(f'Equity Curve - {self.backtest_id}',
                    fontsize=16, fontweight='bold')
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Portfolio Value ($)', fontsize=12)
        ax.grid(True, alpha=0.3)

        # Add initial capital line
        ax.axhline(y=self.initial_capital, color='gray', linestyle='--',
                  label=f'Initial Capital: ${self.initial_capital:,.0f}')

        # Format y-axis as currency
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, p: f'${x:,.0f}')
        )

        ax.legend()
        plt.tight_layout()

        chart_path = output_path / f'{self.backtest_id}_equity_curve.png'
        plt.savefig(chart_path, dpi=150)
        plt.close()

        return str(chart_path)

    def _plot_drawdown(self, output_path: Path) -> str:
        """
        Plot drawdown over time.

        Args:
            output_path: Output directory

        Returns:
            Path to chart file
        """
        if len(self.equity_curve) < 2:
            return ""

        timestamps, equity = zip(*self.equity_curve)
        equity_series = pd.Series(equity, index=pd.DatetimeIndex(timestamps))

        # Calculate drawdown
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.fill_between(drawdown.index, 0, drawdown.values,
                        alpha=0.5, color='#E63946')
        ax.plot(drawdown.index, drawdown.values, linewidth=1, color='#E63946')

        ax.set_title(f'Drawdown - {self.backtest_id}',
                    fontsize=16, fontweight='bold')
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Drawdown (%)', fontsize=12)
        ax.grid(True, alpha=0.3)

        # Format y-axis as percentage
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, p: f'{x*100:.1f}%')
        )

        plt.tight_layout()

        chart_path = output_path / f'{self.backtest_id}_drawdown.png'
        plt.savefig(chart_path, dpi=150)
        plt.close()

        return str(chart_path)

    def _plot_returns_distribution(self, output_path: Path) -> str:
        """
        Plot histogram of daily returns.

        Args:
            output_path: Output directory

        Returns:
            Path to chart file
        """
        if len(self.equity_curve) < 2:
            return ""

        timestamps, equity = zip(*self.equity_curve)
        equity_series = pd.Series(equity, index=pd.DatetimeIndex(timestamps))
        daily_returns = equity_series.pct_change().dropna()

        if len(daily_returns) == 0:
            return ""

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.hist(daily_returns.values, bins=50, alpha=0.7, color='#457B9D',
               edgecolor='black')

        ax.set_title(f'Returns Distribution - {self.backtest_id}',
                    fontsize=16, fontweight='bold')
        ax.set_xlabel('Daily Return', fontsize=12)
        ax.set_ylabel('Frequency', fontsize=12)
        ax.grid(True, alpha=0.3)

        # Add vertical line at mean
        mean_return = daily_returns.mean()
        ax.axvline(x=mean_return, color='red', linestyle='--',
                  label=f'Mean: {mean_return*100:.2f}%')

        # Format x-axis as percentage
        ax.xaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, p: f'{x*100:.1f}%')
        )

        ax.legend()
        plt.tight_layout()

        chart_path = output_path / f'{self.backtest_id}_returns_dist.png'
        plt.savefig(chart_path, dpi=150)
        plt.close()

        return str(chart_path)

    def _plot_monthly_heatmap(self, output_path: Path) -> str:
        """
        Plot monthly returns heatmap.

        Args:
            output_path: Output directory

        Returns:
            Path to chart file
        """
        monthly_returns = self.metrics.get('monthly', {}).get('monthly_returns', {})

        if not monthly_returns:
            return ""

        # Convert to DataFrame
        returns_df = pd.Series(monthly_returns)
        returns_df.index = pd.to_datetime(returns_df.index)

        # Create pivot table (year x month)
        pivot = returns_df.groupby([
            returns_df.index.year,
            returns_df.index.month
        ]).first().unstack()

        if pivot.empty:
            return ""

        fig, ax = plt.subplots(figsize=(12, 6))

        # Create heatmap manually since seaborn might not be installed
        im = ax.imshow(pivot.values, cmap='RdYlGn', aspect='auto',
                      vmin=-0.1, vmax=0.1)

        # Set ticks
        ax.set_xticks(range(12))
        ax.set_xticklabels(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                            'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels(pivot.index)

        # Add colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Monthly Return', rotation=270, labelpad=15)

        ax.set_title(f'Monthly Returns Heatmap - {self.backtest_id}',
                    fontsize=16, fontweight='bold')

        plt.tight_layout()

        chart_path = output_path / f'{self.backtest_id}_monthly_heatmap.png'
        plt.savefig(chart_path, dpi=150)
        plt.close()

        return str(chart_path)

    def _export_trades_csv(self, output_path: Path) -> str:
        """
        Export trades to CSV.

        Args:
            output_path: Output directory

        Returns:
            Path to CSV file
        """
        if not self.trades:
            return ""

        # Convert to DataFrame
        trades_df = pd.DataFrame(self.trades)

        # Select relevant columns
        columns = ['symbol', 'side', 'quantity', 'entry_price', 'entry_time',
                  'exit_price', 'exit_time', 'pnl_realized', 'status']
        columns = [c for c in columns if c in trades_df.columns]

        trades_df = trades_df[columns]

        csv_path = output_path / f'{self.backtest_id}_trades.csv'
        trades_df.to_csv(csv_path, index=False)

        return str(csv_path)

    def _export_results_json(self, output_path: Path) -> str:
        """
        Export complete results to JSON.

        Args:
            output_path: Output directory

        Returns:
            Path to JSON file
        """
        results = {
            'backtest_id': self.backtest_id,
            'initial_capital': self.initial_capital,
            'final_value': self.equity_curve[-1][1] if self.equity_curve else 0,
            'metrics': self.metrics,
            'num_trades': len(self.trades)
        }

        json_path = output_path / f'{self.backtest_id}_results.json'
        with open(json_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        return str(json_path)

    def _generate_html_report(self, output_path: Path, charts: Dict,
                              exports: Dict) -> str:
        """
        Generate HTML summary report.

        Args:
            output_path: Output directory
            charts: Dict of chart names -> paths
            exports: Dict of export names -> paths

        Returns:
            Path to HTML file
        """
        # Get metrics
        returns = self.metrics.get('returns', {})
        risk = self.metrics.get('risk_adjusted', {})
        dd = self.metrics.get('drawdown', {})
        trades = self.metrics.get('trades', {})
        monthly = self.metrics.get('monthly', {})

        # Get chart filenames
        equity_chart = Path(charts.get('equity', '')).name if charts.get('equity') else ''
        drawdown_chart = Path(charts.get('drawdown', '')).name if charts.get('drawdown') else ''
        returns_chart = Path(charts.get('returns', '')).name if charts.get('returns') else ''
        monthly_chart = Path(charts.get('monthly', '')).name if charts.get('monthly') else ''

        # Get export filenames
        trades_csv = Path(exports.get('trades_csv', '')).name if exports.get('trades_csv') else ''
        results_json = Path(exports.get('results_json', '')).name if exports.get('results_json') else ''

        # Compute CSS classes
        return_class = 'positive' if returns.get('total_return_pct', 0) > 0 else 'negative'

        # Generate HTML
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Backtest Report - {self.backtest_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        h1 {{ color: #2E86AB; }}
        h2 {{ color: #457B9D; margin-top: 30px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; background-color: white; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #2E86AB; color: white; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        .positive {{ color: green; font-weight: bold; }}
        .negative {{ color: red; font-weight: bold; }}
        .chart {{ margin: 20px 0; text-align: center; }}
        .chart img {{ max-width: 100%; height: auto; border: 1px solid #ddd; }}
        .export-links {{ margin: 20px 0; }}
        .export-links a {{ margin-right: 20px; color: #2E86AB; text-decoration: none; font-weight: bold; }}
        .export-links a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <h1>Backtest Report: {self.backtest_id}</h1>
    <p><strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p><strong>Initial Capital:</strong> ${self.initial_capital:,.2f}</p>
    <p><strong>Final Value:</strong> ${self.equity_curve[-1][1]:,.2f if self.equity_curve else 0}</p>

    <h2>Performance Metrics</h2>
    <table>
        <tr>
            <th>Metric</th>
            <th>Value</th>
        </tr>
        <tr>
            <td>Total Return</td>
            <td class="{return_class}">
                {returns.get('total_return_pct', 0)*100:.2f}%
            </td>
        </tr>
        <tr>
            <td>CAGR</td>
            <td>{returns.get('cagr', 0)*100:.2f}%</td>
        </tr>
        <tr>
            <td>Sharpe Ratio</td>
            <td>{risk.get('sharpe_ratio', 0):.2f}</td>
        </tr>
        <tr>
            <td>Sortino Ratio</td>
            <td>{risk.get('sortino_ratio', 0):.2f}</td>
        </tr>
        <tr>
            <td>Max Drawdown</td>
            <td class="negative">{dd.get('max_drawdown_pct', 0)*100:.2f}%</td>
        </tr>
        <tr>
            <td>Volatility (Annualized)</td>
            <td>{risk.get('volatility', 0)*100:.2f}%</td>
        </tr>
    </table>

    <h2>Trade Statistics</h2>
    <table>
        <tr>
            <th>Metric</th>
            <th>Value</th>
        </tr>
        <tr>
            <td>Total Trades</td>
            <td>{trades.get('total_trades', 0)}</td>
        </tr>
        <tr>
            <td>Win Rate</td>
            <td>{trades.get('win_rate', 0)*100:.2f}%</td>
        </tr>
        <tr>
            <td>Profit Factor</td>
            <td>{trades.get('profit_factor', 0):.2f}</td>
        </tr>
        <tr>
            <td>Expectancy</td>
            <td>${trades.get('expectancy', 0):.2f}</td>
        </tr>
        <tr>
            <td>Average Win</td>
            <td class="positive">${trades.get('avg_win', 0):.2f}</td>
        </tr>
        <tr>
            <td>Average Loss</td>
            <td class="negative">${trades.get('avg_loss', 0):.2f}</td>
        </tr>
    </table>

    <h2>Equity Curve</h2>
    <div class="chart">
        <img src="{equity_chart}" alt="Equity Curve">
    </div>

    <h2>Drawdown</h2>
    <div class="chart">
        <img src="{drawdown_chart}" alt="Drawdown">
    </div>

    <h2>Returns Distribution</h2>
    <div class="chart">
        <img src="{returns_chart}" alt="Returns Distribution">
    </div>

    <h2>Monthly Returns Heatmap</h2>
    <div class="chart">
        <img src="{monthly_chart}" alt="Monthly Returns">
    </div>

    <h2>Exports</h2>
    <div class="export-links">
        <a href="{trades_csv}">Download Trade Log (CSV)</a>
        <a href="{results_json}">Download Full Results (JSON)</a>
    </div>

    <hr>
    <p><small>Generated by QuantSage Backtesting Engine</small></p>
</body>
</html>
"""

        html_path = output_path / f'{self.backtest_id}_summary.html'
        with open(html_path, 'w') as f:
            f.write(html)

        return str(html_path)
