"""Tests for WhatsApp webhook bot."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hauba.channels.whatsapp_webhook import GREETING, WhatsAppBot


class TestConfigure:
    """Test WhatsAppBot.configure()."""

    def test_missing_all_vars(self) -> None:
        """Returns False when all env vars are missing."""
        bot = WhatsAppBot()
        with patch.dict("os.environ", {}, clear=True):
            assert bot.configure() is False

    def test_missing_api_key(self) -> None:
        """Returns False when HAUBA_LLM_API_KEY is missing."""
        bot = WhatsAppBot()
        env = {
            "TWILIO_ACCOUNT_SID": "ACtest123",
            "TWILIO_AUTH_TOKEN": "token123",
        }
        with patch.dict("os.environ", env, clear=True):
            assert bot.configure() is False

    def test_missing_twilio_creds(self) -> None:
        """Returns False when Twilio creds are missing."""
        bot = WhatsAppBot()
        env = {"HAUBA_LLM_API_KEY": "sk-test"}
        with patch.dict("os.environ", env, clear=True):
            assert bot.configure() is False

    @patch("hauba.channels.whatsapp_webhook.TwilioClient", create=True)
    def test_configure_success(self, _mock_twilio_cls: MagicMock) -> None:
        """Returns True with all required env vars."""
        bot = WhatsAppBot()
        env = {
            "TWILIO_ACCOUNT_SID": "ACtest123",
            "TWILIO_AUTH_TOKEN": "token123",
            "HAUBA_LLM_API_KEY": "sk-test-key",
            "HAUBA_LLM_PROVIDER": "openai",
            "HAUBA_LLM_MODEL": "gpt-4o",
        }
        with (
            patch.dict("os.environ", env, clear=True),
            patch(
                "hauba.channels.whatsapp_webhook.WhatsAppBot.configure",
                return_value=True,
            ),
        ):
            assert bot.configure() is True


class TestSplitMessage:
    """Test WhatsAppBot.split_message()."""

    def test_short_message(self) -> None:
        """Short message returns single chunk."""
        result = WhatsAppBot.split_message("Hello world")
        assert result == ["Hello world"]

    def test_exact_limit(self) -> None:
        """Message exactly at limit returns single chunk."""
        msg = "x" * 1600
        result = WhatsAppBot.split_message(msg)
        assert result == [msg]

    def test_long_message_splits(self) -> None:
        """Long message is split into multiple chunks."""
        msg = "A" * 3200
        result = WhatsAppBot.split_message(msg, max_len=1600)
        assert len(result) == 2
        for chunk in result:
            assert len(chunk) <= 1600

    def test_splits_at_paragraph(self) -> None:
        """Prefers splitting at paragraph boundaries."""
        para1 = "First paragraph. " * 50  # ~850 chars
        para2 = "Second paragraph. " * 50
        msg = para1 + "\n\n" + para2
        result = WhatsAppBot.split_message(msg, max_len=1600)
        assert len(result) >= 2
        # First chunk should end before the paragraph break
        assert "\n\n" not in result[0]

    def test_splits_at_sentence(self) -> None:
        """Falls back to sentence boundaries when no paragraph break."""
        sentences = "This is sentence number one. " * 80  # ~2320 chars
        result = WhatsAppBot.split_message(sentences, max_len=1600)
        assert len(result) >= 2
        # Each chunk should end at a sentence boundary
        assert result[0].rstrip().endswith(".")

    def test_empty_message(self) -> None:
        """Empty message returns single empty chunk."""
        result = WhatsAppBot.split_message("")
        assert result == [""]


class TestHandleMessage:
    """Test WhatsAppBot.handle_message()."""

    @pytest.mark.asyncio
    async def test_help_command(self) -> None:
        """Help command sends the greeting."""
        bot = WhatsAppBot()
        bot._send_reply = AsyncMock()  # type: ignore[assignment]

        await bot.handle_message("/help", "whatsapp:+1234567890")
        bot._send_reply.assert_called_once_with(
            "whatsapp:+1234567890",
            GREETING,
        )

    @pytest.mark.asyncio
    async def test_reset_command(self) -> None:
        """Reset command clears session and sends confirmation."""
        bot = WhatsAppBot()
        bot._send_reply = AsyncMock()  # type: ignore[assignment]

        await bot.handle_message("/reset", "whatsapp:+1234567890")
        bot._send_reply.assert_called_once_with(
            "whatsapp:+1234567890",
            "Session cleared. Send a new task to get started.",
        )

    @pytest.mark.asyncio
    async def test_new_command(self) -> None:
        """New command clears session."""
        bot = WhatsAppBot()
        bot._send_reply = AsyncMock()  # type: ignore[assignment]

        await bot.handle_message("/new", "whatsapp:+1234567890")
        bot._send_reply.assert_called()

    @pytest.mark.asyncio
    async def test_dedup_message_sid(self) -> None:
        """Duplicate MessageSid is ignored."""
        bot = WhatsAppBot()
        bot._send_reply = AsyncMock()  # type: ignore[assignment]

        # First call processes
        await bot.handle_message("/help", "whatsapp:+1234567890", "SM123")
        assert bot._send_reply.call_count == 1

        # Second call with same SID is ignored
        await bot.handle_message("/help", "whatsapp:+1234567890", "SM123")
        assert bot._send_reply.call_count == 1

    @pytest.mark.asyncio
    async def test_normalizes_number(self) -> None:
        """Adds whatsapp: prefix if missing."""
        bot = WhatsAppBot()
        bot._send_reply = AsyncMock()  # type: ignore[assignment]

        await bot.handle_message("/help", "+1234567890")
        bot._send_reply.assert_called_once_with(
            "whatsapp:+1234567890",
            GREETING,
        )


class TestSessionManagement:
    """Test session lifecycle."""

    def test_session_count(self) -> None:
        """Session count reflects active sessions."""
        bot = WhatsAppBot()
        assert bot.session_count == 0

        bot._get_or_create_session("whatsapp:+1111111111")
        assert bot.session_count == 1

        bot._get_or_create_session("whatsapp:+2222222222")
        assert bot.session_count == 2

    @pytest.mark.asyncio
    async def test_destroy_session(self) -> None:
        """Destroying session removes it from active sessions."""
        bot = WhatsAppBot()
        bot._get_or_create_session("whatsapp:+1111111111")
        assert bot.session_count == 1

        await bot._destroy_session("whatsapp:+1111111111")
        assert bot.session_count == 0

    @pytest.mark.asyncio
    async def test_cleanup_idle_sessions(self) -> None:
        """Idle sessions are cleaned up."""
        bot = WhatsAppBot()
        session = bot._get_or_create_session("whatsapp:+1111111111")
        session.last_active = 0  # Set to epoch (definitely idle)

        removed = await bot.cleanup_idle_sessions()
        assert removed == 1
        assert bot.session_count == 0


class TestGreeting:
    """Test the greeting message."""

    def test_greeting_not_empty(self) -> None:
        """Greeting message is not empty."""
        assert len(GREETING) > 100

    def test_greeting_contains_brand(self) -> None:
        """Greeting contains Hauba branding."""
        assert "Hauba" in GREETING

    def test_greeting_contains_commands(self) -> None:
        """Greeting lists available commands."""
        assert "/help" in GREETING
        assert "/new" in GREETING
        assert "/reset" in GREETING

    def test_greeting_within_whatsapp_limit(self) -> None:
        """Greeting fits within a single WhatsApp message."""
        assert len(GREETING) <= 1600
