"""
Live Portfolio Manager for real-time trading.

Converts signals to orders, tracks positions, monitors stops, and calculates P&L.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from src.core.events import (
    EventType, SignalEvent, OrderEvent, FillEvent,
    PositionUpdateEvent, MarketDataEvent
)
from src.core.event_bus import EventBus
from src.data.storage import DatabaseManager
from src.portfolio.position import Position

logger = logging.getLogger(__name__)


class PortfolioManager:
    """
    Live portfolio manager for real-time trading.

    Responsibilities:
    1. Convert SignalEvents to OrderEvents with position sizing
    2. Track open positions using Position class
    3. Monitor stop-loss and take-profit triggers
    4. Update positions on FillEvents
    5. Calculate portfolio value and P&L in real-time
    6. Publish PositionUpdateEvents

    Key Differences from Backtesting PortfolioManager:
    - Subscribes to SignalEvent (not just FillEvent)
    - Implements position sizing logic
    - Monitors market data for stop triggers
    - Handles multi-strategy coordination
    """

    def __init__(
        self,
        event_bus: EventBus,
        db: DatabaseManager,
        initial_cash: float,
        config: Optional[Dict] = None
    ):
        """
        Initialize live portfolio manager.

        Args:
            event_bus: EventBus for pub/sub
            db: DatabaseManager for persistence
            initial_cash: Starting cash balance
            config: Optional configuration dict
        """
        self.event_bus = event_bus
        self.db = db
        self.cash = initial_cash
        self.initial_cash = initial_cash

        # Configuration
        self.config = config or {}
        self.default_position_size_pct = self.config.get('default_position_size', 0.05)  # 5% of portfolio

        # Track positions: {symbol: Position}
        self.positions: Dict[str, Position] = {}

        # Track current market prices for valuation
        self.current_prices: Dict[str, float] = {}

        # Subscribe to events
        self.event_bus.subscribe(EventType.SIGNAL, self._on_signal)
        self.event_bus.subscribe(EventType.FILL, self._on_fill)
        self.event_bus.subscribe(EventType.MARKET_DATA, self._on_market_data)

        logger.info(
            f"PortfolioManager initialized: ${initial_cash:,.2f} cash, "
            f"{self.default_position_size_pct*100:.1f}% default position size"
        )

    def _on_signal(self, signal: SignalEvent):
        """
        Process trading signal and create order.

        Steps:
        1. Validate signal
        2. Calculate position size
        3. Check if we already have a position
        4. Create OrderEvent
        5. Publish order to event bus

        Args:
            signal: SignalEvent from strategy
        """
        try:
            # Validate signal
            if not self._validate_signal(signal):
                return

            symbol = signal.symbol

            # Check for existing position
            existing_position = self.positions.get(symbol)

            # Determine order side
            if signal.direction == 'LONG':
                # LONG signal
                if existing_position and existing_position.side == 'SHORT':
                    # Close SHORT position first
                    self._create_close_order(existing_position, signal)
                elif existing_position and existing_position.side == 'LONG':
                    # Already LONG, ignore or scale (for now, ignore)
                    logger.info(f"Already LONG {symbol}, ignoring signal")
                    return
                else:
                    # Open new LONG
                    self._create_open_order(signal, 'LONG')

            elif signal.direction == 'SHORT':
                # SHORT signal
                if existing_position and existing_position.side == 'LONG':
                    # Close LONG position first
                    self._create_close_order(existing_position, signal)
                elif existing_position and existing_position.side == 'SHORT':
                    # Already SHORT, ignore
                    logger.info(f"Already SHORT {symbol}, ignoring signal")
                    return
                else:
                    # Open new SHORT
                    self._create_open_order(signal, 'SHORT')

            elif signal.direction == 'EXIT':
                # EXIT signal - close position if exists
                if existing_position:
                    self._create_close_order(existing_position, signal)
                else:
                    logger.info(f"No position to exit for {symbol}")

        except Exception as e:
            logger.error(f"Error processing signal: {e}", exc_info=True)

    def _create_open_order(self, signal: SignalEvent, side: str):
        """
        Create order to open a new position.

        Args:
            signal: Trading signal
            side: 'LONG' or 'SHORT'
        """
        # Calculate position size
        quantity = self._calculate_position_size(
            signal.symbol,
            signal.price,
            signal.position_size_pct
        )

        if quantity == 0:
            logger.warning(f"Position size calculated to 0 for {signal.symbol}")
            return

        # Determine order side (BUY for LONG, SELL for SHORT)
        order_side = 'BUY' if side == 'LONG' else 'SELL'

        # Create order
        order = OrderEvent(
            timestamp=datetime.now(),
            type=EventType.ORDER,
            order_id=f"ORD-{uuid.uuid4().hex[:12].upper()}",
            symbol=signal.symbol,
            asset_type=signal.asset_type,
            side=order_side,
            order_type='MARKET',  # For now, use market orders
            quantity=quantity,
            price=None,  # Market order
            strategy_id=signal.strategy_id,
            position_id=None  # New position
        )

        # Publish order
        logger.info(
            f"Creating order: {order_side} {quantity} {signal.symbol} "
            f"(signal: {signal.direction}, strategy: {signal.strategy_id})"
        )
        self.event_bus.publish(order)

    def _create_close_order(self, position: Position, signal: SignalEvent):
        """
        Create order to close an existing position.

        Args:
            position: Position to close
            signal: Trading signal
        """
        # Determine order side (opposite of position)
        order_side = 'SELL' if position.side == 'LONG' else 'BUY'

        # Create order for full position quantity
        order = OrderEvent(
            timestamp=datetime.now(),
            type=EventType.ORDER,
            order_id=f"ORD-{uuid.uuid4().hex[:12].upper()}",
            symbol=position.symbol,
            asset_type=position.asset_type,
            side=order_side,
            order_type='MARKET',
            quantity=position.quantity,
            price=None,
            strategy_id=signal.strategy_id,
            position_id=position.position_id  # Close this position
        )

        logger.info(
            f"Creating close order: {order_side} {position.quantity} "
            f"{position.symbol} (position_id: {position.position_id})"
        )
        self.event_bus.publish(order)

    def _on_fill(self, fill: FillEvent):
        """
        Process fill and update positions.

        Steps:
        1. Determine if opening or closing
        2. Update or create Position
        3. Update cash balance
        4. Store in database
        5. Publish PositionUpdateEvent

        Args:
            fill: FillEvent from execution
        """
        try:
            symbol = fill.symbol
            existing_position = self.positions.get(symbol)

            if fill.side == 'BUY':
                if existing_position and existing_position.side == 'SHORT':
                    # Closing SHORT position
                    self._close_position(existing_position, fill)
                else:
                    # Opening LONG position
                    self._open_position(fill, 'LONG')

            elif fill.side == 'SELL':
                if existing_position and existing_position.side == 'LONG':
                    # Closing LONG position
                    self._close_position(existing_position, fill)
                else:
                    # Opening SHORT position
                    self._open_position(fill, 'SHORT')

        except Exception as e:
            logger.error(f"Error processing fill: {e}", exc_info=True)

    def _open_position(self, fill: FillEvent, side: str):
        """
        Open a new position from fill.

        Args:
            fill: FillEvent
            side: 'LONG' or 'SHORT'
        """
        # Calculate cost/proceeds
        cost = fill.quantity * fill.price + fill.commission

        # Update cash
        if side == 'LONG':
            # LONG: pay cash to buy
            self.cash -= cost
        else:
            # SHORT: receive cash from selling (minus commission)
            self.cash += (fill.quantity * fill.price - fill.commission)

        # Create position in database
        position_id = self.db.create_position(
            symbol=fill.symbol,
            asset_type=fill.asset_type,
            side=side,
            entry_price=fill.price,
            quantity=fill.quantity,
            entry_time=fill.timestamp.isoformat(),
            strategy_id=fill.metadata.get('strategy_id', 'unknown'),
            stop_loss=None,  # TODO: Get from signal
            take_profit=None
        )

        # Create Position object
        position = Position(
            position_id=position_id,
            symbol=fill.symbol,
            asset_type=fill.asset_type,
            side=side,
            entry_price=fill.price,
            quantity=fill.quantity,
            entry_time=fill.timestamp,
            strategy_id=fill.metadata.get('strategy_id', 'unknown'),
            commission=fill.commission
        )

        # Store in positions dict
        self.positions[fill.symbol] = position

        # Publish update
        self._publish_position_update(position, 'OPENED')

        logger.info(
            f"Position opened: {side} {fill.quantity} {fill.symbol} "
            f"@ ${fill.price:.2f}, cash: ${self.cash:,.2f}"
        )

    def _close_position(self, position: Position, fill: FillEvent):
        """
        Close an existing position.

        Args:
            position: Position to close
            fill: FillEvent with exit info
        """
        # Close position
        realized_pnl = position.close(
            exit_price=fill.price,
            exit_time=fill.timestamp,
            commission=fill.commission
        )

        # Update cash
        if position.side == 'LONG':
            # LONG: sell and receive cash
            proceeds = fill.quantity * fill.price - fill.commission
            self.cash += proceeds
        else:
            # SHORT: buy back and pay cash
            cost = fill.quantity * fill.price + fill.commission
            self.cash -= cost

        # Update database
        self.db.close_position(
            position_id=position.position_id,
            exit_price=fill.price,
            exit_time=fill.timestamp.isoformat(),
            pnl_realized=realized_pnl
        )

        # Remove from active positions
        del self.positions[position.symbol]

        # Publish update
        self._publish_position_update(position, 'CLOSED')

        logger.info(
            f"Position closed: {position.side} {position.quantity} "
            f"{position.symbol}, P&L: ${realized_pnl:,.2f}, cash: ${self.cash:,.2f}"
        )

    def _on_market_data(self, event: MarketDataEvent):
        """
        Update market prices and check stop-loss/take-profit triggers.

        Args:
            event: MarketDataEvent with current prices
        """
        symbol = event.symbol
        current_price = event.close

        # Update price tracking
        self.current_prices[symbol] = current_price

        # Check if we have an open position
        position = self.positions.get(symbol)
        if not position:
            return

        # Update unrealized P&L
        position.update_market_price(current_price)

        # Check for stop-loss trigger
        if position.should_stop_loss(current_price):
            logger.warning(
                f"Stop-loss triggered for {symbol}: "
                f"price ${current_price:.2f} vs stop ${position.stop_loss:.2f}"
            )
            self._trigger_stop_loss(position)

        # Check for take-profit trigger
        elif position.should_take_profit(current_price):
            logger.info(
                f"Take-profit triggered for {symbol}: "
                f"price ${current_price:.2f} vs target ${position.take_profit:.2f}"
            )
            self._trigger_take_profit(position)

    def _trigger_stop_loss(self, position: Position):
        """
        Trigger stop-loss by creating market exit order.

        Args:
            position: Position to exit
        """
        order_side = 'SELL' if position.side == 'LONG' else 'BUY'

        order = OrderEvent(
            timestamp=datetime.now(),
            type=EventType.ORDER,
            order_id=f"SL-{uuid.uuid4().hex[:12].upper()}",
            symbol=position.symbol,
            asset_type=position.asset_type,
            side=order_side,
            order_type='MARKET',
            quantity=position.quantity,
            price=None,
            strategy_id=position.strategy_id,
            position_id=position.position_id
        )

        logger.warning(f"Executing stop-loss order for {position.symbol}")
        self.event_bus.publish(order)

    def _trigger_take_profit(self, position: Position):
        """
        Trigger take-profit by creating market exit order.

        Args:
            position: Position to exit
        """
        order_side = 'SELL' if position.side == 'LONG' else 'BUY'

        order = OrderEvent(
            timestamp=datetime.now(),
            type=EventType.ORDER,
            order_id=f"TP-{uuid.uuid4().hex[:12].upper()}",
            symbol=position.symbol,
            asset_type=position.asset_type,
            side=order_side,
            order_type='MARKET',
            quantity=position.quantity,
            price=None,
            strategy_id=position.strategy_id,
            position_id=position.position_id
        )

        logger.info(f"Executing take-profit order for {position.symbol}")
        self.event_bus.publish(order)

    def _calculate_position_size(
        self,
        symbol: str,
        price: float,
        position_size_pct: Optional[float] = None
    ) -> float:
        """
        Calculate position size based on portfolio value and risk.

        Args:
            symbol: Trading symbol
            price: Current price
            position_size_pct: Position size as % of portfolio (optional)

        Returns:
            Quantity to trade
        """
        # Use signal's position size or default
        size_pct = position_size_pct if position_size_pct else self.default_position_size_pct

        # Calculate portfolio value
        portfolio_value = self.get_portfolio_value()

        # Position value = portfolio_value * size_pct
        position_value = portfolio_value * size_pct

        # Quantity = position_value / price
        quantity = position_value / price if price > 0 else 0

        logger.debug(
            f"Position sizing for {symbol}: "
            f"portfolio=${portfolio_value:,.2f}, "
            f"size={size_pct*100:.1f}%, "
            f"value=${position_value:,.2f}, "
            f"qty={quantity:.6f}"
        )

        return quantity

    def get_portfolio_value(self) -> float:
        """
        Calculate total portfolio value.

        Portfolio Value = Cash + Sum of position values

        Returns:
            Total portfolio value
        """
        # Start with cash
        total = self.cash

        # Add value of all open positions
        for symbol, position in self.positions.items():
            current_price = self.current_prices.get(symbol, position.entry_price)
            position_value = position.get_value(current_price)
            total += position_value

        return total

    def get_total_pnl(self) -> Dict[str, float]:
        """
        Calculate total realized and unrealized P&L.

        Returns:
            Dict with 'realized' and 'unrealized' P&L
        """
        unrealized = sum(pos.pnl_unrealized for pos in self.positions.values())

        # Realized P&L = current portfolio value - initial cash
        total_value = self.get_portfolio_value()
        realized = total_value - self.initial_cash

        return {
            'unrealized': unrealized,
            'realized': realized - unrealized,  # Subtract unrealized to get actual realized
            'total': realized
        }

    def _validate_signal(self, signal: SignalEvent) -> bool:
        """
        Validate signal has required fields.

        Args:
            signal: SignalEvent to validate

        Returns:
            True if valid
        """
        if not signal.symbol or not signal.direction:
            logger.warning(f"Invalid signal: missing symbol or direction")
            return False

        if signal.direction not in ['LONG', 'SHORT', 'EXIT']:
            logger.warning(f"Invalid signal direction: {signal.direction}")
            return False

        return True

    def _publish_position_update(self, position: Position, action: str):
        """
        Publish PositionUpdateEvent.

        Args:
            position: Position that was updated
            action: 'OPENED' or 'CLOSED'
        """
        event = PositionUpdateEvent(
            timestamp=datetime.now(),
            type=EventType.POSITION_UPDATE,
            position_id=position.position_id,
            symbol=position.symbol,
            side=position.side,
            quantity=position.quantity,
            entry_price=position.entry_price,
            current_price=self.current_prices.get(position.symbol, position.entry_price),
            pnl_unrealized=position.pnl_unrealized,
            pnl_realized=position.pnl_realized,
            action=action
        )

        self.event_bus.publish(event)

    def get_positions_summary(self) -> List[Dict]:
        """
        Get summary of all open positions.

        Returns:
            List of position dictionaries
        """
        return [pos.to_dict() for pos in self.positions.values()]

    def __repr__(self) -> str:
        """String representation."""
        portfolio_value = self.get_portfolio_value()
        pnl = self.get_total_pnl()
        return (
            f"PortfolioManager(cash=${self.cash:,.2f}, "
            f"value=${portfolio_value:,.2f}, "
            f"positions={len(self.positions)}, "
            f"P&L=${pnl['total']:,.2f})"
        )
