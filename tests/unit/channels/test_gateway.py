"""Tests for ChannelGateway — unified message routing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from hauba.channels.gateway import ChannelGateway, ChannelMessage, ChannelType
from hauba.core.events import EventEmitter


@pytest.fixture
def events() -> EventEmitter:
    return EventEmitter()


@pytest.fixture
def gateway(events: EventEmitter) -> ChannelGateway:
    return ChannelGateway(events)


# --- Registration ---


def test_register_channel(gateway: ChannelGateway) -> None:
    mock_channel = MagicMock()
    gateway.register_channel(ChannelType.TELEGRAM, mock_channel)
    assert ChannelType.TELEGRAM in gateway.active_channels


def test_active_channels_empty_initially(gateway: ChannelGateway) -> None:
    assert gateway.active_channels == []


def test_multiple_channels(gateway: ChannelGateway) -> None:
    gateway.register_channel(ChannelType.TELEGRAM, MagicMock())
    gateway.register_channel(ChannelType.DISCORD, MagicMock())
    assert len(gateway.active_channels) == 2


# --- Message routing ---


async def test_route_message_calls_handler(gateway: ChannelGateway) -> None:
    handler = AsyncMock()
    gateway.set_message_handler(handler)

    msg = ChannelMessage(
        text="build an app",
        channel=ChannelType.CLI,
        sender_id="user-1",
    )
    result = await gateway.route_message(msg)
    assert result is True
    handler.assert_called_once_with(msg)


async def test_route_message_no_handler(gateway: ChannelGateway) -> None:
    msg = ChannelMessage(text="hello", channel=ChannelType.CLI, sender_id="u1")
    result = await gateway.route_message(msg)
    assert result is False


async def test_rate_limiting(gateway: ChannelGateway) -> None:
    handler = AsyncMock()
    gateway.set_message_handler(handler)
    gateway._rate_limit_seconds = 10.0  # 10 second rate limit

    msg = ChannelMessage(text="first", channel=ChannelType.CLI, sender_id="user-1")
    result1 = await gateway.route_message(msg)
    assert result1 is True

    msg2 = ChannelMessage(text="second", channel=ChannelType.CLI, sender_id="user-1")
    result2 = await gateway.route_message(msg2)
    assert result2 is False  # Rate limited

    assert handler.call_count == 1


async def test_rate_limiting_different_senders(gateway: ChannelGateway) -> None:
    handler = AsyncMock()
    gateway.set_message_handler(handler)
    gateway._rate_limit_seconds = 10.0

    msg1 = ChannelMessage(text="hello", channel=ChannelType.CLI, sender_id="user-1")
    msg2 = ChannelMessage(text="hello", channel=ChannelType.CLI, sender_id="user-2")

    await gateway.route_message(msg1)
    await gateway.route_message(msg2)
    assert handler.call_count == 2  # Different senders, both go through


# --- Notifications ---


async def test_notify_broadcasts_to_channels(gateway: ChannelGateway) -> None:
    mock_channel = AsyncMock()
    mock_channel.broadcast = AsyncMock()
    gateway.register_channel(ChannelType.WEB, mock_channel)

    sent = await gateway.notify("Task completed!")
    assert sent == 1
    mock_channel.broadcast.assert_called_once_with("Task completed!")


async def test_notify_specific_channels(gateway: ChannelGateway) -> None:
    mock_tg = AsyncMock()
    mock_tg.broadcast = AsyncMock()
    mock_discord = AsyncMock()
    mock_discord.broadcast = AsyncMock()

    gateway.register_channel(ChannelType.TELEGRAM, mock_tg)
    gateway.register_channel(ChannelType.DISCORD, mock_discord)

    sent = await gateway.notify("hello", channels=[ChannelType.TELEGRAM])
    assert sent == 1
    mock_tg.broadcast.assert_called_once_with("hello")
    mock_discord.broadcast.assert_not_called()


async def test_notify_handles_errors(gateway: ChannelGateway) -> None:
    mock_channel = AsyncMock()
    mock_channel.broadcast = AsyncMock(side_effect=Exception("Network error"))
    gateway.register_channel(ChannelType.TELEGRAM, mock_channel)

    sent = await gateway.notify("test")
    assert sent == 0  # Failed to send


# --- ChannelMessage ---


def test_channel_message_creation() -> None:
    msg = ChannelMessage(
        text="build a dashboard",
        channel=ChannelType.TELEGRAM,
        sender_id="tg-12345",
        channel_ref=12345,
    )
    assert msg.text == "build a dashboard"
    assert msg.channel == ChannelType.TELEGRAM
    assert msg.sender_id == "tg-12345"
    assert msg.channel_ref == 12345
    assert msg.attachments == []
