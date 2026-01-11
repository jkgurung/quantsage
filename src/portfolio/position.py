"""
Position class for tracking individual trading positions.

Handles position lifecycle, P&L calculations, and stop-loss/take-profit management.
"""

from datetime import datetime
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class Position:
    """
    Represents a single trading position (LONG or SHORT).

    Features:
    - Track entry/exit prices and quantities
    - Calculate realized and unrealized P&L
    - Manage stop-loss and take-profit levels
    - Support partial fills and position averaging
    - Track all commissions
    """

    def __init__(
        self,
        position_id: int,
        symbol: str,
        asset_type: str,
        side: str,  # 'LONG' or 'SHORT'
        entry_price: float,
        quantity: float,
        entry_time: datetime,
        strategy_id: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        commission: float = 0.0
    ):
        """
        Initialize a new position.

        Args:
            position_id: Unique position ID from database
            symbol: Trading pair (e.g., 'BTC/USDT')
            asset_type: 'CRYPTO' or 'STOCK'
            side: 'LONG' or 'SHORT'
            entry_price: Average entry price
            quantity: Position size
            entry_time: When position was opened
            strategy_id: Strategy that created this position
            stop_loss: Stop-loss price (optional)
            take_profit: Take-profit price (optional)
            commission: Entry commission paid
        """
        self.position_id = position_id
        self.symbol = symbol
        self.asset_type = asset_type
        self.side = side
        self.entry_price = entry_price
        self.quantity = quantity
        self.entry_time = entry_time
        self.strategy_id = strategy_id
        self.stop_loss = stop_loss
        self.take_profit = take_profit

        # Track commissions
        self.entry_commission = commission
        self.exit_commission = 0.0

        # Status
        self.status = 'OPEN'
        self.exit_price: Optional[float] = None
        self.exit_time: Optional[datetime] = None

        # P&L tracking
        self.pnl_realized = 0.0
        self.pnl_unrealized = 0.0

        logger.info(
            f"Position opened: {self.side} {self.quantity} {self.symbol} "
            f"@ ${self.entry_price:.2f} (ID: {self.position_id})"
        )

    def update_market_price(self, current_price: float) -> float:
        """
        Update unrealized P&L based on current market price.

        Args:
            current_price: Current market price

        Returns:
            Unrealized P&L
        """
        if self.status != 'OPEN':
            return 0.0

        if self.side == 'LONG':
            # LONG: profit when price goes up
            price_diff = current_price - self.entry_price
        else:
            # SHORT: profit when price goes down
            price_diff = self.entry_price - current_price

        # P&L = price difference * quantity - entry commission
        # (exit commission will be deducted on close)
        self.pnl_unrealized = (price_diff * self.quantity) - self.entry_commission

        return self.pnl_unrealized

    def close(
        self,
        exit_price: float,
        exit_time: datetime,
        commission: float = 0.0
    ) -> float:
        """
        Close the position and calculate realized P&L.

        Args:
            exit_price: Exit price
            exit_time: Exit timestamp
            commission: Exit commission

        Returns:
            Realized P&L (positive = profit, negative = loss)
        """
        if self.status == 'CLOSED':
            logger.warning(f"Position {self.position_id} already closed")
            return self.pnl_realized

        self.exit_price = exit_price
        self.exit_time = exit_time
        self.exit_commission = commission
        self.status = 'CLOSED'

        # Calculate realized P&L
        if self.side == 'LONG':
            # LONG: (exit - entry) * quantity - commissions
            price_diff = self.exit_price - self.entry_price
        else:
            # SHORT: (entry - exit) * quantity - commissions
            price_diff = self.entry_price - self.exit_price

        self.pnl_realized = (price_diff * self.quantity) - \
                           (self.entry_commission + self.exit_commission)

        self.pnl_unrealized = 0.0  # No longer unrealized

        logger.info(
            f"Position closed: {self.side} {self.quantity} {self.symbol} "
            f"@ ${self.exit_price:.2f} | P&L: ${self.pnl_realized:,.2f} "
            f"({self.get_return_pct():.2f}%)"
        )

        return self.pnl_realized

    def get_return_pct(self) -> float:
        """
        Calculate return percentage.

        Returns:
            Return as percentage (e.g., 5.2 for 5.2% gain)
        """
        if self.entry_price == 0:
            return 0.0

        cost_basis = self.entry_price * self.quantity
        if cost_basis == 0:
            return 0.0

        if self.status == 'OPEN':
            return (self.pnl_unrealized / cost_basis) * 100
        else:
            return (self.pnl_realized / cost_basis) * 100

    def should_stop_loss(self, current_price: float) -> bool:
        """
        Check if stop-loss should be triggered.

        Args:
            current_price: Current market price

        Returns:
            True if stop-loss triggered
        """
        if self.stop_loss is None or self.status != 'OPEN':
            return False

        if self.side == 'LONG':
            # LONG: stop-loss triggers when price falls below stop
            return current_price <= self.stop_loss
        else:
            # SHORT: stop-loss triggers when price rises above stop
            return current_price >= self.stop_loss

    def should_take_profit(self, current_price: float) -> bool:
        """
        Check if take-profit should be triggered.

        Args:
            current_price: Current market price

        Returns:
            True if take-profit triggered
        """
        if self.take_profit is None or self.status != 'OPEN':
            return False

        if self.side == 'LONG':
            # LONG: take-profit triggers when price rises above target
            return current_price >= self.take_profit
        else:
            # SHORT: take-profit triggers when price falls below target
            return current_price <= self.take_profit

    def update_stops(
        self,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ):
        """
        Update stop-loss and/or take-profit levels.

        Useful for trailing stops or dynamic risk management.

        Args:
            stop_loss: New stop-loss price (None = no change)
            take_profit: New take-profit price (None = no change)
        """
        if stop_loss is not None:
            old_stop = self.stop_loss
            self.stop_loss = stop_loss
            logger.info(
                f"Position {self.position_id}: Stop-loss updated "
                f"${old_stop} -> ${stop_loss}"
            )

        if take_profit is not None:
            old_tp = self.take_profit
            self.take_profit = take_profit
            logger.info(
                f"Position {self.position_id}: Take-profit updated "
                f"${old_tp} -> ${take_profit}"
            )

    def get_value(self, current_price: float) -> float:
        """
        Calculate current position value.

        For LONG: quantity * current_price
        For SHORT: original value + unrealized P&L

        Args:
            current_price: Current market price

        Returns:
            Position value in quote currency
        """
        if self.status != 'OPEN':
            return 0.0

        if self.side == 'LONG':
            # LONG positions have market value
            return self.quantity * current_price
        else:
            # SHORT positions: track as liability
            # Value = initial proceeds - current cost
            initial_proceeds = self.quantity * self.entry_price
            current_cost = self.quantity * current_price
            return initial_proceeds - current_cost

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert position to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        return {
            'position_id': self.position_id,
            'symbol': self.symbol,
            'asset_type': self.asset_type,
            'side': self.side,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time.isoformat() if self.entry_time else None,
            'exit_price': self.exit_price,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'status': self.status,
            'pnl_realized': self.pnl_realized,
            'pnl_unrealized': self.pnl_unrealized,
            'entry_commission': self.entry_commission,
            'exit_commission': self.exit_commission,
            'strategy_id': self.strategy_id,
            'return_pct': self.get_return_pct()
        }

    def __repr__(self) -> str:
        """String representation for debugging."""
        if self.status == 'OPEN':
            return (
                f"Position({self.side} {self.quantity} {self.symbol} "
                f"@ ${self.entry_price:.2f}, "
                f"unrealized P&L: ${self.pnl_unrealized:,.2f})"
            )
        else:
            return (
                f"Position({self.side} {self.quantity} {self.symbol} "
                f"@ ${self.entry_price:.2f} -> ${self.exit_price:.2f}, "
                f"P&L: ${self.pnl_realized:,.2f})"
            )
