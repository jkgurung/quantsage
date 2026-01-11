"""
Order Executor for paper and live trading.

Handles order execution via exchanges (CCXT) or simulation (paper trading).
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Dict, Optional
from enum import Enum

from src.core.events import EventType, OrderEvent, FillEvent
from src.core.event_bus import EventBus
from src.data.storage import DatabaseManager

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Execution modes."""
    PAPER = "paper"  # Simulated execution
    LIVE = "live"    # Real execution via exchange


class OrderExecutor:
    """
    Execute orders via exchanges or simulation.

    Features:
    - Paper trading: Simulated fills with realistic slippage
    - Live trading: Real execution via CCXT
    - Order tracking and status updates
    - Error handling and logging
    """

    def __init__(
        self,
        event_bus: EventBus,
        db: DatabaseManager,
        mode: ExecutionMode = ExecutionMode.PAPER,
        config: Optional[Dict] = None,
        exchange=None  # CCXT exchange instance for live trading
    ):
        """
        Initialize order executor.

        Args:
            event_bus: EventBus for pub/sub
            db: DatabaseManager for persistence
            mode: PAPER or LIVE execution
            config: Optional configuration dict
            exchange: CCXT exchange instance (required for LIVE mode)
        """
        self.event_bus = event_bus
        self.db = db
        self.mode = mode
        self.config = config or {}
        self.exchange = exchange

        # Configuration
        self.slippage_pct = self.config.get('slippage_pct', 0.001)  # 0.1% default
        self.commission_pct = self.config.get('commission_pct', {
            'CRYPTO': 0.006,  # 0.6% (Coinbase taker)
            'STOCK': 0.0      # $0 (Alpaca)
        })

        # Validate live mode has exchange
        if mode == ExecutionMode.LIVE and exchange is None:
            raise ValueError("LIVE mode requires exchange instance")

        # Subscribe to orders
        self.event_bus.subscribe(EventType.ORDER, self._on_order)

        logger.info(
            f"OrderExecutor initialized: mode={mode.value}, "
            f"slippage={self.slippage_pct*100:.2f}%"
        )

    def _on_order(self, order: OrderEvent):
        """
        Process order and execute.

        Args:
            order: OrderEvent to execute
        """
        try:
            logger.info(
                f"Executing order: {order.side} {order.quantity} {order.symbol} "
                f"({order.order_type})"
            )

            if self.mode == ExecutionMode.PAPER:
                self._execute_paper(order)
            else:
                self._execute_live(order)

        except Exception as e:
            logger.error(f"Order execution failed: {e}", exc_info=True)

    def _execute_paper(self, order: OrderEvent):
        """
        Execute order in paper trading mode (simulated).

        Simulates realistic fills with slippage and commission.

        Args:
            order: OrderEvent to execute
        """
        # Get current market price (would come from live feed in real system)
        # For now, use the order price if LIMIT, or estimate market price
        if order.order_type == 'MARKET':
            # Market order: simulate worst-case fill
            # This would normally come from latest market data
            # For paper trading, we'll use the price from the signal
            # with realistic slippage applied
            fill_price = self._simulate_market_fill(order)
        elif order.order_type == 'LIMIT':
            # Limit order: fill at limit price (assuming it gets filled)
            fill_price = order.price
        else:
            logger.warning(f"Unsupported order type: {order.order_type}")
            return

        # Calculate commission
        commission = self._calculate_commission(
            order.symbol,
            order.asset_type,
            order.quantity,
            fill_price
        )

        # Simulate execution delay (1-2 seconds for realism)
        time.sleep(0.5)

        # Create and publish FillEvent
        fill = FillEvent(
            timestamp=datetime.now(),
            type=EventType.FILL,
            trade_id=f"FILL-{uuid.uuid4().hex[:12].upper()}",
            order_id=order.order_id,
            symbol=order.symbol,
            asset_type=order.asset_type,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            commission=commission,
            metadata={
                'execution_mode': 'PAPER',
                'strategy_id': order.strategy_id,
                'position_id': order.position_id
            }
        )

        # Store in database
        try:
            self.db.create_trade(
                trade_id=fill.trade_id,
                order_id=order.order_id,
                symbol=order.symbol,
                asset_type=order.asset_type,
                side=order.side,
                quantity=order.quantity,
                price=fill_price,
                commission=commission,
                timestamp=fill.timestamp.isoformat()
            )
        except Exception as e:
            logger.error(f"Failed to store trade: {e}")

        # Publish fill
        self.event_bus.publish(fill)

        logger.info(
            f"Order filled (PAPER): {order.side} {order.quantity} {order.symbol} "
            f"@ ${fill_price:.2f} (commission: ${commission:.2f})"
        )

    def _execute_live(self, order: OrderEvent):
        """
        Execute order on real exchange via CCXT.

        Args:
            order: OrderEvent to execute
        """
        try:
            # Create order via CCXT
            if order.order_type == 'MARKET':
                result = self.exchange.create_market_order(
                    symbol=order.symbol,
                    side=order.side.lower(),
                    amount=order.quantity
                )
            elif order.order_type == 'LIMIT':
                result = self.exchange.create_limit_order(
                    symbol=order.symbol,
                    side=order.side.lower(),
                    amount=order.quantity,
                    price=order.price
                )
            else:
                logger.error(f"Unsupported order type: {order.order_type}")
                return

            # Parse exchange response
            fill_price = float(result.get('average', result.get('price', 0)))
            filled_qty = float(result.get('filled', order.quantity))
            commission_cost = float(result.get('fee', {}).get('cost', 0))

            # If no commission in response, calculate it
            if commission_cost == 0:
                commission_cost = self._calculate_commission(
                    order.symbol,
                    order.asset_type,
                    filled_qty,
                    fill_price
                )

            # Create FillEvent
            fill = FillEvent(
                timestamp=datetime.now(),
                type=EventType.FILL,
                trade_id=result.get('id', f"FILL-{uuid.uuid4().hex[:12].upper()}"),
                order_id=order.order_id,
                symbol=order.symbol,
                asset_type=order.asset_type,
                side=order.side,
                quantity=filled_qty,
                price=fill_price,
                commission=commission_cost,
                metadata={
                    'execution_mode': 'LIVE',
                    'exchange_order_id': result.get('id'),
                    'strategy_id': order.strategy_id,
                    'position_id': order.position_id
                }
            )

            # Store in database
            self.db.create_trade(
                trade_id=fill.trade_id,
                order_id=order.order_id,
                symbol=order.symbol,
                asset_type=order.asset_type,
                side=order.side,
                quantity=filled_qty,
                price=fill_price,
                commission=commission_cost,
                timestamp=fill.timestamp.isoformat()
            )

            # Publish fill
            self.event_bus.publish(fill)

            logger.info(
                f"Order filled (LIVE): {order.side} {filled_qty} {order.symbol} "
                f"@ ${fill_price:.2f} (commission: ${commission_cost:.2f})"
            )

        except Exception as e:
            logger.error(f"Live order execution failed: {e}", exc_info=True)

    def _simulate_market_fill(self, order: OrderEvent) -> float:
        """
        Simulate market order fill price with slippage.

        Conservative approach:
        - BUY orders: add slippage (pay more)
        - SELL orders: subtract slippage (receive less)

        Args:
            order: OrderEvent

        Returns:
            Simulated fill price
        """
        # In real paper trading, this would use latest market data
        # For now, we'll use a placeholder price
        # TODO: Integrate with market data feed

        # Get reference price (would come from latest MarketDataEvent)
        # For demo purposes, using a placeholder
        base_price = order.price if order.price else 50000.0  # Placeholder

        # Apply slippage
        if order.side == 'BUY':
            # BUY: slippage works against us (pay more)
            fill_price = base_price * (1 + self.slippage_pct)
        else:
            # SELL: slippage works against us (receive less)
            fill_price = base_price * (1 - self.slippage_pct)

        return fill_price

    def _calculate_commission(
        self,
        symbol: str,
        asset_type: str,
        quantity: float,
        price: float
    ) -> float:
        """
        Calculate commission cost.

        Args:
            symbol: Trading symbol
            asset_type: 'CRYPTO' or 'STOCK'
            quantity: Order quantity
            price: Fill price

        Returns:
            Commission cost
        """
        # Get commission rate for asset type
        if isinstance(self.commission_pct, dict):
            rate = self.commission_pct.get(asset_type, 0.006)
        else:
            rate = self.commission_pct

        # Commission = trade value * rate
        trade_value = quantity * price
        commission = trade_value * rate

        return commission

    def set_mode(self, mode: ExecutionMode):
        """
        Change execution mode.

        Args:
            mode: New execution mode
        """
        if mode == ExecutionMode.LIVE and self.exchange is None:
            raise ValueError("Cannot switch to LIVE mode without exchange instance")

        self.mode = mode
        logger.info(f"Execution mode changed to: {mode.value}")

    def get_mode(self) -> str:
        """
        Get current execution mode.

        Returns:
            Mode as string
        """
        return self.mode.value
