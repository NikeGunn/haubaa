"""Telegram channel — python-telegram-bot integration."""

from __future__ import annotations

from typing import Any

import structlog

from hauba.core.events import EventEmitter
from hauba.core.types import Event
from hauba.exceptions import HaubaError

logger = structlog.get_logger()

try:
    from telegram import Update  # type: ignore[import-untyped]  # noqa: F401
    from telegram.ext import (  # type: ignore[import-untyped]
        Application,
        CommandHandler,
        MessageHandler,
        filters,
    )

    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False


class TelegramChannelError(HaubaError):
    """Telegram channel error."""


class TelegramChannel:
    """Telegram bot channel for interacting with Hauba via Telegram.

    Supports:
    - /start — Welcome message
    - /status — Show current agent status
    - Text messages → forwarded as tasks to Director
    - Inline progress updates during task execution
    """

    def __init__(
        self,
        token: str,
        events: EventEmitter,
        on_message: Any = None,
    ) -> None:
        if not TELEGRAM_AVAILABLE:
            raise TelegramChannelError(
                "python-telegram-bot not installed. Run: pip install hauba[channels]"
            )

        self.token = token
        self.events = events
        self._on_message = on_message
        self._app: Any = None
        self._chat_ids: set[int] = set()

    async def start(self) -> None:
        """Start the Telegram bot."""
        self._app = Application.builder().token(self.token).build()

        self._app.add_handler(CommandHandler("start", self._handle_start))
        self._app.add_handler(CommandHandler("status", self._handle_status))
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

        # Subscribe to events for progress updates
        self.events.on("task.completed", self._on_task_event)
        self.events.on("task.failed", self._on_task_event)

        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()  # type: ignore[union-attr]
        logger.info("telegram.started")

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        if self._app:
            await self._app.updater.stop()  # type: ignore[union-attr]
            await self._app.stop()
            await self._app.shutdown()
            logger.info("telegram.stopped")

    async def send_message(self, chat_id: int, text: str) -> None:
        """Send a message to a specific chat."""
        if self._app and self._app.bot:
            await self._app.bot.send_message(chat_id=chat_id, text=text)

    async def broadcast(self, text: str) -> None:
        """Send a message to all known chats."""
        for chat_id in self._chat_ids:
            try:
                await self.send_message(chat_id, text)
            except Exception as exc:
                logger.error("telegram.broadcast_failed", chat_id=chat_id, error=str(exc))

    async def _handle_start(self, update: Any, context: Any) -> None:
        """Handle /start command."""
        if update.effective_chat:
            self._chat_ids.add(update.effective_chat.id)
            await update.message.reply_text(
                "Welcome to Hauba AI!\n\n"
                "Send me a task description and I'll get my AI team working on it.\n\n"
                "Commands:\n"
                "/start — This message\n"
                "/status — Check agent status"
            )

    async def _handle_status(self, update: Any, context: Any) -> None:
        """Handle /status command."""
        if update.message:
            await update.message.reply_text("Hauba is online and ready for tasks.")

    async def _handle_message(self, update: Any, context: Any) -> None:
        """Handle incoming text messages as task requests."""
        if not update.message or not update.message.text:
            return

        if update.effective_chat:
            self._chat_ids.add(update.effective_chat.id)

        text = update.message.text
        chat_id = update.effective_chat.id if update.effective_chat else 0

        logger.info("telegram.message_received", chat_id=chat_id, length=len(text))

        await update.message.reply_text(f"Got it! Working on: {text[:100]}...")

        if self._on_message:
            await self._on_message(text, chat_id)

    async def _on_task_event(self, event: Event) -> None:
        """Forward task events to all connected chats."""
        topic = event.topic
        data = event.data

        if topic == "task.completed":
            msg = f"Task completed: {data.get('task_id', 'unknown')}"
        elif topic == "task.failed":
            msg = f"Task failed: {data.get('error', 'unknown error')}"
        else:
            return

        await self.broadcast(msg)
