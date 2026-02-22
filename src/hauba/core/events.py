"""Async event emitter for Hauba agent communication."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any

import structlog

from hauba.core.types import Event

logger = structlog.get_logger()

# Type alias for event handlers
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventEmitter:
    """Async pub/sub event system with topic-based routing."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._history: list[Event] = []
        self._max_history: int = 10000

    def on(self, topic: str, handler: EventHandler) -> None:
        """Subscribe a handler to a topic."""
        self._handlers[topic].append(handler)
        logger.debug("event.subscribed", topic=topic)

    def off(self, topic: str, handler: EventHandler) -> None:
        """Unsubscribe a handler from a topic."""
        if topic in self._handlers:
            self._handlers[topic] = [h for h in self._handlers[topic] if h is not handler]

    async def emit(self, topic: str, data: dict[str, Any] | None = None, **kwargs: Any) -> None:
        """Emit an event to all subscribers of the topic."""
        event = Event(
            id=str(uuid.uuid4()),
            topic=topic,
            data=data or {},
            source=kwargs.get("source", ""),
            task_id=kwargs.get("task_id", ""),
        )
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]

        handlers = self._handlers.get(topic, [])
        # Also fire wildcard handlers
        handlers = handlers + self._handlers.get("*", [])

        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception("event.handler_error", topic=topic, handler=handler.__name__)

    def get_history(self, topic: str | None = None, limit: int = 100) -> list[Event]:
        """Get event history, optionally filtered by topic."""
        events = self._history
        if topic:
            events = [e for e in events if e.topic == topic]
        return events[-limit:]

    def clear_history(self) -> None:
        """Clear event history."""
        self._history.clear()
