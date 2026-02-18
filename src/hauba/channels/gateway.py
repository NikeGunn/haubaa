"""Channel gateway — unified message routing across all channels."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

from hauba.core.events import EventEmitter

logger = structlog.get_logger()


class ChannelType(str, Enum):
    """Supported channel types."""

    TELEGRAM = "telegram"
    DISCORD = "discord"
    WEB = "web"
    VOICE = "voice"
    CLI = "cli"


@dataclass
class ChannelMessage:
    """Unified message format across all channels."""

    text: str
    channel: ChannelType
    sender_id: str
    channel_ref: int | str = 0  # chat_id, channel_id, session_id
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    attachments: list[str] = field(default_factory=list)


# Type for message handlers
MessageHandler = Callable[[ChannelMessage], Coroutine[Any, Any, None]]


class ChannelGateway:
    """Unified gateway that routes messages from any channel to the agent system.

    All channels feed into a single message handler. The gateway also routes
    notifications back to the appropriate channels.

    Rate limiting prevents flooding any single channel.
    """

    def __init__(self, events: EventEmitter) -> None:
        self.events = events
        self._channels: dict[ChannelType, Any] = {}
        self._message_handler: MessageHandler | None = None
        self._rate_limits: dict[str, float] = {}  # sender_id → last_message_time
        self._rate_limit_seconds: float = 1.0

    def register_channel(self, channel_type: ChannelType, channel: Any) -> None:
        """Register a channel with the gateway."""
        self._channels[channel_type] = channel
        logger.info("gateway.channel_registered", channel=channel_type.value)

    def set_message_handler(self, handler: MessageHandler) -> None:
        """Set the handler that processes incoming messages from any channel."""
        self._message_handler = handler

    async def route_message(self, message: ChannelMessage) -> bool:
        """Route an incoming message to the handler with rate limiting.

        Returns:
            True if the message was processed, False if rate-limited.
        """
        # Rate limiting
        now = datetime.now(UTC).timestamp()
        last = self._rate_limits.get(message.sender_id, 0)
        if now - last < self._rate_limit_seconds:
            logger.warning(
                "gateway.rate_limited",
                sender=message.sender_id,
                channel=message.channel.value,
            )
            return False

        self._rate_limits[message.sender_id] = now

        if self._message_handler:
            try:
                await self._message_handler(message)
                return True
            except Exception as exc:
                logger.error(
                    "gateway.handler_error",
                    error=str(exc),
                    channel=message.channel.value,
                )
                return False

        logger.warning("gateway.no_handler")
        return False

    async def notify(
        self,
        text: str,
        channels: list[ChannelType] | None = None,
        sender_id: str | None = None,
    ) -> int:
        """Send a notification to one or more channels.

        Args:
            text: The notification text.
            channels: Target channels (all if None).
            sender_id: Optional — route to the specific sender's channel reference.

        Returns:
            Number of channels notified successfully.
        """
        targets = channels or list(self._channels.keys())
        sent = 0

        for ch_type in targets:
            channel = self._channels.get(ch_type)
            if channel is None:
                continue

            try:
                if hasattr(channel, "broadcast"):
                    await channel.broadcast(text)
                    sent += 1
            except Exception as exc:
                logger.error(
                    "gateway.notify_failed",
                    channel=ch_type.value,
                    error=str(exc),
                )

        return sent

    @property
    def active_channels(self) -> list[ChannelType]:
        """List currently registered channels."""
        return list(self._channels.keys())
