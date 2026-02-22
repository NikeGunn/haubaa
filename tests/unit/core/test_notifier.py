"""Tests for Notifier — event-driven notification system."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from hauba.core.events import EventEmitter
from hauba.core.notifier import Notification, NotificationLevel, Notifier


@pytest.fixture
def events() -> EventEmitter:
    return EventEmitter()


@pytest.fixture
def notifier(events: EventEmitter) -> Notifier:
    n = Notifier(events)
    n.subscribe()
    return n


# --- Notification model ---


def test_notification_to_dict() -> None:
    n = Notification(
        level=NotificationLevel.SUCCESS,
        title="Done",
        body="Task complete",
        task_id="t-1",
        source="dir-1",
    )
    d = n.to_dict()
    assert d["level"] == "success"
    assert d["title"] == "Done"
    assert d["body"] == "Task complete"
    assert "timestamp" in d


# --- Send to sinks ---


async def test_send_to_single_sink(notifier: Notifier) -> None:
    sink = AsyncMock()
    notifier.add_sink(sink)

    n = Notification(level=NotificationLevel.INFO, title="Test")
    sent = await notifier.send(n)
    assert sent == 1
    sink.assert_called_once_with(n)


async def test_send_to_multiple_sinks(notifier: Notifier) -> None:
    sink1 = AsyncMock()
    sink2 = AsyncMock()
    notifier.add_sink(sink1)
    notifier.add_sink(sink2)

    n = Notification(level=NotificationLevel.ERROR, title="Failure")
    sent = await notifier.send(n)
    assert sent == 2


async def test_send_handles_sink_error(notifier: Notifier) -> None:
    bad_sink = AsyncMock(side_effect=Exception("sink error"))
    good_sink = AsyncMock()
    notifier.add_sink(bad_sink)
    notifier.add_sink(good_sink)

    n = Notification(level=NotificationLevel.INFO, title="Test")
    sent = await notifier.send(n)
    assert sent == 1  # Only good sink succeeded


# --- Event-driven notifications ---


async def test_task_started_generates_notification(
    events: EventEmitter, notifier: Notifier
) -> None:
    sink = AsyncMock()
    notifier.add_sink(sink)

    await events.emit("task.started", {"task_id": "t-1", "instruction": "build app"})
    assert sink.call_count == 1
    notification = sink.call_args[0][0]
    assert notification.level == NotificationLevel.INFO
    assert notification.title == "Task Started"


async def test_task_completed_generates_notification(
    events: EventEmitter, notifier: Notifier
) -> None:
    sink = AsyncMock()
    notifier.add_sink(sink)

    await events.emit("task.completed", {"task_id": "t-2"})
    notification = sink.call_args[0][0]
    assert notification.level == NotificationLevel.SUCCESS
    assert notification.title == "Task Completed"


async def test_task_failed_generates_notification(events: EventEmitter, notifier: Notifier) -> None:
    sink = AsyncMock()
    notifier.add_sink(sink)

    await events.emit("task.failed", {"task_id": "t-3", "error": "timeout"})
    notification = sink.call_args[0][0]
    assert notification.level == NotificationLevel.ERROR
    assert "timeout" in notification.body


async def test_milestone_completed_notification(events: EventEmitter, notifier: Notifier) -> None:
    sink = AsyncMock()
    notifier.add_sink(sink)

    await events.emit("milestone.completed", {"milestone_id": "m-1"}, task_id="t-1")
    notification = sink.call_args[0][0]
    assert notification.level == NotificationLevel.MILESTONE


async def test_gate_failed_notification(events: EventEmitter, notifier: Notifier) -> None:
    sink = AsyncMock()
    notifier.add_sink(sink)

    await events.emit("ledger.gate_failed", {"gate": 4}, task_id="t-1")
    notification = sink.call_args[0][0]
    assert notification.level == NotificationLevel.ERROR
    assert "Gate" in notification.body


# --- History ---


async def test_notification_history(notifier: Notifier) -> None:
    sink = AsyncMock()
    notifier.add_sink(sink)

    for i in range(5):
        n = Notification(level=NotificationLevel.INFO, title=f"Notif {i}")
        await notifier.send(n)

    history = notifier.get_history()
    assert len(history) == 5


async def test_notification_history_filtered(notifier: Notifier) -> None:
    sink = AsyncMock()
    notifier.add_sink(sink)

    await notifier.send(Notification(level=NotificationLevel.INFO, title="Info"))
    await notifier.send(Notification(level=NotificationLevel.ERROR, title="Error"))
    await notifier.send(Notification(level=NotificationLevel.INFO, title="Info 2"))

    errors = notifier.get_history(level=NotificationLevel.ERROR)
    assert len(errors) == 1
    assert errors[0].title == "Error"


# --- Subscribe idempotency ---


def test_subscribe_idempotent(events: EventEmitter) -> None:
    n = Notifier(events)
    n.subscribe()
    n.subscribe()  # Should not double-subscribe
    # Check handler count for one event
    assert len(events._handlers.get("task.started", [])) == 1
