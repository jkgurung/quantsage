"""
Event bus for pub/sub messaging between components.

The event bus allows components to communicate without tight coupling.
Supports both synchronous and asynchronous event handling.
"""

import asyncio
import logging
from collections import defaultdict
from typing import Callable, List, Optional, Dict
from datetime import datetime
import queue

from .events import Event, EventType

logger = logging.getLogger(__name__)


class EventBus:
    """
    Central event bus for system communication.

    Features:
    - Subscriber pattern for decoupling
    - Event history for backtesting
    - Both sync and async support
    - Event filtering
    """

    def __init__(self, mode: str = 'live'):
        """
        Initialize event bus.

        Args:
            mode: 'live' or 'backtest'
                  In backtest mode, events are stored for analysis
        """
        self.mode = mode
        self.subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        self.event_queue = queue.Queue()
        self.event_history: List[Event] = [] if mode == 'backtest' else None
        self.running = False

        logger.info(f"EventBus initialized in {mode} mode")

    def subscribe(self, event_type: EventType, handler: Callable):
        """
        Subscribe to specific event type.

        Args:
            event_type: Type of event to subscribe to
            handler: Callback function to handle event
                     Should accept Event as parameter
        """
        self.subscribers[event_type].append(handler)
        logger.debug(f"Subscribed {handler.__name__} to {event_type.value}")

    def unsubscribe(self, event_type: EventType, handler: Callable):
        """Unsubscribe from event type."""
        if handler in self.subscribers[event_type]:
            self.subscribers[event_type].remove(handler)
            logger.debug(f"Unsubscribed {handler.__name__} from {event_type.value}")

    def publish(self, event: Event):
        """
        Publish event to all subscribers.

        Args:
            event: Event to publish
        """
        # Store in history for backtesting
        if self.event_history is not None:
            self.event_history.append(event)

        # Add to queue
        self.event_queue.put(event)

        logger.debug(f"Published {event.type.value} event at {event.timestamp}")

    def process_events(self):
        """
        Process all events in queue synchronously.

        Called in main loop to dispatch events to subscribers.
        """
        while not self.event_queue.empty():
            try:
                event = self.event_queue.get_nowait()
                self._dispatch_event(event)
            except queue.Empty:
                break
            except Exception as e:
                logger.error(f"Error processing event: {e}", exc_info=True)

    def _dispatch_event(self, event: Event):
        """Dispatch event to subscribers."""
        event_type = event.type

        # Call subscribers for this specific event type
        if event_type in self.subscribers:
            for handler in self.subscribers[event_type]:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(
                        f"Error in {handler.__name__} handling {event_type.value}: {e}",
                        exc_info=True
                    )

    def clear_history(self):
        """Clear event history (for backtesting)."""
        if self.event_history is not None:
            self.event_history.clear()
            logger.debug("Event history cleared")

    def get_history(self, event_type: Optional[EventType] = None,
                   start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None) -> List[Event]:
        """
        Get event history with optional filtering.

        Args:
            event_type: Filter by event type
            start_time: Filter events after this time
            end_time: Filter events before this time

        Returns:
            List of events matching criteria
        """
        if self.event_history is None:
            return []

        events = self.event_history

        # Filter by event type
        if event_type:
            events = [e for e in events if e.type == event_type]

        # Filter by time
        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]

        return events

    def get_stats(self) -> Dict:
        """Get event bus statistics."""
        stats = {
            'mode': self.mode,
            'queue_size': self.event_queue.qsize(),
            'subscriber_count': {
                event_type.value: len(handlers)
                for event_type, handlers in self.subscribers.items()
            }
        }

        if self.event_history is not None:
            stats['history_size'] = len(self.event_history)
            # Count by event type
            type_counts = defaultdict(int)
            for event in self.event_history:
                type_counts[event.type.value] += 1
            stats['event_counts'] = dict(type_counts)

        return stats


class AsyncEventBus(EventBus):
    """
    Async version of event bus using asyncio.

    Use this for production with async/await pattern.
    """

    def __init__(self, mode: str = 'live'):
        super().__init__(mode)
        self.async_queue = asyncio.Queue()

    async def publish_async(self, event: Event):
        """Publish event asynchronously."""
        if self.event_history is not None:
            self.event_history.append(event)

        await self.async_queue.put(event)
        logger.debug(f"Published {event.type.value} event (async)")

    async def process_events_async(self):
        """Process events asynchronously."""
        while not self.async_queue.empty():
            try:
                event = await asyncio.wait_for(
                    self.async_queue.get(),
                    timeout=0.1
                )
                await self._dispatch_event_async(event)
            except asyncio.TimeoutError:
                break
            except Exception as e:
                logger.error(f"Error processing async event: {e}", exc_info=True)

    async def _dispatch_event_async(self, event: Event):
        """Dispatch event to async subscribers."""
        event_type = event.type

        if event_type in self.subscribers:
            tasks = []
            for handler in self.subscribers[event_type]:
                try:
                    # Check if handler is async
                    if asyncio.iscoroutinefunction(handler):
                        tasks.append(handler(event))
                    else:
                        # Run sync handler in executor
                        loop = asyncio.get_event_loop()
                        tasks.append(loop.run_in_executor(None, handler, event))
                except Exception as e:
                    logger.error(
                        f"Error preparing {handler.__name__}: {e}",
                        exc_info=True
                    )

            # Wait for all handlers to complete
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)


# Example usage
if __name__ == "__main__":
    from .events import MarketDataEvent, SignalEvent

    logging.basicConfig(level=logging.DEBUG)

    # Create event bus
    bus = EventBus(mode='backtest')

    # Define handlers
    def on_market_data(event: MarketDataEvent):
        print(f"Market data received: {event.symbol} @ {event.ohlcv['close']}")

    def on_signal(event: SignalEvent):
        print(f"Signal: {event.signal_type} {event.symbol} (confidence: {event.confidence})")

    # Subscribe
    bus.subscribe(EventType.MARKET_DATA, on_market_data)
    bus.subscribe(EventType.SIGNAL, on_signal)

    # Publish events
    bus.publish(MarketDataEvent(
        timestamp=datetime.now(),
        symbol='BTC/USD',
        asset_type='CRYPTO',
        ohlcv={'open': 50000, 'high': 51000, 'low': 49500, 'close': 50500, 'volume': 100}
    ))

    bus.publish(SignalEvent(
        timestamp=datetime.now(),
        symbol='BTC/USD',
        asset_type='CRYPTO',
        strategy_id='mean_reversion',
        signal_type='BUY',
        confidence=0.85,
        price=50500
    ))

    # Process events
    bus.process_events()

    # Check stats
    print("\nEvent Bus Stats:")
    import json
    print(json.dumps(bus.get_stats(), indent=2))
