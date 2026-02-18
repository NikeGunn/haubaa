"""Notifier — event-driven notification system for Hauba."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

from hauba.core.events import EventEmitter
from hauba.core.types import Event

logger = structlog.get_logger()


class NotificationLevel(str, Enum):
    """Notification severity levels."""

    INFO = "info"
    PROGRESS = "progress"
    MILESTONE = "milestone"
    QUESTION = "question"
    ERROR = "error"
    SUCCESS = "success"


class Notification:
    """A single notification to be delivered."""

    def __init__(
        self,
        level: NotificationLevel,
        title: str,
        body: str = "",
        task_id: str = "",
        source: str = "",
    ) -> None:
        self.level = level
        self.title = title
        self.body = body
        self.task_id = task_id
        self.source = source
        self.timestamp = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.value,
            "title": self.title,
            "body": self.body,
            "task_id": self.task_id,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
        }


# Type for notification sinks
NotificationSink = Callable[["Notification"], Coroutine[Any, Any, None]]


class Notifier:
    """Central notification system that listens to events and dispatches notifications.

    Subscribes to Hauba events and converts them to structured notifications
    that can be sent to any registered sink (Telegram, Discord, Web, terminal, etc.).
    """

    def __init__(self, events: EventEmitter) -> None:
        self.events = events
        self._sinks: list[NotificationSink] = []
        self._history: list[Notification] = []
        self._max_history: int = 500
        self._subscribed = False

    def add_sink(self, sink: NotificationSink) -> None:
        """Register a notification sink."""
        self._sinks.append(sink)

    def subscribe(self) -> None:
        """Subscribe to relevant events on the emitter."""
        if self._subscribed:
            return

        self.events.on("task.started", self._on_task_started)
        self.events.on("task.completed", self._on_task_completed)
        self.events.on("task.failed", self._on_task_failed)
        self.events.on("milestone.completed", self._on_milestone_completed)
        self.events.on("milestone.failed", self._on_milestone_failed)
        self.events.on("ledger.gate_failed", self._on_gate_failed)

        self._subscribed = True
        logger.info("notifier.subscribed")

    async def send(self, notification: Notification) -> int:
        """Send a notification to all registered sinks.

        Returns:
            Number of sinks that received the notification successfully.
        """
        self._history.append(notification)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        sent = 0
        for sink in self._sinks:
            try:
                await sink(notification)
                sent += 1
            except Exception as exc:
                logger.error("notifier.sink_error", error=str(exc))

        return sent

    def get_history(
        self,
        level: NotificationLevel | None = None,
        limit: int = 50,
    ) -> list[Notification]:
        """Get notification history, optionally filtered by level."""
        items = self._history
        if level:
            items = [n for n in items if n.level == level]
        return items[-limit:]

    # --- Event handlers ---

    async def _on_task_started(self, event: Event) -> None:
        n = Notification(
            level=NotificationLevel.INFO,
            title="Task Started",
            body=event.data.get("instruction", ""),
            task_id=event.data.get("task_id", ""),
            source=event.source,
        )
        await self.send(n)

    async def _on_task_completed(self, event: Event) -> None:
        n = Notification(
            level=NotificationLevel.SUCCESS,
            title="Task Completed",
            task_id=event.data.get("task_id", ""),
            source=event.source,
        )
        await self.send(n)

    async def _on_task_failed(self, event: Event) -> None:
        n = Notification(
            level=NotificationLevel.ERROR,
            title="Task Failed",
            body=event.data.get("error", ""),
            task_id=event.data.get("task_id", ""),
            source=event.source,
        )
        await self.send(n)

    async def _on_milestone_completed(self, event: Event) -> None:
        n = Notification(
            level=NotificationLevel.MILESTONE,
            title="Milestone Completed",
            body=event.data.get("milestone_id", ""),
            task_id=event.task_id,
            source=event.source,
        )
        await self.send(n)

    async def _on_milestone_failed(self, event: Event) -> None:
        n = Notification(
            level=NotificationLevel.ERROR,
            title="Milestone Failed",
            body=event.data.get("error", ""),
            task_id=event.task_id,
            source=event.source,
        )
        await self.send(n)

    async def _on_gate_failed(self, event: Event) -> None:
        n = Notification(
            level=NotificationLevel.ERROR,
            title="Verification Gate Failed",
            body=f"Gate: {event.data.get('gate', 'unknown')}",
            task_id=event.task_id,
            source=event.source,
        )
        await self.send(n)
