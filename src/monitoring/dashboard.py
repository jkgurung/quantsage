"""
Real-time Trading Dashboard using Plotly Dash.

Professional web-based monitoring interface for live trading system.
Features:
- Live positions table with P&L
- Equity curve visualization
- Risk metrics panel
- Recent signals and trades
- Auto-refreshing every 5 seconds
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd

from src.data.storage import DatabaseManager
from src.core.config import ConfigManager

logger = logging.getLogger(__name__)


class TradingDashboard:
    """
    Real-time trading dashboard web application.

    Displays:
    - Portfolio summary (value, P&L, cash)
    - Open positions with unrealized P&L
    - Equity curve chart
    - Risk metrics and circuit breaker status
    - Recent signals and trades
    - Performance statistics
    """

    def __init__(self, db_path: str = 'data/paper_trading.db', refresh_interval: int = 5000):
        """
        Initialize dashboard.

        Args:
            db_path: Path to database
            refresh_interval: Auto-refresh interval in milliseconds (default: 5000ms = 5s)
        """
        self.db = DatabaseManager(db_path=db_path)
        self.refresh_interval = refresh_interval

        # Load configuration
        try:
            self.config = ConfigManager()
            self.initial_capital = self.config.get('portfolio.initial_capital', 100000.0)
        except Exception as e:
            logger.warning(f"Could not load config, using defaults: {e}")
            self.initial_capital = 100000.0

        # Initialize Dash app with Bootstrap CSS
        self.app = dash.Dash(
            __name__,
            title='QuantSage Trading Dashboard',
            update_title='Updating...'
        )

        # Build layout
        self.app.layout = self._create_layout()

        # Register callbacks
        self._register_callbacks()

        logger.info(f"Dashboard initialized: {db_path}, initial_capital: ${self.initial_capital:,.2f}, refresh every {refresh_interval}ms")

    def _create_layout(self):
        """Create dashboard layout."""
        return html.Div([
            # Header
            html.Div([
                html.H1('🚀 QuantSage Trading Dashboard',
                       style={'color': '#2E86AB', 'textAlign': 'center', 'marginBottom': '10px'}),
                html.P('Real-time monitoring of trading system',
                      style={'textAlign': 'center', 'color': '#666', 'marginBottom': '20px'}),
            ], style={'backgroundColor': '#f8f9fa', 'padding': '20px', 'borderRadius': '8px', 'marginBottom': '20px'}),

            # Auto-refresh interval
            dcc.Interval(
                id='interval-component',
                interval=self.refresh_interval,  # milliseconds
                n_intervals=0
            ),

            # Portfolio Summary Cards
            html.Div([
                html.H2('📊 Portfolio Summary', style={'color': '#457B9D', 'marginBottom': '15px'}),
                html.Div(id='portfolio-summary', children=[]),
            ], style={'marginBottom': '30px'}),

            # Circuit Breaker Status Panel
            html.Div([
                html.H2('🛡️ Risk Status', style={'color': '#457B9D', 'marginBottom': '15px'}),
                html.Div(id='circuit-breaker-status', children=[]),
            ], style={'marginBottom': '30px'}),

            # Two column layout
            html.Div([
                # Left column: Charts
                html.Div([
                    # Equity Curve
                    html.Div([
                        html.H3('📈 Equity Curve', style={'color': '#457B9D'}),
                        dcc.Graph(id='equity-curve'),
                    ], style={'marginBottom': '30px'}),

                    # Performance Metrics
                    html.Div([
                        html.H3('📉 Performance Metrics', style={'color': '#457B9D'}),
                        html.Div(id='performance-metrics'),
                    ]),
                ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top'}),

                # Right column: Tables
                html.Div([
                    # Open Positions
                    html.Div([
                        html.H3('💼 Open Positions', style={'color': '#457B9D'}),
                        html.Div(id='open-positions'),
                    ], style={'marginBottom': '30px'}),

                    # Recent Signals
                    html.Div([
                        html.H3('🎯 Recent Signals', style={'color': '#457B9D'}),
                        html.Div(id='recent-signals'),
                    ], style={'marginBottom': '30px'}),

                    # Recent Trades
                    html.Div([
                        html.H3('📝 Recent Trades', style={'color': '#457B9D'}),
                        html.Div(id='recent-trades'),
                    ], style={'marginBottom': '30px'}),

                    # Risk Alerts
                    html.Div([
                        html.H3('⚠️ Risk Alerts', style={'color': '#457B9D'}),
                        html.Div(id='risk-alerts'),
                    ]),
                ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top', 'marginLeft': '4%'}),
            ]),

            # Footer
            html.Div([
                html.P(f'Last updated: ', style={'display': 'inline', 'color': '#666'}),
                html.Span(id='last-update-time', style={'fontWeight': 'bold', 'color': '#2E86AB'}),
                html.P(' | Auto-refresh every 5 seconds', style={'display': 'inline', 'color': '#666', 'marginLeft': '20px'}),
            ], style={'textAlign': 'center', 'marginTop': '40px', 'padding': '20px', 'backgroundColor': '#f8f9fa', 'borderRadius': '8px'}),

        ], style={'padding': '20px', 'fontFamily': 'Arial, sans-serif', 'backgroundColor': '#ffffff', 'maxWidth': '1400px', 'margin': '0 auto'})

    def _register_callbacks(self):
        """Register all dashboard callbacks for auto-updating."""

        @self.app.callback(
            [Output('portfolio-summary', 'children'),
             Output('circuit-breaker-status', 'children'),
             Output('equity-curve', 'figure'),
             Output('open-positions', 'children'),
             Output('recent-signals', 'children'),
             Output('recent-trades', 'children'),
             Output('risk-alerts', 'children'),
             Output('performance-metrics', 'children'),
             Output('last-update-time', 'children')],
            [Input('interval-component', 'n_intervals')]
        )
        def update_dashboard(n):
            """Update all dashboard components."""
            try:
                # Get data
                portfolio_data = self._get_portfolio_data()
                circuit_breaker_data = self._get_circuit_breaker_status()
                equity_data = self._get_equity_data()
                positions_data = self._get_positions_data()
                signals_data = self._get_signals_data()
                trades_data = self._get_trades_data()
                risk_alerts_data = self._get_risk_alerts()
                metrics_data = self._get_metrics_data()

                # Build components
                summary_cards = self._build_summary_cards(portfolio_data)
                circuit_breaker_display = self._build_circuit_breaker_display(circuit_breaker_data)
                equity_fig = self._build_equity_chart(equity_data)
                positions_table = self._build_positions_table(positions_data)
                signals_table = self._build_signals_table(signals_data)
                trades_table = self._build_trades_table(trades_data)
                risk_alerts_table = self._build_risk_alerts_table(risk_alerts_data)
                metrics_display = self._build_metrics_display(metrics_data)
                update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                return (summary_cards, circuit_breaker_display, equity_fig, positions_table,
                        signals_table, trades_table, risk_alerts_table, metrics_display, update_time)

            except Exception as e:
                logger.error(f"Dashboard update error: {e}", exc_info=True)
                error_msg = html.Div(f"Error updating dashboard: {e}", style={'color': 'red'})
                return error_msg, error_msg, {}, error_msg, error_msg, error_msg, error_msg, error_msg, "Error"

    def _get_portfolio_data(self) -> Dict:
        """Get portfolio summary data with current prices."""
        try:
            # Get open positions
            positions = self.db.get_open_positions()

            # Get current market prices for all positions
            symbols = [pos['symbol'] for pos in positions]
            current_prices = self.db.get_current_market_prices(symbols) if symbols else {}

            # Calculate total position value using CURRENT prices
            total_position_value = 0
            for pos in positions:
                current_price = current_prices.get(pos['symbol'], pos['entry_price'])

                # Calculate position value based on side
                if pos['side'] == 'LONG':
                    position_value = pos['quantity'] * current_price
                else:  # SHORT
                    # For shorts, value is entry cost plus/minus P&L
                    position_value = pos['quantity'] * pos['entry_price']

                total_position_value += position_value

            # Calculate cash from trades
            # Get total buy costs and sell proceeds
            buy_query = "SELECT SUM(quantity * price + commission) as total FROM trades WHERE side = 'BUY'"
            sell_query = "SELECT SUM(quantity * price - commission) as total FROM trades WHERE side = 'SELL'"

            buy_result = self.db.query(buy_query)
            sell_result = self.db.query(sell_query)

            total_buy_cost = buy_result[0]['total'] if buy_result and buy_result[0]['total'] else 0
            total_sell_proceeds = sell_result[0]['total'] if sell_result and sell_result[0]['total'] else 0

            # Cash = initial capital + sells - buys
            cash = self.initial_capital + total_sell_proceeds - total_buy_cost

            # Portfolio value = cash + open positions value
            portfolio_value = cash + total_position_value

            # Calculate P&L
            total_pnl = portfolio_value - self.initial_capital
            total_pnl_pct = (total_pnl / self.initial_capital) * 100 if self.initial_capital > 0 else 0

            return {
                'portfolio_value': portfolio_value,
                'cash': cash,
                'total_pnl': total_pnl,
                'total_pnl_pct': total_pnl_pct,
                'num_positions': len(positions),
                'initial_capital': self.initial_capital
            }

        except Exception as e:
            logger.error(f"Error getting portfolio data: {e}", exc_info=True)
            # Return safe defaults
            return {
                'portfolio_value': self.initial_capital,
                'cash': self.initial_capital,
                'total_pnl': 0.0,
                'total_pnl_pct': 0.0,
                'num_positions': 0,
                'initial_capital': self.initial_capital
            }

    def _get_equity_data(self) -> List[Dict]:
        """Get equity curve data from trades."""
        try:
            # Use database method to build equity curve from trades
            equity_curve = self.db.get_equity_curve_from_trades(self.initial_capital)

            # If no trades yet, return initial point
            if not equity_curve:
                return [{
                    'timestamp': datetime.now() - timedelta(hours=24),
                    'equity': self.initial_capital
                }, {
                    'timestamp': datetime.now(),
                    'equity': self.initial_capital
                }]

            return equity_curve

        except Exception as e:
            logger.error(f"Error getting equity data: {e}", exc_info=True)
            # Return flat line at initial capital
            return [{
                'timestamp': datetime.now() - timedelta(hours=24),
                'equity': self.initial_capital
            }]

    def _get_positions_data(self) -> List[Dict]:
        """Get open positions."""
        return self.db.get_open_positions()

    def _get_signals_data(self) -> List[Dict]:
        """Get recent signals."""
        query = """
            SELECT timestamp, symbol, signal_type, price, confidence, strategy_id
            FROM signals
            ORDER BY timestamp DESC
            LIMIT 10
        """
        signals = self.db.query(query)

        return [
            {
                'timestamp': s[0],
                'symbol': s[1],
                'direction': s[2],  # signal_type maps to direction for display
                'price': s[3],
                'confidence': s[4],
                'strategy_id': s[5]
            }
            for s in signals
        ]

    def _get_trades_data(self) -> List[Dict]:
        """Get recent trades."""
        query = """
            SELECT timestamp, symbol, side, quantity, price, commission
            FROM trades
            ORDER BY timestamp DESC
            LIMIT 10
        """
        trades = self.db.query(query)

        return [
            {
                'timestamp': t[0],
                'symbol': t[1],
                'side': t[2],
                'quantity': t[3],
                'price': t[4],
                'commission': t[5]
            }
            for t in trades
        ]

    def _get_risk_alerts(self) -> List[Dict]:
        """Get recent unresolved risk events."""
        try:
            return self.db.get_recent_risk_events(limit=10, resolved=False)
        except Exception as e:
            logger.error(f"Error getting risk alerts: {e}")
            return []

    def _get_metrics_data(self) -> Dict:
        """Get performance metrics."""
        # Get closed positions for metrics
        query = """
            SELECT pnl_realized, entry_time, exit_time
            FROM positions
            WHERE status = 'CLOSED'
        """
        closed = self.db.query(query)

        if not closed:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0
            }

        wins = [p[0] for p in closed if p[0] > 0]
        losses = [p[0] for p in closed if p[0] < 0]

        return {
            'total_trades': len(closed),
            'win_rate': (len(wins) / len(closed) * 100) if closed else 0,
            'avg_win': sum(wins) / len(wins) if wins else 0,
            'avg_loss': sum(losses) / len(losses) if losses else 0,
            'profit_factor': abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else 0
        }

    def _build_summary_cards(self, data: Dict):
        """Build portfolio summary cards."""
        pnl_color = 'green' if data['total_pnl'] >= 0 else 'red'

        cards = html.Div([
            # Portfolio Value Card
            html.Div([
                html.H4('Portfolio Value', style={'color': '#666', 'fontSize': '14px', 'marginBottom': '5px'}),
                html.H2(f"${data['portfolio_value']:,.2f}", style={'color': '#2E86AB', 'margin': '0'}),
            ], style={'backgroundColor': '#f8f9fa', 'padding': '20px', 'borderRadius': '8px', 'width': '23%', 'display': 'inline-block', 'marginRight': '2%'}),

            # Cash Card
            html.Div([
                html.H4('Cash Balance', style={'color': '#666', 'fontSize': '14px', 'marginBottom': '5px'}),
                html.H2(f"${data['cash']:,.2f}", style={'color': '#457B9D', 'margin': '0'}),
            ], style={'backgroundColor': '#f8f9fa', 'padding': '20px', 'borderRadius': '8px', 'width': '23%', 'display': 'inline-block', 'marginRight': '2%'}),

            # Total P&L Card
            html.Div([
                html.H4('Total P&L', style={'color': '#666', 'fontSize': '14px', 'marginBottom': '5px'}),
                html.H2(f"${data['total_pnl']:,.2f}", style={'color': pnl_color, 'margin': '0'}),
                html.P(f"{data['total_pnl_pct']:+.2f}%", style={'color': pnl_color, 'fontSize': '16px', 'margin': '5px 0 0 0'}),
            ], style={'backgroundColor': '#f8f9fa', 'padding': '20px', 'borderRadius': '8px', 'width': '23%', 'display': 'inline-block', 'marginRight': '2%'}),

            # Open Positions Card
            html.Div([
                html.H4('Open Positions', style={'color': '#666', 'fontSize': '14px', 'marginBottom': '5px'}),
                html.H2(f"{data['num_positions']}", style={'color': '#2E86AB', 'margin': '0'}),
            ], style={'backgroundColor': '#f8f9fa', 'padding': '20px', 'borderRadius': '8px', 'width': '23%', 'display': 'inline-block'}),
        ])

        return cards

    def _build_equity_chart(self, data: List[Dict]):
        """Build equity curve chart."""
        if not data:
            return go.Figure()

        df = pd.DataFrame(data)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['equity'],
            mode='lines',
            name='Portfolio Value',
            line=dict(color='#2E86AB', width=2),
            fill='tozeroy',
            fillcolor='rgba(46, 134, 171, 0.1)'
        ))

        fig.update_layout(
            xaxis_title='Time',
            yaxis_title='Portfolio Value ($)',
            hovermode='x unified',
            template='plotly_white',
            height=400,
            margin=dict(l=50, r=20, t=20, b=50)
        )

        return fig

    def _build_positions_table(self, positions: List[Dict]):
        """Build open positions table with current prices."""
        if not positions:
            return html.P('No open positions', style={'color': '#666', 'fontStyle': 'italic'})

        try:
            # Get current market prices
            symbols = [pos['symbol'] for pos in positions]
            current_prices = self.db.get_current_market_prices(symbols)

            # Format data for table
            table_data = []
            for pos in positions:
                current_price = current_prices.get(pos['symbol'], pos['entry_price'])

                # Calculate unrealized P&L
                if pos['side'] == 'LONG':
                    pnl_unrealized = pos['quantity'] * (current_price - pos['entry_price'])
                else:  # SHORT
                    pnl_unrealized = pos['quantity'] * (pos['entry_price'] - current_price)

                # Use stored pnl_unrealized if available (already accounts for commissions)
                if pos.get('pnl_unrealized') is not None:
                    pnl_unrealized = pos['pnl_unrealized']

                pnl_pct = (pnl_unrealized / (pos['quantity'] * pos['entry_price'])) * 100 if pos['entry_price'] > 0 else 0

                table_data.append({
                    'Symbol': pos['symbol'],
                    'Side': pos['side'],
                    'Qty': f"{pos['quantity']:.6f}",
                    'Entry': f"${pos['entry_price']:,.2f}",
                    'Current': f"${current_price:,.2f}",  # NEW
                    'P&L $': f"${pnl_unrealized:,.2f}",
                    'P&L %': f"{pnl_pct:+.2f}%",  # NEW
                    'Strategy': pos.get('strategy_id', 'N/A')
                })

            df = pd.DataFrame(table_data)

            return dash_table.DataTable(
                data=df.to_dict('records'),
                columns=[{'name': i, 'id': i} for i in df.columns],
                style_cell={'textAlign': 'left', 'padding': '10px', 'fontSize': '14px'},
                style_header={'backgroundColor': '#2E86AB', 'color': 'white', 'fontWeight': 'bold'},
                style_data_conditional=[
                    {'if': {'row_index': 'odd'}, 'backgroundColor': '#f8f9fa'}
                ]
            )

        except Exception as e:
            logger.error(f"Error building positions table: {e}", exc_info=True)
            return html.P(f'Error loading positions: {e}', style={'color': 'red'})

    def _build_signals_table(self, signals: List[Dict]):
        """Build recent signals table."""
        if not signals:
            return html.P('No recent signals', style={'color': '#666', 'fontStyle': 'italic'})

        table_data = [{
            'Time': datetime.fromisoformat(s['timestamp']).strftime('%H:%M:%S'),
            'Symbol': s['symbol'],
            'Direction': s['direction'],
            'Price': f"${s['price']:,.2f}",
            'Confidence': f"{s['confidence']:.2f}" if s['confidence'] else 'N/A'
        } for s in signals[:5]]  # Show last 5

        df = pd.DataFrame(table_data)

        return dash_table.DataTable(
            data=df.to_dict('records'),
            columns=[{'name': i, 'id': i} for i in df.columns],
            style_cell={'textAlign': 'left', 'padding': '8px', 'fontSize': '13px'},
            style_header={'backgroundColor': '#457B9D', 'color': 'white', 'fontWeight': 'bold'},
            style_data_conditional=[
                {'if': {'row_index': 'odd'}, 'backgroundColor': '#f8f9fa'}
            ]
        )

    def _build_trades_table(self, trades: List[Dict]):
        """Build recent trades table."""
        if not trades:
            return html.P('No recent trades', style={'color': '#666', 'fontStyle': 'italic'})

        table_data = [{
            'Time': datetime.fromisoformat(t['timestamp']).strftime('%H:%M:%S'),
            'Symbol': t['symbol'],
            'Side': t['side'],
            'Qty': f"{t['quantity']:.6f}",
            'Price': f"${t['price']:,.2f}",
            'Fee': f"${t['commission']:.2f}"
        } for t in trades[:5]]  # Show last 5

        df = pd.DataFrame(table_data)

        return dash_table.DataTable(
            data=df.to_dict('records'),
            columns=[{'name': i, 'id': i} for i in df.columns],
            style_cell={'textAlign': 'left', 'padding': '8px', 'fontSize': '13px'},
            style_header={'backgroundColor': '#457B9D', 'color': 'white', 'fontWeight': 'bold'},
            style_data_conditional=[
                {'if': {'row_index': 'odd'}, 'backgroundColor': '#f8f9fa'}
            ]
        )

    def _build_metrics_display(self, metrics: Dict):
        """Build performance metrics display."""
        return html.Div([
            html.Div([
                html.Span('Total Trades: ', style={'fontWeight': 'bold'}),
                html.Span(f"{metrics['total_trades']}")
            ], style={'marginBottom': '10px'}),

            html.Div([
                html.Span('Win Rate: ', style={'fontWeight': 'bold'}),
                html.Span(f"{metrics['win_rate']:.1f}%",
                         style={'color': 'green' if metrics['win_rate'] >= 50 else 'red'})
            ], style={'marginBottom': '10px'}),

            html.Div([
                html.Span('Avg Win: ', style={'fontWeight': 'bold'}),
                html.Span(f"${metrics['avg_win']:,.2f}", style={'color': 'green'})
            ], style={'marginBottom': '10px'}),

            html.Div([
                html.Span('Avg Loss: ', style={'fontWeight': 'bold'}),
                html.Span(f"${metrics['avg_loss']:,.2f}", style={'color': 'red'})
            ], style={'marginBottom': '10px'}),

            html.Div([
                html.Span('Profit Factor: ', style={'fontWeight': 'bold'}),
                html.Span(f"{metrics['profit_factor']:.2f}",
                         style={'color': 'green' if metrics['profit_factor'] > 1 else 'red'})
            ]),
        ], style={'backgroundColor': '#f8f9fa', 'padding': '20px', 'borderRadius': '8px'})

    def _get_circuit_breaker_status(self) -> Dict:
        """Get circuit breaker and risk status from database."""
        try:
            # Check for circuit breaker events
            query = """
                SELECT event_type, severity, timestamp, description
                FROM risk_events
                WHERE event_type LIKE '%CIRCUIT_BREAKER%' OR event_type LIKE '%HALT%'
                ORDER BY timestamp DESC
                LIMIT 1
            """
            breaker_events = self.db.query(query)

            # Calculate current drawdown from portfolio data
            portfolio_data = self._get_portfolio_data()
            current_drawdown = portfolio_data.get('total_pnl_pct', 0)

            # Get today's P&L
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            daily_pnl_query = """
                SELECT SUM(CASE WHEN side = 'SELL' THEN quantity * price ELSE -quantity * price END) as pnl
                FROM trades
                WHERE timestamp >= ?
            """
            daily_result = self.db.query(daily_pnl_query, (today_start.isoformat(),))
            daily_pnl = daily_result[0][0] if daily_result and daily_result[0][0] else 0

            # Determine circuit breaker status
            is_active = False
            breaker_reason = None

            if breaker_events:
                # Check if the most recent breaker event indicates active halt
                last_event = breaker_events[0]
                if 'TRIGGERED' in str(last_event[3]).upper() or last_event[1] == 'CRITICAL':
                    is_active = True
                    breaker_reason = last_event[3]

            # Also check against risk limits
            daily_limit = -0.05 * self.initial_capital  # -5%
            drawdown_limit = -0.20  # -20%

            if daily_pnl < daily_limit:
                is_active = True
                breaker_reason = f"Daily loss limit exceeded: ${daily_pnl:,.2f}"
            elif current_drawdown < drawdown_limit * 100:
                is_active = True
                breaker_reason = f"Max drawdown exceeded: {current_drawdown:.1f}%"

            return {
                'is_active': is_active,
                'reason': breaker_reason,
                'current_drawdown': current_drawdown,
                'daily_pnl': daily_pnl,
                'daily_limit': daily_limit,
                'drawdown_limit': drawdown_limit * 100
            }

        except Exception as e:
            logger.error(f"Error getting circuit breaker status: {e}")
            return {
                'is_active': False,
                'reason': None,
                'current_drawdown': 0,
                'daily_pnl': 0,
                'daily_limit': -5000,
                'drawdown_limit': -20
            }

    def _build_circuit_breaker_display(self, data: Dict):
        """Build circuit breaker status display."""
        is_active = data.get('is_active', False)

        # Status indicator
        if is_active:
            status_style = {
                'backgroundColor': '#dc3545',
                'color': 'white',
                'padding': '10px 20px',
                'borderRadius': '8px',
                'fontWeight': 'bold',
                'display': 'inline-block'
            }
            status_text = '⛔ TRADING HALTED'
        else:
            status_style = {
                'backgroundColor': '#28a745',
                'color': 'white',
                'padding': '10px 20px',
                'borderRadius': '8px',
                'fontWeight': 'bold',
                'display': 'inline-block'
            }
            status_text = '✅ TRADING ACTIVE'

        # Build the display
        children = [
            # Status indicator
            html.Div([
                html.Span(status_text, style=status_style),
            ], style={'marginBottom': '15px'}),
        ]

        # Add reason if halted
        if is_active and data.get('reason'):
            children.append(
                html.Div([
                    html.Span('Reason: ', style={'fontWeight': 'bold', 'color': '#dc3545'}),
                    html.Span(data['reason'], style={'color': '#dc3545'})
                ], style={'marginBottom': '10px'})
            )

        # Risk metrics row
        drawdown_color = 'red' if data['current_drawdown'] < -10 else ('orange' if data['current_drawdown'] < -5 else 'green')
        daily_pnl_color = 'red' if data['daily_pnl'] < 0 else 'green'

        children.append(
            html.Div([
                # Current Drawdown
                html.Div([
                    html.Span('Current Drawdown: ', style={'fontWeight': 'bold'}),
                    html.Span(f"{data['current_drawdown']:.2f}%", style={'color': drawdown_color}),
                    html.Span(f" (Limit: {data['drawdown_limit']:.0f}%)", style={'color': '#666', 'fontSize': '12px'}),
                ], style={'display': 'inline-block', 'marginRight': '40px'}),

                # Daily P&L
                html.Div([
                    html.Span("Today's P&L: ", style={'fontWeight': 'bold'}),
                    html.Span(f"${data['daily_pnl']:,.2f}", style={'color': daily_pnl_color}),
                    html.Span(f" (Limit: ${data['daily_limit']:,.0f})", style={'color': '#666', 'fontSize': '12px'}),
                ], style={'display': 'inline-block'}),
            ], style={'backgroundColor': '#f8f9fa', 'padding': '15px', 'borderRadius': '8px'})
        )

        return html.Div(children)

    def _build_risk_alerts_table(self, alerts: List) -> html.Div:
        """Build risk alerts table from risk events."""
        if not alerts:
            return html.P('No risk alerts', style={'color': '#666', 'fontStyle': 'italic'})

        try:
            # Format alerts for table
            table_data = []
            for alert in alerts[:5]:  # Show last 5 alerts
                # alert is a tuple: (timestamp, event_type, severity, symbol, description, resolved)
                timestamp = alert[0] if isinstance(alert, (list, tuple)) else alert.get('timestamp', '')
                event_type = alert[1] if isinstance(alert, (list, tuple)) else alert.get('event_type', '')
                severity = alert[2] if isinstance(alert, (list, tuple)) else alert.get('severity', '')
                symbol = alert[3] if isinstance(alert, (list, tuple)) else alert.get('symbol', '')
                description = alert[4] if isinstance(alert, (list, tuple)) else alert.get('description', '')

                # Parse timestamp
                try:
                    time_str = datetime.fromisoformat(timestamp).strftime('%H:%M:%S')
                except:
                    time_str = str(timestamp)[:8]

                table_data.append({
                    'Time': time_str,
                    'Type': event_type,
                    'Severity': severity,
                    'Symbol': symbol or 'N/A',
                    'Description': description[:50] + '...' if len(str(description)) > 50 else description
                })

            df = pd.DataFrame(table_data)

            # Define severity colors
            severity_colors = {
                'CRITICAL': '#dc3545',
                'HIGH': '#fd7e14',
                'MEDIUM': '#ffc107',
                'LOW': '#17a2b8'
            }

            return dash_table.DataTable(
                data=df.to_dict('records'),
                columns=[{'name': i, 'id': i} for i in df.columns],
                style_cell={'textAlign': 'left', 'padding': '8px', 'fontSize': '13px'},
                style_header={'backgroundColor': '#dc3545', 'color': 'white', 'fontWeight': 'bold'},
                style_data_conditional=[
                    {'if': {'row_index': 'odd'}, 'backgroundColor': '#fff5f5'},
                    {'if': {'filter_query': '{Severity} = "CRITICAL"'}, 'backgroundColor': '#ffcccc'},
                    {'if': {'filter_query': '{Severity} = "HIGH"'}, 'backgroundColor': '#ffe4cc'},
                ]
            )

        except Exception as e:
            logger.error(f"Error building risk alerts table: {e}")
            return html.P(f'Error loading alerts: {e}', style={'color': 'red'})

    def run(self, host: str = '127.0.0.1', port: int = 8050, debug: bool = False):
        """
        Run the dashboard server.

        Args:
            host: Host address
            port: Port number
            debug: Enable debug mode
        """
        logger.info(f"Starting dashboard on http://{host}:{port}")
        print(f"\n{'='*60}")
        print(f"🚀 QuantSage Dashboard Starting...")
        print(f"{'='*60}")
        print(f"\n📊 Dashboard URL: http://{host}:{port}")
        print(f"🔄 Auto-refresh: Every {self.refresh_interval/1000:.0f} seconds")
        print(f"\n⚠️  Press CTRL+C to stop the server\n")

        self.app.run(host=host, port=port, debug=debug)


def create_dashboard(db_path: str = 'data/paper_trading.db',
                     refresh_interval: int = 5000) -> TradingDashboard:
    """
    Create and return dashboard instance.

    Args:
        db_path: Path to trading database
        refresh_interval: Auto-refresh interval in milliseconds

    Returns:
        TradingDashboard instance
    """
    return TradingDashboard(db_path=db_path, refresh_interval=refresh_interval)
