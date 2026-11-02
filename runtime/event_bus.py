"""
runtime/event_bus.py - Thread-safe lightweight event bus for DREX.

The bus is intentionally synchronous. Publishing an event invokes matching
subscribers on the caller's thread, keeping the foundation simple and easy to
reason about. Async queues can be layered on later without changing event
definitions.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Callable

from loguru import logger

from runtime.events import Event


EventHandler = Callable[[Event], None]


class EventBus:
    """
    Thread-safe publish/subscribe event bus.

    Subscribe to a concrete event type, or to "*" to receive every event.
    """

    WILDCARD = "*"

    def __init__(self):
        self._lock = threading.RLock()
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._published_count = 0
        logger.debug("EventBus initialized")

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe a handler to an event type."""
        if not event_type:
            raise ValueError("event_type is required")
        if not callable(handler):
            raise TypeError("handler must be callable")

        with self._lock:
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)
                logger.debug("EventBus subscriber added | type={}", event_type)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove a handler from an event type."""
        with self._lock:
            handlers = self._subscribers.get(event_type)
            if not handlers:
                return
            if handler in handlers:
                handlers.remove(handler)
                logger.debug("EventBus subscriber removed | type={}", event_type)
            if not handlers:
                self._subscribers.pop(event_type, None)

    def publish(self, event: Event) -> None:
        """Publish an event to exact-type subscribers and wildcard subscribers."""
        if not isinstance(event, Event):
            raise TypeError("event must be an Event instance")

        with self._lock:
            handlers = list(self._subscribers.get(event.type, ()))
            wildcard_handlers = list(self._subscribers.get(self.WILDCARD, ()))
            self._published_count += 1

        for handler in handlers + wildcard_handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.exception(
                    "EventBus handler failed | type={} | handler={} | error={}",
                    event.type,
                    getattr(handler, "__name__", repr(handler)),
                    exc,
                )

    def get_status(self) -> dict:
        """Return JSON-safe event bus status."""
        with self._lock:
            return {
                "published_count": self._published_count,
                "subscriber_count": sum(
                    len(handlers) for handlers in self._subscribers.values()
                ),
                "subscriptions": {
                    event_type: len(handlers)
                    for event_type, handlers in self._subscribers.items()
                },
            }


__all__ = ["EventBus", "EventHandler"]
