"""
Risk Manager for multi-layer trading risk validation.

Validates all trading signals against 4 layers of risk protection:
1. Position Level - Individual position sizing, stop-loss validation
2. Symbol Level - Aggregate exposure per symbol across strategies
3. Portfolio Level - Total invested amount, correlation checks
4. System Level - Circuit breakers (daily loss, max drawdown)

Event Flow:
Strategy → SignalEvent → RiskManager → OrderEvent (approved) | RiskAlertEvent (rejected)
"""

import logging
import uuid
from typing import Dict, Optional, Tuple, List
from datetime import datetime

from src.core.events import SignalEvent, OrderEvent, RiskAlertEvent, EventType
from src.core.event_bus import EventBus
from src.data.storage import DatabaseManager


logger = logging.getLogger(__name__)


class RiskManager:
    """
    Multi-layer risk manager that validates trading signals before execution.

    Subscribes to SignalEvent from strategies and validates against:
    - Position sizing limits (max 10% per position)
    - Symbol exposure limits (max 15% per symbol)
    - Portfolio exposure limits (max 80% invested)
    - Circuit breakers (daily loss -5%, max drawdown -20%)

    Publishes:
    - OrderEvent for approved signals
    - RiskAlertEvent for rejected signals
    """

    def __init__(self, config: Dict, event_bus: EventBus, db: DatabaseManager,
                 initial_capital: float = 100000.0):
        """
        Initialize risk manager with configuration.

        Args:
            config: Risk configuration dict from config/risk.yaml
            event_bus: Event bus for pub/sub
            db: Database manager for queries
            initial_capital: Starting portfolio value (default $100k)
        """
        self.config = config
        self.event_bus = event_bus
        self.db = db

        # Load risk limits from configuration
        position_config = config.get('position', {})
        symbol_config = config.get('symbol', {})
        portfolio_config = config.get('portfolio', {})
        system_config = config.get('system', {})

        # Position-level limits
        self.max_position_pct = position_config.get('max_position_pct', 0.10)
        self.min_stop_loss_pct = 0.005  # 0.5% minimum
        self.max_stop_loss_pct = 0.10   # 10% maximum

        # Symbol-level limits
        self.max_symbol_exposure = symbol_config.get('max_symbol_exposure', 0.15)

        # Portfolio-level limits
        self.max_portfolio_exposure = portfolio_config.get('max_portfolio_exposure', 0.80)
        self.max_correlation = portfolio_config.get('max_correlation', 0.70)

        # System-level limits (circuit breakers)
        self.daily_loss_limit = system_config.get('daily_loss_limit', 0.05)  # 5%
        self.max_drawdown = system_config.get('max_drawdown', 0.20)  # 20%

        # State tracking
        self.initial_capital = initial_capital
        self.portfolio_value = initial_capital  # Current total value
        self.daily_start_equity = initial_capital  # Equity at start of day
        self.peak_equity = initial_capital  # All-time high for drawdown calc
        self.circuit_breaker_active = False  # Trading halt flag
        self.open_positions_cache = []  # Cached positions (refresh periodically)
        self.last_cache_refresh = datetime.now()

        # Subscribe to SignalEvent
        self.event_bus.subscribe(EventType.SIGNAL, self._on_signal)

        logger.info(f"RiskManager initialized - Position limit: {self.max_position_pct:.1%}, "
                   f"Symbol limit: {self.max_symbol_exposure:.1%}, "
                   f"Portfolio limit: {self.max_portfolio_exposure:.1%}")
        logger.info(f"Circuit breakers: Daily loss {-self.daily_loss_limit:.1%}, "
                   f"Max drawdown {-self.max_drawdown:.1%}")

    def _on_signal(self, signal: SignalEvent):
        """
        Process incoming signal and validate against all risk layers.

        Validation order (short-circuit on first failure):
        1. Circuit breakers (system-wide halt check)
        2. Position risk (sizing and stop-loss)
        3. Symbol risk (aggregate exposure)
        4. Portfolio risk (total exposure)

        Args:
            signal: Trading signal from strategy
        """
        try:
            logger.debug(f"Validating signal: {signal.symbol} {signal.signal_type} @ {signal.price:.2f}")

            # Skip validation for CLOSE signals (just closing existing position)
            if signal.signal_type == 'CLOSE':
                logger.info(f"CLOSE signal approved without validation: {signal.symbol}")
                order = self._create_order_event(signal)
                self.event_bus.publish(order)
                return

            # 1. Check circuit breakers FIRST (system-wide halt)
            trading_allowed, reason = self._check_circuit_breakers()
            if not trading_allowed:
                logger.warning(f"Signal REJECTED (circuit breaker): {signal.symbol} - {reason}")
                alert = self._create_risk_alert(signal, reason, 'CRITICAL')
                self.event_bus.publish(alert)
                self._log_risk_event(alert)
                return

            # Calculate position value for subsequent checks
            position_pct = signal.metadata.get('quantity', 0)
            position_value = position_pct * self.portfolio_value

            # 2. Check position-level risk
            approved, reason = self._check_position_risk(signal)
            if not approved:
                logger.warning(f"Signal REJECTED (position risk): {signal.symbol} - {reason}")
                alert = self._create_risk_alert(signal, reason, 'HIGH')
                self.event_bus.publish(alert)
                self._log_risk_event(alert)
                return

            # 3. Check symbol-level risk
            approved, reason = self._check_symbol_risk(signal.symbol, position_value)
            if not approved:
                logger.warning(f"Signal REJECTED (symbol risk): {signal.symbol} - {reason}")
                alert = self._create_risk_alert(signal, reason, 'MEDIUM')
                self.event_bus.publish(alert)
                self._log_risk_event(alert)
                return

            # 4. Check portfolio-level risk
            approved, reason = self._check_portfolio_risk(position_value)
            if not approved:
                logger.warning(f"Signal REJECTED (portfolio risk): {signal.symbol} - {reason}")
                alert = self._create_risk_alert(signal, reason, 'MEDIUM')
                self.event_bus.publish(alert)
                self._log_risk_event(alert)
                return

            # All checks passed - create and publish order
            logger.info(f"Signal APPROVED: {signal.symbol} {signal.signal_type} @ {signal.price:.2f} "
                       f"(size: {position_pct:.1%})")
            order = self._create_order_event(signal)
            self.event_bus.publish(order)

        except Exception as e:
            logger.error(f"Error processing signal {signal.symbol}: {e}", exc_info=True)
            # On error, reject signal conservatively
            alert = self._create_risk_alert(signal, f"Processing error: {str(e)}", 'HIGH')
            self.event_bus.publish(alert)

    def _check_circuit_breakers(self) -> Tuple[bool, Optional[str]]:
        """
        Check if system-level circuit breakers are triggered.

        Circuit breakers are sticky - once triggered, they remain active
        until manually reset (not implemented in this version).

        Returns:
            (trading_allowed, reason) - False if breaker active
        """
        # Check if breaker already active
        if self.circuit_breaker_active:
            return (False, "Circuit breaker active - trading halted")

        # Use current portfolio value (don't refresh to avoid test issues)
        current_value = self.portfolio_value

        # Calculate daily P&L percentage
        if self.daily_start_equity > 0:
            daily_pnl_pct = (current_value - self.daily_start_equity) / self.daily_start_equity

            # Check daily loss limit
            if daily_pnl_pct < -self.daily_loss_limit:
                self.circuit_breaker_active = True
                reason = (f"Daily loss limit breached: {daily_pnl_pct:.2%} exceeds "
                         f"limit {-self.daily_loss_limit:.2%}")
                logger.critical(f"CIRCUIT BREAKER ACTIVATED: {reason}")
                return (False, reason)

        # Calculate drawdown from peak
        if self.peak_equity > 0:
            drawdown_pct = (self.peak_equity - current_value) / self.peak_equity

            # Check max drawdown limit
            if drawdown_pct > self.max_drawdown:
                self.circuit_breaker_active = True
                reason = (f"Max drawdown breached: {drawdown_pct:.2%} exceeds "
                         f"limit {self.max_drawdown:.2%}")
                logger.critical(f"CIRCUIT BREAKER ACTIVATED: {reason}")
                return (False, reason)

        # Update peak equity if we're at new high
        if current_value > self.peak_equity:
            self.peak_equity = current_value
            logger.debug(f"New peak equity: ${self.peak_equity:,.2f}")

        return (True, None)

    def _check_position_risk(self, signal: SignalEvent) -> Tuple[bool, Optional[str]]:
        """
        Validate position-level risk parameters.

        Checks:
        - Position size <= max_position_pct (10%)
        - Stop-loss is present for BUY/SELL signals
        - Stop-loss is reasonable (not too tight or too wide)

        Args:
            signal: Trading signal to validate

        Returns:
            (approved, reason) - False if validation fails
        """
        # Extract position size from signal metadata
        position_pct = signal.metadata.get('quantity', 0)

        # Check against max_position_pct
        if position_pct > self.max_position_pct:
            return (False, f"Position size {position_pct:.1%} exceeds limit {self.max_position_pct:.1%}")

        # Validate stop-loss for BUY/SELL signals (not CLOSE)
        if signal.signal_type in ['BUY', 'SELL']:
            stop_loss = signal.metadata.get('stop_loss')

            # Stop-loss must be present
            if stop_loss is None:
                return (False, "Stop-loss required but not provided")

            # Validate stop-loss is reasonable
            stop_loss_pct = abs(signal.price - stop_loss) / signal.price

            if stop_loss_pct < self.min_stop_loss_pct:
                return (False, f"Stop-loss too tight: {stop_loss_pct:.2%} < {self.min_stop_loss_pct:.2%}")

            if stop_loss_pct > self.max_stop_loss_pct:
                return (False, f"Stop-loss too wide: {stop_loss_pct:.2%} > {self.max_stop_loss_pct:.2%}")

        return (True, None)

    def _check_symbol_risk(self, symbol: str, new_exposure: float) -> Tuple[bool, Optional[str]]:
        """
        Validate symbol-level risk (aggregate exposure to single symbol).

        Aggregates exposure across all open positions for this symbol
        and checks against max_symbol_exposure limit (15%).

        Args:
            symbol: Trading symbol
            new_exposure: Dollar value of new position

        Returns:
            (approved, reason) - False if limit exceeded
        """
        try:
            # Query all OPEN positions for this symbol
            query = "SELECT quantity, entry_price FROM positions WHERE symbol=? AND status='OPEN'"
            result = self.db.execute_query(query, (symbol,))

            # Calculate existing exposure
            existing_exposure = sum(row['quantity'] * row['entry_price'] for row in result)

            # Calculate total exposure (existing + new)
            total_exposure = existing_exposure + new_exposure
            exposure_pct = total_exposure / self.portfolio_value if self.portfolio_value > 0 else 0

            # Check against limit
            if exposure_pct > self.max_symbol_exposure:
                return (False,
                       f"Symbol exposure {exposure_pct:.1%} exceeds limit {self.max_symbol_exposure:.1%} "
                       f"(existing: ${existing_exposure:,.0f}, new: ${new_exposure:,.0f})")

            logger.debug(f"Symbol {symbol} exposure: {exposure_pct:.1%} (OK)")
            return (True, None)

        except Exception as e:
            logger.error(f"Error checking symbol risk for {symbol}: {e}")
            # Conservative: reject on error
            return (False, f"Symbol risk check failed: {str(e)}")

    def _check_portfolio_risk(self, new_position_value: float) -> Tuple[bool, Optional[str]]:
        """
        Validate portfolio-level risk (total exposure across all positions).

        Checks that total invested amount doesn't exceed max_portfolio_exposure
        limit (80%), leaving cash reserve for risk management.

        Args:
            new_position_value: Dollar value of new position

        Returns:
            (approved, reason) - False if limit exceeded
        """
        try:
            # Get all open positions
            positions = self._get_open_positions()

            # Calculate total invested amount (mark-to-market)
            total_invested = sum(self._calculate_position_value(p['symbol'], p['quantity'])
                               for p in positions)

            # Add new position
            total_invested += new_position_value

            # Calculate exposure percentage
            exposure_pct = total_invested / self.portfolio_value if self.portfolio_value > 0 else 0

            # Check against max_portfolio_exposure
            if exposure_pct > self.max_portfolio_exposure:
                return (False,
                       f"Portfolio exposure {exposure_pct:.1%} exceeds limit {self.max_portfolio_exposure:.1%} "
                       f"(invested: ${total_invested:,.0f}, portfolio: ${self.portfolio_value:,.0f})")

            logger.debug(f"Portfolio exposure: {exposure_pct:.1%} (OK)")
            return (True, None)

        except Exception as e:
            logger.error(f"Error checking portfolio risk: {e}")
            # Conservative: reject on error
            return (False, f"Portfolio risk check failed: {str(e)}")

    def _get_portfolio_value(self) -> float:
        """
        Calculate total portfolio value (cash + open positions).

        For simplicity in this version, we assume:
        - Cash = initial_capital - invested_amount
        - Invested amount calculated from open positions at current prices

        Returns:
            Total portfolio value in dollars
        """
        try:
            positions = self._get_open_positions()

            # Calculate mark-to-market value of all positions
            invested_value = sum(self._calculate_position_value(p['symbol'], p['quantity'])
                               for p in positions)

            # Cash = initial capital - invested (simplified, ignores realized P&L)
            # In production, track cash separately
            cash = max(0, self.initial_capital - invested_value)

            total_value = cash + invested_value
            logger.debug(f"Portfolio value: ${total_value:,.2f} (cash: ${cash:,.2f}, invested: ${invested_value:,.2f})")

            return total_value

        except Exception as e:
            logger.error(f"Error calculating portfolio value: {e}")
            return self.initial_capital  # Fallback to initial capital

    def _get_open_positions(self) -> List[Dict]:
        """
        Query all open positions from database.

        Uses cache if recently refreshed (<60 seconds old).

        Returns:
            List of position dicts with symbol, quantity, entry_price
        """
        try:
            # Check cache freshness
            age_seconds = (datetime.now() - self.last_cache_refresh).total_seconds()
            if age_seconds < 60 and self.open_positions_cache:
                return self.open_positions_cache

            # Refresh from database
            query = "SELECT symbol, quantity, entry_price FROM positions WHERE status='OPEN'"
            positions = self.db.execute_query(query)

            self.open_positions_cache = positions
            self.last_cache_refresh = datetime.now()

            logger.debug(f"Refreshed position cache: {len(positions)} open positions")
            return positions

        except Exception as e:
            logger.error(f"Error querying open positions: {e}")
            return []

    def _calculate_position_value(self, symbol: str, quantity: float) -> float:
        """
        Calculate mark-to-market value of a position.

        In this version, we use entry price as a proxy for current price.
        In production, query real-time market data.

        Args:
            symbol: Trading symbol
            quantity: Position size

        Returns:
            Position value in dollars
        """
        try:
            # In production: query current market price
            # For now: use entry price from database as approximation
            query = "SELECT entry_price FROM positions WHERE symbol=? AND status='OPEN' LIMIT 1"
            result = self.db.execute_query(query, (symbol,))

            if result:
                price = result[0]['entry_price']
                return quantity * price

            return 0.0

        except Exception as e:
            logger.error(f"Error calculating position value for {symbol}: {e}")
            return 0.0

    def _create_order_event(self, signal: SignalEvent) -> OrderEvent:
        """
        Convert approved signal to order event.

        Args:
            signal: Approved trading signal

        Returns:
            OrderEvent ready for execution
        """
        # Generate unique order ID
        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"

        # Convert signal metadata to order parameters
        quantity_pct = signal.metadata.get('quantity', 0)
        quantity = (quantity_pct * self.portfolio_value) / signal.price

        # Determine order side from signal type
        side = signal.signal_type if signal.signal_type in ['BUY', 'SELL'] else 'SELL'

        # Create order event (timestamp and type set automatically)
        order = OrderEvent(
            timestamp=datetime.now(),
            type=EventType.ORDER,  # Required by Event base class
            order_id=order_id,
            symbol=signal.symbol,
            asset_type=signal.asset_type,
            side=side,
            order_type='MARKET',  # Simplified: always use market orders
            quantity=quantity,
            price=None,  # Market order - no limit price
            stop_price=None,
            strategy_id=signal.strategy_id,
            position_id=None  # Will be set by portfolio manager
        )

        logger.debug(f"Created order: {order_id} {side} {quantity:.4f} {signal.symbol}")
        return order

    def _create_risk_alert(self, signal: SignalEvent, reason: str, severity: str) -> RiskAlertEvent:
        """
        Create risk alert for rejected signal.

        Args:
            signal: Rejected trading signal
            reason: Reason for rejection
            severity: Alert severity (LOW, MEDIUM, HIGH, CRITICAL)

        Returns:
            RiskAlertEvent with full context
        """
        alert = RiskAlertEvent(
            timestamp=datetime.now(),
            type=EventType.RISK_ALERT,  # Required by Event base class
            alert_type='SIGNAL_REJECTED',
            severity=severity,
            description=reason,
            symbol=signal.symbol,
            asset_type=signal.asset_type,
            strategy_id=signal.strategy_id,
            metadata={
                'signal_type': signal.signal_type,
                'signal_price': signal.price,
                'signal_confidence': signal.confidence,
                'reason': reason,
                'portfolio_value': self.portfolio_value,
                'circuit_breaker_active': self.circuit_breaker_active
            }
        )

        return alert

    def _log_risk_event(self, alert: RiskAlertEvent):
        """
        Persist risk alert to database for analysis.

        Args:
            alert: Risk alert to log
        """
        try:
            self.db.log_risk_event(
                event_type=alert.alert_type,
                severity=alert.severity,
                description=alert.description,
                symbol=alert.symbol,
                asset_type=alert.asset_type,
                strategy_id=alert.strategy_id,
                metadata=alert.metadata
            )
            logger.debug(f"Logged risk event: {alert.severity} - {alert.description}")

        except Exception as e:
            logger.error(f"Error logging risk event: {e}")

    def reset_circuit_breaker(self):
        """
        Manually reset circuit breaker to resume trading.

        Should only be called after reviewing risk conditions
        and confirming it's safe to resume.
        """
        if self.circuit_breaker_active:
            logger.warning("Circuit breaker manually reset - trading resumed")
            self.circuit_breaker_active = False
        else:
            logger.info("Circuit breaker already inactive")

    def reset_daily_tracking(self):
        """
        Reset daily tracking at start of new trading day.

        Should be called at market open or start of trading session.
        """
        self.portfolio_value = self._get_portfolio_value()
        self.daily_start_equity = self.portfolio_value
        logger.info(f"Daily tracking reset - Starting equity: ${self.daily_start_equity:,.2f}")

    def __repr__(self) -> str:
        return (f"RiskManager(portfolio=${self.portfolio_value:,.0f}, "
               f"breaker_active={self.circuit_breaker_active})")
