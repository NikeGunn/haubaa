"""Phase 4 Integration Tests — Channels + Notifier + Gateway pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock

from hauba.channels.gateway import ChannelGateway, ChannelMessage, ChannelType
from hauba.core.events import EventEmitter
from hauba.core.notifier import Notification, NotificationLevel, Notifier


async def test_full_notification_pipeline() -> None:
    """Events → Notifier → Sinks → Gateway → Channels.

    Verifies the complete Phase 4 pipeline: an event triggers a notification
    which is delivered through the gateway to registered channels.
    """
    events = EventEmitter()
    notifier = Notifier(events)

    # Track all notifications
    received: list[Notification] = []

    async def capture_sink(n: Notification) -> None:
        received.append(n)

    notifier.add_sink(capture_sink)
    notifier.subscribe()

    # Set up gateway with mock channel
    gateway = ChannelGateway(events)
    mock_channel = AsyncMock()
    mock_channel.broadcast = AsyncMock()
    gateway.register_channel(ChannelType.WEB, mock_channel)

    # Simulate a task lifecycle
    await events.emit("task.started", {"task_id": "t-1", "instruction": "build app"})
    await events.emit("milestone.completed", {"milestone_id": "m-1"}, task_id="t-1")
    await events.emit("task.completed", {"task_id": "t-1"})

    # Verify notifications were captured
    assert len(received) == 3
    assert received[0].level == NotificationLevel.INFO
    assert received[1].level == NotificationLevel.MILESTONE
    assert received[2].level == NotificationLevel.SUCCESS

    # Send notifications through gateway
    for n in received:
        await gateway.notify(f"{n.title}: {n.body}")

    assert mock_channel.broadcast.call_count == 3


async def test_gateway_routes_messages_to_agent() -> None:
    """Channel message → Gateway → Task handler."""
    events = EventEmitter()
    gateway = ChannelGateway(events)

    tasks_received: list[str] = []

    async def handle_message(msg: ChannelMessage) -> None:
        tasks_received.append(msg.text)

    gateway.set_message_handler(handle_message)

    # Simulate messages from different channels
    msg1 = ChannelMessage(text="build a website", channel=ChannelType.TELEGRAM, sender_id="tg-1")
    msg2 = ChannelMessage(text="deploy to AWS", channel=ChannelType.DISCORD, sender_id="dc-1")

    await gateway.route_message(msg1)
    await gateway.route_message(msg2)

    assert len(tasks_received) == 2
    assert "build a website" in tasks_received
    assert "deploy to AWS" in tasks_received


async def test_notifier_with_error_events() -> None:
    """Error events generate error-level notifications."""
    events = EventEmitter()
    notifier = Notifier(events)

    errors: list[Notification] = []

    async def error_sink(n: Notification) -> None:
        if n.level == NotificationLevel.ERROR:
            errors.append(n)

    notifier.add_sink(error_sink)
    notifier.subscribe()

    await events.emit("task.failed", {"task_id": "t-1", "error": "LLM timeout"})
    await events.emit("ledger.gate_failed", {"gate": 5}, task_id="t-1")

    assert len(errors) == 2
    assert "LLM timeout" in errors[0].body
    assert "Gate" in errors[1].body
