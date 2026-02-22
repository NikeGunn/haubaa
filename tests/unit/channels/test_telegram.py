"""Tests for TelegramChannel — python-telegram-bot integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hauba.core.events import EventEmitter

# --- Graceful degradation ---


def test_telegram_unavailable_raises() -> None:
    with patch("hauba.channels.telegram.TELEGRAM_AVAILABLE", False):
        from hauba.channels.telegram import TelegramChannel, TelegramChannelError

        events = EventEmitter()
        with pytest.raises(TelegramChannelError, match="python-telegram-bot not installed"):
            TelegramChannel(token="fake", events=events)


# --- Construction with deps available ---


def test_telegram_channel_creates_with_mock_deps() -> None:
    """When telegram deps are mocked as available, channel constructs."""
    mock_app_builder = MagicMock()
    mock_app = MagicMock()
    mock_app_builder.token.return_value.build.return_value = mock_app

    with (
        patch("hauba.channels.telegram.TELEGRAM_AVAILABLE", True),
        patch("hauba.channels.telegram.Application", create=True),
        patch("hauba.channels.telegram.CommandHandler", create=True),
        patch("hauba.channels.telegram.MessageHandler", create=True),
        patch("hauba.channels.telegram.filters", create=True),
    ):
        events = EventEmitter()
        from hauba.channels.telegram import TelegramChannel

        channel = TelegramChannel(token="test-token", events=events)
        assert channel.token == "test-token"


# --- Event forwarding ---


async def test_telegram_on_task_event_broadcasts() -> None:
    """Task events should be broadcast to all known chats."""
    from hauba.channels.telegram import TelegramChannel
    from hauba.core.types import Event

    with (
        patch("hauba.channels.telegram.TELEGRAM_AVAILABLE", True),
        patch("hauba.channels.telegram.Application", create=True),
        patch("hauba.channels.telegram.CommandHandler", create=True),
        patch("hauba.channels.telegram.MessageHandler", create=True),
        patch("hauba.channels.telegram.filters", create=True),
    ):
        events = EventEmitter()
        channel = TelegramChannel(token="t", events=events)
        channel.broadcast = AsyncMock()
        channel._chat_ids = {123, 456}

        event = Event(topic="task.completed", data={"task_id": "t-1"})
        await channel._on_task_event(event)
        channel.broadcast.assert_called_once()
        assert "t-1" in channel.broadcast.call_args[0][0]
