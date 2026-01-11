"""
Execution Engine for Backtesting.

Simulates realistic order fills with slippage and commissions.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Optional, Tuple

from src.core.events import EventType, OrderEvent, FillEvent
from src.core.event_bus import EventBus
from src.data.storage import DatabaseManager

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """
    Execution engine for simulating order fills in backtests.

    Features:
    - Conservative fill simulation (high for buy, low for sell)
    - Realistic slippage model (base + volume + volatility impact)
    - Transaction cost modeling (from config)
    - Database logging of orders and fills
    """

    def __init__(self, event_bus: EventBus, db: DatabaseManager,
                 current_bars: Dict, config: Dict):
        """
        Initialize execution engine.

        Args:
            event_bus: EventBus instance for publishing FillEvents
            db: DatabaseManager for persisting orders/fills
            current_bars: Dict reference to current bar data (symbol -> bar dict)
            config: Risk config dict with transaction_costs
        """
        self.event_bus = event_bus
        self.db = db
        self.current_bars = current_bars  # Shared reference with BacktestEngine
        self.config = config

        # Subscribe to OrderEvent
        self.event_bus.subscribe(EventType.ORDER, self._on_order)

        logger.info("ExecutionEngine initialized")

    def _on_order(self, order: OrderEvent):
        """
        Process order and simulate execution.

        Steps:
        1. Validate order (has current bar, valid fields)
        2. Get current bar for symbol
        3. Calculate fill price (conservative: high for buy, low for sell)
        4. Apply slippage model
        5. Calculate commission
        6. Store order in database
        7. Create and publish FillEvent

        Args:
            order: OrderEvent to process
        """
        # Validate order
        valid, error = self._validate_order(order)
        if not valid:
            logger.error(f"Order validation failed: {error}")
            # Update order status to REJECTED
            try:
                self.db.update_order_status(order.order_id, 'REJECTED')
            except Exception as e:
                logger.error(f"Failed to update order status: {e}")
            return

        # Get current bar
        bar = self.current_bars.get(order.symbol)
        if bar is None:
            logger.error(f"No current bar for {order.symbol}")
            return

        # Calculate fill price
        fill_price = self._calculate_fill_price(order, bar)

        # Calculate commission
        commission = self._calculate_commission(order, fill_price)

        # Store order in database (if not already stored by RiskManager)
        try:
            # Check if order exists
            existing_order = self.db.query(
                "SELECT id FROM orders WHERE order_id = ?",
                (order.order_id,)
            )

            if not existing_order:
                # Create order
                self.db.create_order(
                    order_id=order.order_id,
                    symbol=order.symbol,
                    asset_type=order.asset_type,
                    side=order.side,
                    order_type=order.order_type,
                    quantity=order.quantity,
                    strategy_id=order.metadata.get('strategy_id', 'unknown'),
                    price=order.price
                )

            # Update order status to FILLED
            self.db.update_order_status(
                order_id=order.order_id,
                status='FILLED',
                filled_quantity=order.quantity,
                avg_fill_price=fill_price,
                commission=commission
            )
        except Exception as e:
            logger.error(f"Failed to store order {order.order_id}: {e}")
            return

        # Create FillEvent
        fill = FillEvent(
            timestamp=datetime.now(),
            type=EventType.FILL,
            trade_id=f"TRADE-{uuid.uuid4().hex[:8].upper()}",
            order_id=order.order_id,
            symbol=order.symbol,
            asset_type=order.asset_type,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            commission=commission,
            metadata={
                'bar': bar,
                'slippage_applied': True,
                'strategy_id': order.metadata.get('strategy_id', 'unknown')
            }
        )

        # Publish FillEvent
        self.event_bus.publish(fill)
        logger.info(f"Order filled: {order.symbol} {order.side} {order.quantity:.4f} @ ${fill_price:.2f} (commission: ${commission:.2f})")

    def _validate_order(self, order: OrderEvent) -> Tuple[bool, Optional[str]]:
        """
        Validate order has required fields.

        Args:
            order: OrderEvent to validate

        Returns:
            (valid, error_message) tuple
        """
        # Check required fields
        if not order.order_id:
            return (False, "Missing order_id")

        if not order.symbol:
            return (False, "Missing symbol")

        if not order.side or order.side not in ['BUY', 'SELL']:
            return (False, f"Invalid side: {order.side}")

        if order.quantity <= 0:
            return (False, f"Invalid quantity: {order.quantity}")

        # Check if current bar exists
        if order.symbol not in self.current_bars:
            return (False, f"No current bar for {order.symbol}")

        return (True, None)

    def _calculate_fill_price(self, order: OrderEvent, bar: Dict) -> float:
        """
        Calculate fill price using conservative assumptions.

        - BUY: Use bar high (worst price for buyer)
        - SELL: Use bar low (worst price for seller)
        - Add slippage (makes price worse)

        This avoids over-optimization by assuming we get worst price in bar.

        Args:
            order: OrderEvent
            bar: Current bar dict with OHLCV

        Returns:
            Fill price (float)
        """
        # Base price (conservative)
        if order.side == 'BUY':
            base_price = bar['high']  # Worst price for buyer
        else:  # SELL
            base_price = bar['low']   # Worst price for seller

        # Calculate slippage
        slippage_amount = self._calculate_slippage(order, base_price, bar)

        # Apply slippage (always makes price worse)
        if order.side == 'BUY':
            fill_price = base_price + slippage_amount  # Pay more
        else:  # SELL
            fill_price = base_price - slippage_amount  # Receive less

        return fill_price

    def _calculate_slippage(self, order: OrderEvent, base_price: float,
                           bar: Dict) -> float:
        """
        Calculate realistic slippage based on:
        1. Base slippage (fixed %)
        2. Volume impact (order size relative to bar volume)
        3. Volatility impact (bar range)

        Args:
            order: OrderEvent
            base_price: Base fill price
            bar: Current bar dict with OHLCV

        Returns:
            Slippage amount in dollars (always positive)
        """
        # Get config
        params = self.config.get('transaction_costs', {}).get('slippage_params', {})
        base_slippage_pct = params.get('base_slippage', 0.001)  # 0.1% default
        volume_impact_factor = params.get('volume_impact', 0.00001)

        # 1. Base slippage
        base_slippage = base_price * base_slippage_pct

        # 2. Volume impact
        order_value = order.quantity * base_price
        bar_volume = bar.get('volume', 0)

        if bar_volume > 0:
            bar_volume_value = bar_volume * bar['close']
            volume_pct = order_value / max(bar_volume_value, order_value)
            volume_slippage = base_price * (volume_pct * volume_impact_factor)
        else:
            volume_slippage = 0

        # 3. Volatility impact (bar range)
        if bar['close'] > 0:
            bar_range = (bar['high'] - bar['low']) / bar['close']
            volatility_slippage = base_price * (bar_range * 0.5)
        else:
            volatility_slippage = 0

        # Total slippage (cap at 2% to avoid extreme values)
        total_slippage = min(
            base_slippage + volume_slippage + volatility_slippage,
            base_price * 0.02
        )

        return total_slippage

    def _calculate_commission(self, order: OrderEvent, fill_price: float) -> float:
        """
        Calculate commission based on asset type.

        Args:
            order: OrderEvent
            fill_price: Fill price

        Returns:
            Commission amount in dollars
        """
        costs = self.config.get('transaction_costs', {})
        asset_type = order.asset_type.lower()

        if asset_type == 'crypto':
            # Use taker fee for market orders
            rate = costs.get('crypto', {}).get('taker_fee', 0.006)  # 0.6% default
            return order.quantity * fill_price * rate

        elif asset_type in ['stock', 'etf']:
            # Stocks: $0 commission, but SEC/FINRA fees for sells
            if order.side == 'SELL':
                order_value = order.quantity * fill_price
                sec_fee = order_value * costs.get('stocks', {}).get('sec_fee', 0.0000278)
                finra_fee = order.quantity * costs.get('stocks', {}).get('finra_taf', 0.000166)
                return sec_fee + finra_fee
            return 0.0

        # Unknown asset type - no commission
        return 0.0
