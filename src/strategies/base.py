"""
Base strategy abstract class.

Defines the interface that all trading strategies must implement.
Provides common functionality for:
- Configuration management
- Event subscription/publishing
- Position tracking
- Position sizing
- Signal generation
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional, List
from datetime import datetime

from src.core.events import MarketDataEvent, SignalEvent, EventType
from src.core.event_bus import EventBus
from src.data.storage import DatabaseManager


logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    
    All strategies must implement the on_market_data() method which
    processes market data and generates trading signals.
    
    The strategy framework is event-driven:
    - Subscribe to MarketDataEvent
    - Process data and evaluate conditions
    - Publish SignalEvent when conditions met
    
    Configuration is loaded from YAML files in config/strategies/
    
    Usage:
        class MyStrategy(BaseStrategy):
            def on_market_data(self, event: MarketDataEvent):
                # Implement strategy logic
                if buy_conditions_met:
                    return self._create_signal(...)
                return None
    """
    
    def __init__(self, config: Dict, event_bus: EventBus, db: DatabaseManager):
        """
        Initialize strategy with configuration and dependencies.
        
        Args:
            config: Strategy configuration dict from YAML
            event_bus: Event bus for pub/sub
            db: Database manager for queries
        """
        self.config = config
        self.event_bus = event_bus
        self.db = db
        
        # Extract configuration
        self.name = config.get('strategy', {}).get('name', self.__class__.__name__)
        self.enabled = config.get('strategy', {}).get('enabled', True)
        self.symbols = config.get('strategy', {}).get('symbols', [])
        self.asset_type = config.get('strategy', {}).get('asset_type', 'CRYPTO')
        
        # Position sizing config
        sizing_config = config.get('strategy', {}).get('position_sizing', {})
        self.max_position_pct = sizing_config.get('max_position_pct', 0.10)
        self.sizing_method = sizing_config.get('method', 'fixed')
        
        # State tracking
        self.positions = {}  # symbol -> position dict
        self.entry_prices = {}  # symbol -> entry price
        self.pending_orders = {}  # symbol -> order dict
        
        # Subscribe to market data events if enabled
        if self.enabled:
            self.event_bus.subscribe(EventType.MARKET_DATA, self._on_market_data_wrapper)
            logger.info(f"Strategy {self.name} initialized and subscribed to market data")
        else:
            logger.info(f"Strategy {self.name} initialized but DISABLED")
    
    def _on_market_data_wrapper(self, event: MarketDataEvent):
        """
        Wrapper for on_market_data that handles common logic.
        
        - Filters events for configured symbols
        - Calls subclass implementation
        - Publishes generated signals
        """
        try:
            # Filter for configured symbols only
            if event.symbol not in self.symbols:
                return
            
            # Call subclass implementation
            signal = self.on_market_data(event)
            
            # Publish signal if generated
            if signal is not None:
                logger.info(f"{self.name}: Generated signal for {signal.symbol} - "
                          f"{signal.signal_type} @ {signal.price:.2f}")
                self.event_bus.publish(signal)
                
        except Exception as e:
            logger.error(f"{self.name}: Error processing market data for {event.symbol}: {e}",
                        exc_info=True)
    
    @abstractmethod
    def on_market_data(self, event: MarketDataEvent) -> Optional[SignalEvent]:
        """
        Process market data and generate trading signal.
        
        Subclasses MUST implement this method with strategy-specific logic.
        
        Args:
            event: Market data event with OHLCV data
        
        Returns:
            SignalEvent if conditions are met, None otherwise
        """
        pass
    
    def calculate_position_size(self, symbol: str, signal_strength: float = 1.0,
                                stop_loss_pct: Optional[float] = None) -> float:
        """
        Calculate position size based on configured method.
        
        Args:
            symbol: Trading symbol
            signal_strength: Signal confidence (0-1)
            stop_loss_pct: Stop loss percentage for risk-based sizing
        
        Returns:
            Position size as percentage of portfolio (0-1)
        """
        try:
            if self.sizing_method == 'fixed':
                # Fixed percentage of portfolio
                size = self.max_position_pct
                
            elif self.sizing_method == 'risk_based' and stop_loss_pct:
                # Risk-based: size based on stop loss distance
                # Assume willing to risk 1% of portfolio per trade
                portfolio_risk = 0.01
                size = portfolio_risk / stop_loss_pct
                # Cap at max position size
                size = min(size, self.max_position_pct)
                
            else:
                # Default to max position size
                size = self.max_position_pct
            
            # Adjust by signal strength
            size = size * signal_strength
            
            logger.debug(f"Position size for {symbol}: {size:.2%} (strength: {signal_strength:.2f})")
            return size
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return self.max_position_pct  # Fallback
    
    def has_position(self, symbol: str) -> bool:
        """Check if we have an open position for symbol."""
        return symbol in self.positions and self.positions[symbol] is not None
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """Get current position for symbol."""
        return self.positions.get(symbol)
    
    def update_position(self, symbol: str, position: Optional[Dict]):
        """
        Update position state.
        
        Args:
            symbol: Trading symbol
            position: Position dict or None to clear
        """
        if position is None:
            if symbol in self.positions:
                del self.positions[symbol]
            if symbol in self.entry_prices:
                del self.entry_prices[symbol]
        else:
            self.positions[symbol] = position
            if 'entry_price' in position:
                self.entry_prices[symbol] = position['entry_price']
    
    def _create_signal(self, symbol: str, direction: str, target_price: float,
                      stop_loss: Optional[float] = None,
                      take_profit: Optional[float] = None,
                      confidence: float = 1.0,
                      metadata: Optional[Dict] = None) -> SignalEvent:
        """
        Create a SignalEvent with standard fields.

        Args:
            symbol: Trading symbol
            direction: 'BUY', 'SELL', or 'CLOSE'
            target_price: Target entry/exit price
            stop_loss: Optional stop loss price
            take_profit: Optional take profit price
            confidence: Signal confidence (0-1)
            metadata: Optional metadata dict

        Returns:
            SignalEvent
        """
        # Calculate position size
        stop_loss_pct = None
        if stop_loss and direction in ['BUY', 'SELL']:
            stop_loss_pct = abs(target_price - stop_loss) / target_price

        position_size = self.calculate_position_size(symbol, confidence, stop_loss_pct)

        # Create metadata with additional strategy fields
        signal_metadata = {
            'strategy': self.name,
            'asset_type': self.asset_type,
            'quantity': position_size,  # Position size as percentage
            'stop_loss': stop_loss,
            'take_profit': take_profit,
        }
        if metadata:
            signal_metadata.update(metadata)

        return SignalEvent(
            timestamp=datetime.now(),
            symbol=symbol,
            asset_type=self.asset_type,
            strategy_id=self.name,
            signal_type=direction,  # BUY, SELL, or CLOSE
            confidence=confidence,
            price=target_price,
            metadata=signal_metadata
        )
    
    def get_recent_data(self, symbol: str, lookback_periods: int = 100) -> Optional[List[Dict]]:
        """
        Get recent market data from database.
        
        Args:
            symbol: Trading symbol
            lookback_periods: Number of periods to fetch
        
        Returns:
            List of market data dicts or None
        """
        try:
            # Query database for recent data
            from datetime import timedelta
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=lookback_periods)
            
            data = self.db.get_market_data(
                symbol=symbol,
                start_date=start_time,
                end_date=end_time,
                limit=lookback_periods
            )
            
            if not data:
                logger.warning(f"No data found for {symbol}")
                return None
            
            logger.debug(f"Fetched {len(data)} periods for {symbol}")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None
    
    def __repr__(self) -> str:
        status = "ENABLED" if self.enabled else "DISABLED"
        return f"{self.__class__.__name__}(name={self.name}, status={status}, symbols={self.symbols})"


