"""Discord channel — discord.py integration."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from hauba.core.events import EventEmitter
from hauba.core.types import Event
from hauba.exceptions import HaubaError

logger = structlog.get_logger()

try:
    import discord  # type: ignore[import-untyped]
    from discord.ext import commands  # type: ignore[import-untyped]

    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False


class DiscordChannelError(HaubaError):
    """Discord channel error."""


class DiscordChannel:
    """Discord bot channel for interacting with Hauba via Discord.

    Supports:
    - !hauba <task> — Submit a task
    - !status — Show current agent status
    - !help — Show available commands
    - Event-driven progress notifications
    """

    def __init__(
        self,
        token: str,
        events: EventEmitter,
        on_message: Any = None,
        command_prefix: str = "!",
    ) -> None:
        if not DISCORD_AVAILABLE:
            raise DiscordChannelError(
                "discord.py not installed. Run: pip install hauba[channels]"
            )

        self.token = token
        self.events = events
        self._on_message = on_message
        self._channel_ids: set[int] = set()

        intents = discord.Intents.default()
        intents.message_content = True

        self._bot = commands.Bot(command_prefix=command_prefix, intents=intents)
        self._setup_commands()

    def _setup_commands(self) -> None:
        """Register bot commands."""

        @self._bot.command(name="hauba")
        async def hauba_cmd(ctx: Any, *, task: str) -> None:
            """Submit a task to the AI team."""
            self._channel_ids.add(ctx.channel.id)
            await ctx.send(f"Working on: {task[:200]}...")
            logger.info("discord.task_received", channel=ctx.channel.id, task=task[:100])

            if self._on_message:
                await self._on_message(task, ctx.channel.id)

        @self._bot.command(name="status")
        async def status_cmd(ctx: Any) -> None:
            """Show Hauba status."""
            self._channel_ids.add(ctx.channel.id)
            await ctx.send("Hauba is online and ready for tasks.")

        @self._bot.event
        async def on_ready() -> None:
            logger.info("discord.connected", user=str(self._bot.user))

    async def start(self) -> None:
        """Start the Discord bot (non-blocking)."""
        # Subscribe to events
        self.events.on("task.completed", self._on_task_event)
        self.events.on("task.failed", self._on_task_event)

        # Start bot in background
        asyncio.create_task(self._bot.start(self.token))
        logger.info("discord.starting")

    async def stop(self) -> None:
        """Stop the Discord bot."""
        await self._bot.close()
        logger.info("discord.stopped")

    async def send_message(self, channel_id: int, text: str) -> None:
        """Send a message to a specific channel."""
        channel = self._bot.get_channel(channel_id)
        if channel:
            await channel.send(text)

    async def broadcast(self, text: str) -> None:
        """Send a message to all known channels."""
        for channel_id in self._channel_ids:
            try:
                await self.send_message(channel_id, text)
            except Exception as exc:
                logger.error("discord.broadcast_failed", channel_id=channel_id, error=str(exc))

    async def _on_task_event(self, event: Event) -> None:
        """Forward task events to all connected channels."""
        topic = event.topic
        data = event.data

        if topic == "task.completed":
            msg = f"Task completed: {data.get('task_id', 'unknown')}"
        elif topic == "task.failed":
            msg = f"Task failed: {data.get('error', 'unknown error')}"
        else:
            return

        await self.broadcast(msg)
