"""Tests for ReplyAssistant."""

from __future__ import annotations

import pytest

from hauba.services.reply_assistant import ReplyAssistant


class TestReplyAssistant:
    """Test ReplyAssistant auto-reply functionality."""

    @pytest.mark.asyncio
    async def test_disabled_by_default(self) -> None:
        assistant = ReplyAssistant()
        assert await assistant.is_enabled() is False

    @pytest.mark.asyncio
    async def test_set_and_get_auto_reply(self) -> None:
        assistant = ReplyAssistant()
        await assistant.set_auto_reply("I'm away")
        result = await assistant.get_auto_reply()
        assert result == "I'm away"

    @pytest.mark.asyncio
    async def test_enable_disable(self) -> None:
        assistant = ReplyAssistant()
        await assistant.set_enabled(True)
        assert await assistant.is_enabled() is True
        await assistant.set_enabled(False)
        assert await assistant.is_enabled() is False

    @pytest.mark.asyncio
    async def test_handle_message_when_disabled(self) -> None:
        assistant = ReplyAssistant()
        await assistant.set_auto_reply("Away message")
        result = await assistant.handle_message("+1234", "hello")
        assert result is None  # Disabled, should not reply

    @pytest.mark.asyncio
    async def test_handle_message_when_enabled(self) -> None:
        assistant = ReplyAssistant()
        await assistant.set_auto_reply("I'm out of office")
        await assistant.set_enabled(True)
        result = await assistant.handle_message("+1234", "hello")
        assert result == "I'm out of office"

    @pytest.mark.asyncio
    async def test_handle_message_no_reply_set(self) -> None:
        assistant = ReplyAssistant()
        await assistant.set_enabled(True)
        result = await assistant.handle_message("+1234", "hello")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_auto_reply_not_set(self) -> None:
        assistant = ReplyAssistant()
        result = await assistant.get_auto_reply()
        assert result is None
