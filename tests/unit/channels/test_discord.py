"""Tests for DiscordChannel — discord.py integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hauba.core.events import EventEmitter

# --- Graceful degradation ---


def test_discord_unavailable_raises() -> None:
    with patch("hauba.channels.discord.DISCORD_AVAILABLE", False):
        from hauba.channels.discord import DiscordChannel, DiscordChannelError

        events = EventEmitter()
        with pytest.raises(DiscordChannelError, match="discord.py not installed"):
            DiscordChannel(token="fake", events=events)


# --- Construction with deps available ---


def test_discord_channel_creates_with_mock_deps() -> None:
    mock_intents = MagicMock()
    mock_intents.default.return_value = mock_intents

    with patch("hauba.channels.discord.DISCORD_AVAILABLE", True), \
         patch("hauba.channels.discord.discord", create=True) as mock_discord, \
         patch("hauba.channels.discord.commands", create=True) as mock_commands:
        mock_discord.Intents = mock_intents
        mock_bot = MagicMock()
        mock_commands.Bot = MagicMock(return_value=mock_bot)

        events = EventEmitter()
        from hauba.channels.discord import DiscordChannel

        channel = DiscordChannel(token="test-token", events=events)
        assert channel.token == "test-token"


# --- Event forwarding ---


async def test_discord_on_task_event_broadcasts() -> None:
    mock_intents = MagicMock()
    mock_intents.default.return_value = mock_intents

    with patch("hauba.channels.discord.DISCORD_AVAILABLE", True), \
         patch("hauba.channels.discord.discord", create=True) as mock_discord, \
         patch("hauba.channels.discord.commands", create=True) as mock_commands:
        mock_discord.Intents = mock_intents
        mock_commands.Bot = MagicMock(return_value=MagicMock())

        events = EventEmitter()
        from hauba.channels.discord import DiscordChannel
        from hauba.core.types import Event

        channel = DiscordChannel(token="t", events=events)
        channel.broadcast = AsyncMock()

        event = Event(topic="task.failed", data={"error": "timeout"})
        await channel._on_task_event(event)
        channel.broadcast.assert_called_once()
        assert "timeout" in channel.broadcast.call_args[0][0]
