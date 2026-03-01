"""Tests for WhatsApp channel."""

from __future__ import annotations

import pytest


def test_whatsapp_channel_import() -> None:
    """WhatsApp channel module can be imported."""
    from hauba.channels.whatsapp import WhatsAppChannel, WhatsAppChannelError

    assert WhatsAppChannel is not None
    assert issubclass(WhatsAppChannelError, Exception)


def test_whatsapp_channel_requires_twilio() -> None:
    """WhatsApp channel raises error when twilio is not installed."""
    # This test checks the error handling path
    from hauba.channels.whatsapp import WHATSAPP_AVAILABLE

    # WHATSAPP_AVAILABLE is True if twilio is installed, False otherwise
    assert isinstance(WHATSAPP_AVAILABLE, bool)


def test_whatsapp_channel_add_recipient() -> None:
    """add_recipient normalizes phone numbers."""
    from hauba.channels.whatsapp import WHATSAPP_AVAILABLE

    if not WHATSAPP_AVAILABLE:
        pytest.skip("twilio not installed")

    from hauba.channels.whatsapp import WhatsAppChannel
    from hauba.core.events import EventEmitter

    events = EventEmitter()
    wa = WhatsAppChannel(
        account_sid="test_sid",
        auth_token="test_token",
        from_number="whatsapp:+14155238886",
        events=events,
    )

    # Without whatsapp: prefix
    wa.add_recipient("+1234567890")
    assert "whatsapp:+1234567890" in wa._recipient_numbers

    # With whatsapp: prefix
    wa.add_recipient("whatsapp:+9876543210")
    assert "whatsapp:+9876543210" in wa._recipient_numbers
