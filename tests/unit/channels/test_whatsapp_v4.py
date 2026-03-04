"""Tests for WhatsApp V4.0 commands."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from hauba.channels.whatsapp_webhook import WhatsAppBot
from hauba.daemon.queue import TaskQueue


@pytest.fixture
def bot() -> WhatsAppBot:
    b = WhatsAppBot()
    b._send_reply = AsyncMock()  # type: ignore[assignment]
    return b


@pytest.fixture
def bot_with_queue(bot: WhatsAppBot) -> WhatsAppBot:
    queue = TaskQueue()
    bot.set_task_queue(queue)
    return bot


class TestParseCommand:
    """Test WhatsAppBot._parse_command()."""

    def test_command_with_args(self) -> None:
        cmd, args = WhatsAppBot._parse_command("/cancel abc123")
        assert cmd == "/cancel"
        assert args == "abc123"

    def test_command_no_args(self) -> None:
        cmd, args = WhatsAppBot._parse_command("/tasks")
        assert cmd == "/tasks"
        assert args == ""

    def test_not_a_command(self) -> None:
        cmd, args = WhatsAppBot._parse_command("build me a dashboard")
        assert cmd == ""
        assert args == "build me a dashboard"

    def test_command_case_insensitive(self) -> None:
        cmd, _args = WhatsAppBot._parse_command("/HELP")
        assert cmd == "/help"


class TestHandleTasks:
    """Test /tasks command."""

    @pytest.mark.asyncio
    async def test_no_queue(self, bot: WhatsAppBot) -> None:
        await bot._handle_tasks("whatsapp:+1234")
        bot._send_reply.assert_called_once()
        assert "No task queue" in bot._send_reply.call_args[0][1]

    @pytest.mark.asyncio
    async def test_no_tasks(self, bot_with_queue: WhatsAppBot) -> None:
        await bot_with_queue._handle_tasks("whatsapp:+1234")
        assert "No tasks" in bot_with_queue._send_reply.call_args[0][1]

    @pytest.mark.asyncio
    async def test_with_tasks(self, bot_with_queue: WhatsAppBot) -> None:
        bot_with_queue._task_queue.submit(
            "whatsapp:+1234",
            "build something",
            channel="whatsapp",
            channel_address="whatsapp:+1234",
        )
        await bot_with_queue._handle_tasks("whatsapp:+1234")
        reply = bot_with_queue._send_reply.call_args[0][1]
        assert "build something" in reply


class TestHandleCancel:
    """Test /cancel command."""

    @pytest.mark.asyncio
    async def test_cancel_no_args(self, bot_with_queue: WhatsAppBot) -> None:
        await bot_with_queue._handle_cancel("whatsapp:+1234", "")
        assert "Usage" in bot_with_queue._send_reply.call_args[0][1]

    @pytest.mark.asyncio
    async def test_cancel_existing_task(self, bot_with_queue: WhatsAppBot) -> None:
        task = bot_with_queue._task_queue.submit("whatsapp:+1234", "build app")
        prefix = task.task_id[:8]
        await bot_with_queue._handle_cancel("whatsapp:+1234", prefix)
        assert "cancelled" in bot_with_queue._send_reply.call_args[0][1].lower()

    @pytest.mark.asyncio
    async def test_cancel_not_found(self, bot_with_queue: WhatsAppBot) -> None:
        await bot_with_queue._handle_cancel("whatsapp:+1234", "nonexist")
        assert "No task found" in bot_with_queue._send_reply.call_args[0][1]


class TestHandleRetry:
    """Test /retry command."""

    @pytest.mark.asyncio
    async def test_retry_no_args(self, bot_with_queue: WhatsAppBot) -> None:
        await bot_with_queue._handle_retry("whatsapp:+1234", "")
        assert "Usage" in bot_with_queue._send_reply.call_args[0][1]

    @pytest.mark.asyncio
    async def test_retry_failed_task(self, bot_with_queue: WhatsAppBot) -> None:
        task = bot_with_queue._task_queue.submit("whatsapp:+1234", "build dashboard")
        task.status = "failed"
        prefix = task.task_id[:8]
        await bot_with_queue._handle_retry("whatsapp:+1234", prefix)
        assert "retried" in bot_with_queue._send_reply.call_args[0][1].lower()


class TestHandleWeb:
    """Test /web command."""

    @pytest.mark.asyncio
    async def test_no_url(self, bot: WhatsAppBot) -> None:
        await bot._handle_web("whatsapp:+1234", "")
        assert "Usage" in bot._send_reply.call_args[0][1]


class TestHandleEmail:
    """Test /email command."""

    @pytest.mark.asyncio
    async def test_no_email_service(self, bot: WhatsAppBot) -> None:
        await bot._handle_email("whatsapp:+1234", "user@test.com subject")
        assert "not configured" in bot._send_reply.call_args[0][1].lower()

    @pytest.mark.asyncio
    async def test_no_args(self, bot: WhatsAppBot) -> None:
        bot._email_service = AsyncMock()
        bot._email_service.is_configured = True
        await bot._handle_email("whatsapp:+1234", "")
        assert "Usage" in bot._send_reply.call_args[0][1]


class TestHandleReply:
    """Test /reply command."""

    @pytest.mark.asyncio
    async def test_no_assistant(self, bot: WhatsAppBot) -> None:
        await bot._handle_reply_cmd("whatsapp:+1234", "I'm away")
        assert "not available" in bot._send_reply.call_args[0][1].lower()

    @pytest.mark.asyncio
    async def test_set_reply(self, bot: WhatsAppBot) -> None:
        from hauba.services.reply_assistant import ReplyAssistant

        bot._reply_assistant = ReplyAssistant()
        await bot._handle_reply_cmd("whatsapp:+1234", "Out of office")
        assert "set" in bot._send_reply.call_args[0][1].lower()

    @pytest.mark.asyncio
    async def test_disable_reply(self, bot: WhatsAppBot) -> None:
        from hauba.services.reply_assistant import ReplyAssistant

        bot._reply_assistant = ReplyAssistant()
        await bot._handle_reply_cmd("whatsapp:+1234", "off")
        assert "disabled" in bot._send_reply.call_args[0][1].lower()


class TestHandleUsage:
    """Test /usage command."""

    @pytest.mark.asyncio
    async def test_no_queue(self, bot: WhatsAppBot) -> None:
        await bot._handle_usage("whatsapp:+1234")
        assert "no usage data" in bot._send_reply.call_args[0][1].lower()

    @pytest.mark.asyncio
    async def test_with_tasks(self, bot_with_queue: WhatsAppBot) -> None:
        bot_with_queue._task_queue.submit("whatsapp:+1234", "task 1")
        await bot_with_queue._handle_usage("whatsapp:+1234")
        reply = bot_with_queue._send_reply.call_args[0][1]
        assert "Total tasks" in reply


class TestHandlePlugins:
    """Test /plugins command."""

    @pytest.mark.asyncio
    async def test_no_registry(self, bot: WhatsAppBot) -> None:
        await bot._handle_plugins("whatsapp:+1234")
        assert "No plugins" in bot._send_reply.call_args[0][1]


class TestHandleFeedback:
    """Test /feedback command."""

    @pytest.mark.asyncio
    async def test_no_message(self, bot: WhatsAppBot) -> None:
        await bot._handle_feedback("whatsapp:+1234", "")
        assert "Usage" in bot._send_reply.call_args[0][1]

    @pytest.mark.asyncio
    async def test_feedback_received(self, bot: WhatsAppBot) -> None:
        await bot._handle_feedback("whatsapp:+1234", "Great product!")
        assert "Thank you" in bot._send_reply.call_args[0][1]
