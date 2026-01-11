"""
Portfolio Manager for Backtesting.

Tracks positions, calculates P&L, and manages cash.
"""

import logging
from datetime import datetime
from typing import Dict, Optional

from src.core.events import EventType, FillEvent, PositionUpdateEvent
from src.core.event_bus import EventBus
from src.data.storage import DatabaseManager

logger = logging.getLogger(__name__)


class PortfolioManager:
    """
    Portfolio manager for tracking positions and calculating P&L in backtests.

    Features:
    - Position lifecycle management (open/close)
    - Realized P&L calculation (on close)
    - Unrealized P&L calculation (mark-to-market)
    - Cash balance tracking
    - Database persistence
    """

    def __init__(self, event_bus: EventBus, db: DatabaseManager,
                 initial_cash: float):
        """
        Initialize portfolio manager.

        Args:
            event_bus: EventBus instance for subscribing/publishing
            db: DatabaseManager for persisting positions
            initial_cash: Starting cash balance
        """
        self.event_bus = event_bus
        self.db = db
        self.cash = initial_cash

        # Track open positions (symbol -> position_id)
        self.positions = {}

        # Subscribe to FillEvent
        self.event_bus.subscribe(EventType.FILL, self._on_fill)

        logger.info(f"PortfolioManager initialized with ${initial_cash:,.2f} cash")

    def _on_fill(self, fill: FillEvent):
        """
        Process fill and update positions.

        Steps:
        1. Check if opening or closing position
        2. If opening: Create new position, deduct cash
        3. If closing: Calculate realized P&L, add cash, update position
        4. Store in database
        5. Publish PositionUpdateEvent

        Args:
            fill: FillEvent to process
        """
        symbol = fill.symbol

        # Check for existing open position
        existing_position = self._get_open_position(symbol)

        if existing_position is None:
            # Opening new position
            self._open_position(fill)
        else:
            # Closing or modifying existing position
            position_side = existing_position['side']

            # Determine if closing (opposite side)
            is_closing = (position_side == 'LONG' and fill.side == 'SELL') or \
                         (position_side == 'SHORT' and fill.side == 'BUY')

            if is_closing:
                self._close_position(existing_position, fill)
            else:
                # Adding to position (same side)
                self._add_to_position(existing_position, fill)

    def _get_open_position(self, symbol: str) -> Optional[Dict]:
        """
        Get open position for symbol.

        Args:
            symbol: Symbol to check

        Returns:
            Position dict or None if no open position
        """
        if symbol in self.positions:
            position_id = self.positions[symbol]
            # Query database for position details
            position = self.db.query(
                "SELECT * FROM positions WHERE id = ? AND status = 'OPEN'",
                (position_id,)
            )
            if position:
                return position[0]

        return None

    def _open_position(self, fill: FillEvent):
        """
        Open new position.

        Args:
            fill: FillEvent that opens the position
        """
        # Deduct cash (buy) or add cash (short sell)
        if fill.side == 'BUY':
            cash_change = -(fill.quantity * fill.price + fill.commission)
        else:  # SHORT
            cash_change = (fill.quantity * fill.price - fill.commission)

        self.cash += cash_change

        # Create position in database
        position_id = self.db.create_position(
            symbol=fill.symbol,
            asset_type=fill.asset_type,
            side='LONG' if fill.side == 'BUY' else 'SHORT',
            quantity=fill.quantity,
            entry_price=fill.price,
            entry_time=fill.timestamp,
            strategy_id=fill.metadata.get('strategy_id', 'unknown'),
            metadata={'entry_commission': fill.commission}
        )

        # Cache position
        self.positions[fill.symbol] = position_id

        # Publish update
        self._publish_position_update(position_id, 'OPEN')

        logger.info(f"Opened {fill.side} position: {fill.symbol} {fill.quantity:.4f} @ ${fill.price:.2f}")

    def _close_position(self, position: Dict, fill: FillEvent):
        """
        Close position and calculate realized P&L.

        Args:
            position: Position dict from database
            fill: FillEvent that closes the position
        """
        # Calculate realized P&L
        realized_pnl = self._calculate_realized_pnl(position, fill)

        # Add cash back
        if fill.side == 'SELL':  # Closing LONG
            cash_change = (fill.quantity * fill.price - fill.commission)
        else:  # Closing SHORT
            cash_change = -(fill.quantity * fill.price + fill.commission)

        self.cash += cash_change

        # Update position in database
        self.db.update_position(
            position_id=position['id'],
            exit_price=fill.price,
            exit_time=fill.timestamp,
            pnl_realized=realized_pnl,
            status='CLOSED'
        )

        # Remove from cache
        if fill.symbol in self.positions:
            del self.positions[fill.symbol]

        # Publish update
        self._publish_position_update(position['id'], 'CLOSED', realized_pnl)

        pnl_pct = (realized_pnl / (position['entry_price'] * position['quantity'])) * 100
        logger.info(f"Closed position: {fill.symbol} P&L: ${realized_pnl:+,.2f} ({pnl_pct:+.2f}%)")

    def _add_to_position(self, position: Dict, fill: FillEvent):
        """
        Add to existing position (same side).

        This updates the position quantity and average entry price.

        Args:
            position: Existing position dict
            fill: FillEvent that adds to the position
        """
        # Calculate new average entry price
        existing_cost = position['quantity'] * position['entry_price']
        new_cost = fill.quantity * fill.price
        total_quantity = position['quantity'] + fill.quantity
        new_avg_price = (existing_cost + new_cost) / total_quantity

        # Deduct cash
        if fill.side == 'BUY':
            cash_change = -(fill.quantity * fill.price + fill.commission)
        else:  # SHORT
            cash_change = (fill.quantity * fill.price - fill.commission)

        self.cash += cash_change

        # Update position in database
        self.db.update_position(
            position_id=position['id'],
            quantity=total_quantity,
            entry_price=new_avg_price
        )

        logger.info(f"Added to position: {fill.symbol} +{fill.quantity:.4f} @ ${fill.price:.2f} (new avg: ${new_avg_price:.2f})")

    def _calculate_realized_pnl(self, position: Dict, fill: FillEvent) -> float:
        """
        Calculate realized P&L for closing position.

        LONG: (exit_price - entry_price) * quantity - total_commission
        SHORT: (entry_price - exit_price) * quantity - total_commission

        Args:
            position: Position dict
            fill: FillEvent

        Returns:
            Realized P&L in dollars
        """
        entry_price = position['entry_price']
        exit_price = fill.price
        quantity = min(position['quantity'], fill.quantity)

        # Get entry commission from metadata (if available)
        import json
        metadata = json.loads(position.get('metadata', '{}')) if position.get('metadata') else {}
        entry_commission = metadata.get('entry_commission', 0)
        exit_commission = fill.commission
        total_commission = entry_commission + exit_commission

        if position['side'] == 'LONG':
            pnl = (exit_price - entry_price) * quantity - total_commission
        else:  # SHORT
            pnl = (entry_price - exit_price) * quantity - total_commission

        return pnl

    def _calculate_unrealized_pnl(self, position: Dict, current_price: float) -> float:
        """
        Calculate unrealized P&L for open position (mark-to-market).

        LONG: (current_price - entry_price) * quantity
        SHORT: (entry_price - current_price) * quantity

        Args:
            position: Position dict
            current_price: Current market price

        Returns:
            Unrealized P&L in dollars
        """
        entry_price = position['entry_price']
        quantity = position['quantity']

        if position['side'] == 'LONG':
            unrealized_pnl = (current_price - entry_price) * quantity
        else:  # SHORT
            unrealized_pnl = (entry_price - current_price) * quantity

        return unrealized_pnl

    def get_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """
        Calculate total portfolio value (cash + unrealized P&L).

        Args:
            current_prices: Dict of symbol -> current price

        Returns:
            Total portfolio value
        """
        # Start with cash
        total_value = self.cash

        # Add unrealized P&L from open positions
        open_positions = self.db.get_open_positions()

        for position in open_positions:
            symbol = position['symbol']
            if symbol not in current_prices:
                logger.warning(f"No current price for {symbol}, using entry price")
                current_price = position['entry_price']
            else:
                current_price = current_prices[symbol]

            # Calculate unrealized P&L
            unrealized_pnl = self._calculate_unrealized_pnl(position, current_price)

            # For LONG: value = current_price * quantity
            # For SHORT: value is reflected in unrealized P&L (already have cash from short sale)
            if position['side'] == 'LONG':
                total_value += current_price * position['quantity']
            else:  # SHORT
                total_value += unrealized_pnl

        return total_value

    def _publish_position_update(self, position_id: int, status: str,
                                 realized_pnl: float = 0.0):
        """
        Publish PositionUpdateEvent.

        Args:
            position_id: Position ID
            status: Position status ('OPEN' or 'CLOSED')
            realized_pnl: Realized P&L (for closed positions)
        """
        # Query position details
        position = self.db.query(
            "SELECT * FROM positions WHERE id = ?",
            (position_id,)
        )

        if not position:
            logger.error(f"Position {position_id} not found")
            return

        position = position[0]

        # Create PositionUpdateEvent
        event = PositionUpdateEvent(
            timestamp=datetime.now(),
            type=EventType.POSITION_UPDATE,
            position_id=position_id,
            symbol=position['symbol'],
            asset_type=position['asset_type'],
            side=position['side'],
            quantity=position['quantity'],
            entry_price=position['entry_price'],
            exit_price=position.get('exit_price'),
            pnl_realized=realized_pnl,
            pnl_unrealized=0.0,  # Will be calculated separately
            status=status
        )

        # Publish event
        self.event_bus.publish(event)
