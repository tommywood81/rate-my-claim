"""Lightweight in-process domain event bus (extensible to message queues)."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


class EventBus:
    """Async publish/subscribe bus for domain events."""

    def __init__(self) -> None:
        """Initialize empty subscriber registry."""
        self._handlers: dict[str, list[EventHandler]] = {}

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for an event type."""
        self._handlers.setdefault(event_type, []).append(handler)

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """Dispatch an event to all subscribers (errors logged, not raised)."""
        for handler in self._handlers.get(event_type, []):
            try:
                await handler(payload)
            except Exception:
                logger.exception("event_handler_failed", extra={"event_type": event_type})


bus = EventBus()
