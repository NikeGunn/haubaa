"""WhatsApp channel — Twilio WhatsApp API integration."""

from __future__ import annotations

from typing import Any

import structlog

from hauba.core.events import EventEmitter
from hauba.core.types import Event
from hauba.exceptions import HaubaError

logger = structlog.get_logger()

try:
    from twilio.rest import Client as TwilioClient  # type: ignore[import-untyped]

    WHATSAPP_AVAILABLE = True
except ImportError:
    WHATSAPP_AVAILABLE = False


class WhatsAppChannelError(HaubaError):
    """WhatsApp channel error."""


class WhatsAppChannel:
    """WhatsApp channel for interacting with Hauba via Twilio WhatsApp API.

    Supports:
    - Sending messages to WhatsApp numbers
    - Broadcasting task status updates
    - Receiving messages via webhook (FastAPI integration)

    Requires:
    - Twilio account with WhatsApp sandbox or approved number
    - pip install twilio
    """

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        events: EventEmitter,
        on_message: Any = None,
    ) -> None:
        if not WHATSAPP_AVAILABLE:
            raise WhatsAppChannelError("twilio not installed. Run: pip install twilio")

        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number  # e.g., "whatsapp:+14155238886"
        self.events = events
        self._on_message = on_message
        self._client: Any = None
        self._recipient_numbers: set[str] = set()

    async def start(self) -> None:
        """Initialize the Twilio client."""
        self._client = TwilioClient(self.account_sid, self.auth_token)

        # Subscribe to events for progress updates
        self.events.on("task.completed", self._on_task_event)
        self.events.on("task.failed", self._on_task_event)

        logger.info("whatsapp.started")

    async def stop(self) -> None:
        """Stop the WhatsApp channel."""
        self._client = None
        logger.info("whatsapp.stopped")

    async def send_message(self, to_number: str, text: str) -> None:
        """Send a WhatsApp message to a specific number.

        Args:
            to_number: Recipient number in format "whatsapp:+1234567890"
            text: Message text (max 1600 chars for WhatsApp)
        """
        if not self._client:
            raise WhatsAppChannelError("WhatsApp channel not started")

        # Ensure whatsapp: prefix
        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"

        # WhatsApp message limit is 1600 chars, truncate if needed
        if len(text) > 1600:
            text = text[:1597] + "..."

        try:
            self._client.messages.create(
                body=text,
                from_=self.from_number,
                to=to_number,
            )
            self._recipient_numbers.add(to_number)
            logger.info("whatsapp.message_sent", to=to_number)
        except Exception as exc:
            logger.error("whatsapp.send_failed", to=to_number, error=str(exc))
            raise WhatsAppChannelError(f"Failed to send WhatsApp message: {exc}")

    async def broadcast(self, text: str) -> None:
        """Send a message to all known recipients."""
        for number in self._recipient_numbers:
            try:
                await self.send_message(number, text)
            except Exception as exc:
                logger.error(
                    "whatsapp.broadcast_failed",
                    number=number,
                    error=str(exc),
                )

    def add_recipient(self, number: str) -> None:
        """Add a recipient number for broadcasts.

        Args:
            number: Phone number in format "+1234567890" or "whatsapp:+1234567890"
        """
        if not number.startswith("whatsapp:"):
            number = f"whatsapp:{number}"
        self._recipient_numbers.add(number)

    async def handle_incoming_webhook(self, form_data: dict[str, str]) -> None:
        """Handle incoming WhatsApp message from Twilio webhook.

        This should be called from a FastAPI/Flask endpoint that receives
        Twilio's webhook POST when a user sends a WhatsApp message.

        Args:
            form_data: The parsed form data from the Twilio webhook.
        """
        body = form_data.get("Body", "")
        from_num = form_data.get("From", "")

        if not body or not from_num:
            return

        self._recipient_numbers.add(from_num)
        logger.info(
            "whatsapp.message_received",
            from_number=from_num,
            length=len(body),
        )

        if self._on_message:
            await self._on_message(body, from_num)

    async def _on_task_event(self, event: Event) -> None:
        """Forward task events to all connected recipients."""
        topic = event.topic
        data = event.data

        if topic == "task.completed":
            msg = f"Task completed: {data.get('task_id', 'unknown')}"
        elif topic == "task.failed":
            msg = f"Task failed: {data.get('error', 'unknown error')}"
        else:
            return

        await self.broadcast(msg)
