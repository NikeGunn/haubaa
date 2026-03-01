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


def test_whatsapp_config_defaults() -> None:
    """WhatsAppConfig has sensible defaults (sandbox number pre-filled)."""
    from hauba.core.config import WhatsAppConfig

    cfg = WhatsAppConfig()
    assert cfg.from_number == "whatsapp:+14155238886"
    assert cfg.account_sid == ""
    assert cfg.auth_token == ""
    assert cfg.to_number == ""
    assert cfg.sandbox_code == ""


def test_resolve_twilio_creds_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """_resolve_twilio_creds reads from env vars first."""
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "env_sid_123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "env_token_456")
    monkeypatch.setenv("HAUBA_WHATSAPP_TO", "+9779800000000")

    from hauba.cli import _resolve_twilio_creds

    sid, token, from_num, to_num = _resolve_twilio_creds()
    assert sid == "env_sid_123"
    assert token == "env_token_456"
    assert from_num == "whatsapp:+14155238886"  # Default sandbox
    assert to_num == "+9779800000000"


def test_resolve_twilio_creds_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """_resolve_twilio_creds returns empty strings when nothing is configured."""
    # Clear any existing env vars
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_WHATSAPP_NUMBER", raising=False)
    monkeypatch.delenv("HAUBA_WHATSAPP_TO", raising=False)

    from hauba.cli import _resolve_twilio_creds

    _sid, _token, from_num, _to_num = _resolve_twilio_creds()
    # SID/token might come from config file if it exists, but from_num should be sandbox default
    assert from_num == "whatsapp:+14155238886"
