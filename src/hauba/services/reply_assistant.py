"""Reply assistant — auto-reply to messages on owner's behalf."""

from __future__ import annotations

import structlog

logger = structlog.get_logger()

# Memory namespace for reply assistant settings
REPLY_NAMESPACE = "autoreply"
REPLY_MESSAGE_KEY = "message"
REPLY_ENABLED_KEY = "enabled"


class ReplyAssistant:
    """Auto-reply to messages on owner's behalf.

    Stores auto-reply settings in MemoryStore (persistent SQLite).
    When enabled, returns the configured message for incoming messages.

    Usage:
        assistant = ReplyAssistant(memory_store)
        await assistant.set_auto_reply("I'm away. Will respond later.")
        await assistant.set_enabled(True)

        # On incoming message:
        reply = await assistant.handle_message("+1234", "hey are you there?")
        # → "I'm away. Will respond later."
    """

    def __init__(self, memory_store: object | None = None) -> None:
        self._store = memory_store
        # In-memory fallback when no store available
        self._message: str = ""
        self._enabled: bool = False

    async def set_auto_reply(self, message: str) -> None:
        """Set the auto-reply message."""
        self._message = message
        if self._store is not None:
            await self._store.set(REPLY_NAMESPACE, REPLY_MESSAGE_KEY, message)  # type: ignore[union-attr]
        logger.info("autoreply.message_set", length=len(message))

    async def get_auto_reply(self) -> str | None:
        """Get the current auto-reply message."""
        if self._store is not None:
            msg = await self._store.get(REPLY_NAMESPACE, REPLY_MESSAGE_KEY)  # type: ignore[union-attr]
            if msg:
                return msg
        return self._message or None

    async def set_enabled(self, enabled: bool) -> None:
        """Enable or disable auto-reply."""
        self._enabled = enabled
        if self._store is not None:
            await self._store.set(REPLY_NAMESPACE, REPLY_ENABLED_KEY, str(enabled).lower())  # type: ignore[union-attr]
        logger.info("autoreply.enabled_changed", enabled=enabled)

    async def is_enabled(self) -> bool:
        """Check if auto-reply is currently enabled."""
        if self._store is not None:
            val = await self._store.get(REPLY_NAMESPACE, REPLY_ENABLED_KEY)  # type: ignore[union-attr]
            if val is not None:
                return val.lower() == "true"
        return self._enabled

    async def handle_message(self, sender: str, text: str) -> str | None:
        """Handle an incoming message. Returns auto-reply if enabled, else None.

        Args:
            sender: The sender identifier (phone number, user ID, etc.).
            text: The incoming message text.

        Returns:
            The auto-reply message if enabled and configured, else None.
        """
        if not await self.is_enabled():
            return None

        reply = await self.get_auto_reply()
        if not reply:
            return None

        logger.info("autoreply.triggered", sender=sender, text_preview=text[:50])
        return reply
