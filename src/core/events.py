"""
Event classes for the event-driven trading system.

All communication between components happens through events.
This ensures the same code runs in backtest and live modes.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class EventType(Enum):
    """Event types in the system."""
    MARKET_DATA = "market_data"
    SIGNAL = "signal"
    ORDER = "order"
    FILL = "fill"
    POSITION_UPDATE = "position_update"
    RISK_ALERT = "risk_alert"
    PERFORMANCE_METRIC = "performance_metric"
    SYSTEM = "system"


@dataclass
class Event:
    """Base event class."""
    type: EventType
    timestamp: datetime
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert event to dictionary."""
        return {
            'type': self.type.value,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data
        }


@dataclass
class MarketDataEvent(Event):
    """
    Market data update event.

    Published when new price/volume data arrives.
    """
    symbol: str = ""
    asset_type: str = ""
    ohlcv: Dict[str, float] = field(default_factory=dict)
    data_source: str = ""

    def __init__(self, timestamp: datetime, symbol: str, asset_type: str,
                 ohlcv: Dict[str, float], data_source: str):
        super().__init__(EventType.MARKET_DATA, timestamp)
        self.symbol = symbol
        self.asset_type = asset_type
        self.ohlcv = ohlcv
        self.data_source = data_source

    def to_dict(self) -> Dict:
        return {
            'type': self.type.value,
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'asset_type': self.asset_type,
            'ohlcv': self.ohlcv,
            'data_source': self.data_source
        }


@dataclass
class SignalEvent(Event):
    """
    Trading signal event.

    Published by strategies to indicate trading opportunity.
    """
    symbol: str = ""
    asset_type: str = ""
    strategy_id: str = ""
    signal_type: str = ""  # 'BUY', 'SELL', 'HOLD'
    confidence: float = 0.0  # 0.0 to 1.0
    price: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __init__(self, timestamp: datetime, symbol: str, asset_type: str,
                 strategy_id: str, signal_type: str, confidence: float,
                 price: float, metadata: Dict[str, Any] = None):
        super().__init__(EventType.SIGNAL, timestamp)
        self.symbol = symbol
        self.asset_type = asset_type
        self.strategy_id = strategy_id
        self.signal_type = signal_type
        self.confidence = confidence
        self.price = price
        self.metadata = metadata or {}

    def to_dict(self) -> Dict:
        return {
            'type': self.type.value,
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'asset_type': self.asset_type,
            'strategy_id': self.strategy_id,
            'signal_type': self.signal_type,
            'confidence': self.confidence,
            'price': self.price,
            'metadata': self.metadata
        }


@dataclass
class OrderEvent(Event):
    """
    Order request event.

    Published when a position should be opened/closed.
    """
    order_id: str = ""
    symbol: str = ""
    asset_type: str = ""
    side: str = ""  # 'BUY', 'SELL'
    order_type: str = ""  # 'MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT'
    quantity: float = 0.0
    price: Optional[float] = None
    stop_price: Optional[float] = None
    strategy_id: str = ""
    position_id: Optional[int] = None

    def __post_init__(self):
        self.type = EventType.ORDER
        self.data = {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'asset_type': self.asset_type,
            'side': self.side,
            'order_type': self.order_type,
            'quantity': self.quantity,
            'price': self.price,
            'stop_price': self.stop_price,
            'strategy_id': self.strategy_id,
            'position_id': self.position_id
        }

    def to_dict(self) -> Dict:
        return {
            'type': self.type.value,
            'timestamp': self.timestamp.isoformat(),
            **self.data
        }


@dataclass
class FillEvent(Event):
    """
    Order fill event.

    Published when an order is executed.
    """
    trade_id: str = ""
    order_id: str = ""
    symbol: str = ""
    asset_type: str = ""
    side: str = ""
    quantity: float = 0.0
    price: float = 0.0
    commission: float = 0.0
    commission_asset: str = "USD"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.type = EventType.FILL
        self.data = {
            'trade_id': self.trade_id,
            'order_id': self.order_id,
            'symbol': self.symbol,
            'asset_type': self.asset_type,
            'side': self.side,
            'quantity': self.quantity,
            'price': self.price,
            'commission': self.commission,
            'commission_asset': self.commission_asset,
            'metadata': self.metadata
        }

    def to_dict(self) -> Dict:
        return {
            'type': self.type.value,
            'timestamp': self.timestamp.isoformat(),
            **self.data
        }


@dataclass
class PositionUpdateEvent(Event):
    """
    Position update event.

    Published when a position is opened, updated, or closed.
    """
    position_id: int = 0
    symbol: str = ""
    asset_type: str = ""
    side: str = ""
    quantity: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    pnl_realized: float = 0.0
    pnl_unrealized: float = 0.0
    status: str = ""  # 'OPEN', 'CLOSED', 'PARTIAL'
    strategy_id: str = ""

    def __post_init__(self):
        self.type = EventType.POSITION_UPDATE
        self.data = {
            'position_id': self.position_id,
            'symbol': self.symbol,
            'asset_type': self.asset_type,
            'side': self.side,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'current_price': self.current_price,
            'pnl_realized': self.pnl_realized,
            'pnl_unrealized': self.pnl_unrealized,
            'status': self.status,
            'strategy_id': self.strategy_id
        }


@dataclass
class RiskAlertEvent(Event):
    """
    Risk alert event.

    Published when a risk limit is breached.
    """
    alert_type: str = ""
    severity: str = ""  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    description: str = ""
    symbol: Optional[str] = None
    asset_type: Optional[str] = None
    strategy_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.type = EventType.RISK_ALERT
        self.data = {
            'alert_type': self.alert_type,
            'severity': self.severity,
            'description': self.description,
            'symbol': self.symbol,
            'asset_type': self.asset_type,
            'strategy_id': self.strategy_id,
            'metadata': self.metadata
        }


@dataclass
class PerformanceMetricEvent(Event):
    """
    Performance metric event.

    Published for tracking system performance.
    """
    metric_name: str = ""
    metric_value: float = 0.0
    strategy_id: Optional[str] = None
    timeframe: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.type = EventType.PERFORMANCE_METRIC
        self.data = {
            'metric_name': self.metric_name,
            'metric_value': self.metric_value,
            'strategy_id': self.strategy_id,
            'timeframe': self.timeframe,
            'metadata': self.metadata
        }


@dataclass
class SystemEvent(Event):
    """
    System-level event.

    Published for system state changes.
    """
    event_name: str = ""
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.type = EventType.SYSTEM
        self.data = {
            'event_name': self.event_name,
            'message': self.message,
            'metadata': self.metadata
        }
