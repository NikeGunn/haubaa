"""Tests for WhatsApp bot queue integration."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from hauba.channels.whatsapp_webhook import WhatsAppBot
from hauba.daemon.queue import TaskQueue


class TestIsBuildTask:
    """Test build task detection."""

    def test_short_messages_are_chat(self) -> None:
        assert WhatsAppBot._is_build_task("hi") is False
        assert WhatsAppBot._is_build_task("hello") is False
        assert WhatsAppBot._is_build_task("thanks") is False

    def test_build_keywords_detected(self) -> None:
        assert WhatsAppBot._is_build_task("build me a todo app") is True
        assert WhatsAppBot._is_build_task("create a REST API with auth") is True
        assert WhatsAppBot._is_build_task("make a SaaS dashboard") is True
        assert WhatsAppBot._is_build_task("deploy this to Railway") is True

    def test_code_keywords_detected(self) -> None:
        assert WhatsAppBot._is_build_task("write a Python script to parse CSV") is True
        assert WhatsAppBot._is_build_task("generate a landing page with HTML") is True
        assert WhatsAppBot._is_build_task("implement user authentication") is True

    def test_general_chat_not_detected(self) -> None:
        assert WhatsAppBot._is_build_task("what can you do?") is False
        assert WhatsAppBot._is_build_task("how are you today") is False
        assert WhatsAppBot._is_build_task("tell me about hauba") is False

    def test_no_substring_false_positives(self) -> None:
        """Word-boundary matching prevents 'app' in 'appear' etc."""
        assert (
            WhatsAppBot._is_build_task(
                "Wait 10 second it fetches slowly and the full project will be appear"
            )
            is False
        )
        assert (
            WhatsAppBot._is_build_task("the restaurant has a nice atmosphere and appealing decor")
            is False
        )
        assert WhatsAppBot._is_build_task("she is an authority on the codebreaking topic") is False

    def test_conversational_messages_excluded(self) -> None:
        """Messages starting with wait/thanks/ok are not build tasks."""
        assert WhatsAppBot._is_build_task("wait a moment I need to think about this") is False
        assert WhatsAppBot._is_build_task("thanks for the help with everything") is False
        assert WhatsAppBot._is_build_task("ok I will check and let you know later") is False

    def test_url_fetch_excluded(self) -> None:
        """URL fetch/browse requests should not be queued as build tasks."""
        assert WhatsAppBot._is_build_task("fetch https://example.com and find key points") is False
        assert (
            WhatsAppBot._is_build_task("visit nikhilbhagat.com.np/ and summarize the projects")
            is False
        )


class TestSetTaskQueue:
    """Test task queue wiring."""

    def test_set_task_queue(self) -> None:
        bot = WhatsAppBot()
        queue = TaskQueue()
        bot.set_task_queue(queue)
        assert bot._task_queue is queue

    def test_no_queue_by_default(self) -> None:
        bot = WhatsAppBot()
        assert bot._task_queue is None


class TestQueueBuildTask:
    """Test queuing build tasks."""

    @pytest.mark.asyncio
    async def test_queue_build_task_with_queue(self) -> None:
        bot = WhatsAppBot()
        queue = TaskQueue()
        bot.set_task_queue(queue)
        bot._send_reply = AsyncMock()  # type: ignore[assignment]

        await bot._queue_build_task("whatsapp:+1234", "build me a todo app")

        # Task should be in the queue
        tasks = queue.poll("whatsapp:+1234")
        assert len(tasks) == 1
        assert tasks[0].instruction == "build me a todo app"
        assert tasks[0].channel == "whatsapp"
        assert tasks[0].channel_address == "whatsapp:+1234"

        # Should have sent a confirmation
        bot._send_reply.assert_called_once()
        call_args = bot._send_reply.call_args
        assert "Task Queued" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_queue_build_task_without_queue_falls_back(self) -> None:
        """Without a queue, falls back to direct execution."""
        bot = WhatsAppBot()
        bot._send_reply = AsyncMock()  # type: ignore[assignment]
        bot._process_with_progress = AsyncMock(return_value="Done!")  # type: ignore[assignment]

        await bot._queue_build_task("whatsapp:+1234", "build me an app")

        # Should have used process_with_progress as fallback
        bot._process_with_progress.assert_called_once()


class TestSendStatus:
    """Test status command."""

    @pytest.mark.asyncio
    async def test_status_no_queue(self) -> None:
        bot = WhatsAppBot()
        bot._send_reply = AsyncMock()  # type: ignore[assignment]

        await bot._send_status("whatsapp:+1234")
        bot._send_reply.assert_called_once()
        assert "No task queue" in bot._send_reply.call_args[0][1]

    @pytest.mark.asyncio
    async def test_status_no_tasks(self) -> None:
        bot = WhatsAppBot()
        queue = TaskQueue()
        bot.set_task_queue(queue)
        bot._send_reply = AsyncMock()  # type: ignore[assignment]

        await bot._send_status("whatsapp:+1234")
        bot._send_reply.assert_called_once()
        assert "No tasks found" in bot._send_reply.call_args[0][1]

    @pytest.mark.asyncio
    async def test_status_with_tasks(self) -> None:
        bot = WhatsAppBot()
        queue = TaskQueue()
        bot.set_task_queue(queue)
        bot._send_reply = AsyncMock()  # type: ignore[assignment]

        queue.submit("whatsapp:+1234", "build a todo app", channel="whatsapp")

        await bot._send_status("whatsapp:+1234")
        bot._send_reply.assert_called_once()
        msg = bot._send_reply.call_args[0][1]
        assert "Your Tasks" in msg
        assert "todo app" in msg


class TestStatusCommand:
    """Test the /status command in handle_message."""

    @pytest.mark.asyncio
    async def test_status_command(self) -> None:
        bot = WhatsAppBot()
        queue = TaskQueue()
        bot.set_task_queue(queue)
        bot._send_reply = AsyncMock()  # type: ignore[assignment]

        await bot.handle_message("/status", "whatsapp:+1234")
        bot._send_reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_clears_queue(self) -> None:
        bot = WhatsAppBot()
        queue = TaskQueue()
        bot.set_task_queue(queue)
        bot._send_reply = AsyncMock()  # type: ignore[assignment]

        queue.submit("whatsapp:+1234", "build app", channel="whatsapp")
        assert queue.size == 1

        await bot.handle_message("/clear", "whatsapp:+1234")
        assert queue.size == 0
