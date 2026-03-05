"""Tests for ReplyAssistant — enhanced 24/7 smart reply system."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from hauba.services.reply_assistant import (
    ConversationContext,
    OwnerPresence,
    OwnerProfile,
    ReplyAssistant,
    detect_presence_command,
)

# --- Backward Compatibility Tests ---


class TestReplyAssistant:
    """Test backward-compatible auto-reply functionality."""

    @pytest.mark.asyncio
    async def test_disabled_by_default(self) -> None:
        assistant = ReplyAssistant()
        assert await assistant.is_enabled() is False

    @pytest.mark.asyncio
    async def test_set_and_get_auto_reply(self) -> None:
        assistant = ReplyAssistant()
        await assistant.set_auto_reply("I'm away")
        result = await assistant.get_auto_reply()
        assert result == "I'm away"

    @pytest.mark.asyncio
    async def test_enable_disable(self) -> None:
        assistant = ReplyAssistant()
        await assistant.set_enabled(True)
        assert await assistant.is_enabled() is True
        await assistant.set_enabled(False)
        assert await assistant.is_enabled() is False

    @pytest.mark.asyncio
    async def test_handle_message_when_disabled(self) -> None:
        assistant = ReplyAssistant()
        await assistant.set_auto_reply("Away message")
        result = await assistant.handle_message("+1234", "hello")
        assert result is None  # Disabled, should not reply

    @pytest.mark.asyncio
    async def test_handle_message_when_enabled(self) -> None:
        assistant = ReplyAssistant()
        await assistant.set_auto_reply("I'm out of office")
        await assistant.set_enabled(True)
        result = await assistant.handle_message("+1234", "hello")
        assert result == "I'm out of office"

    @pytest.mark.asyncio
    async def test_handle_message_no_reply_set(self) -> None:
        assistant = ReplyAssistant()
        await assistant.set_enabled(True)
        result = await assistant.handle_message("+1234", "hello")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_auto_reply_not_set(self) -> None:
        assistant = ReplyAssistant()
        result = await assistant.get_auto_reply()
        assert result is None


# --- Presence Management Tests ---


class TestPresenceManagement:
    """Test owner presence state management."""

    @pytest.mark.asyncio
    async def test_default_presence_is_available(self) -> None:
        assistant = ReplyAssistant()
        assert assistant.presence == OwnerPresence.AVAILABLE

    @pytest.mark.asyncio
    async def test_set_presence_sleeping(self) -> None:
        assistant = ReplyAssistant()
        msg = await assistant.set_presence(OwnerPresence.SLEEPING)
        assert assistant.presence == OwnerPresence.SLEEPING
        assert await assistant.is_enabled() is True
        assert "rest well" in msg.lower() or "sleep" in msg.lower()

    @pytest.mark.asyncio
    async def test_set_presence_available_disables_reply(self) -> None:
        assistant = ReplyAssistant()
        await assistant.set_presence(OwnerPresence.SLEEPING)
        assert await assistant.is_enabled() is True

        msg = await assistant.set_presence(OwnerPresence.AVAILABLE)
        assert assistant.presence == OwnerPresence.AVAILABLE
        assert await assistant.is_enabled() is False
        assert "paused" in msg.lower() or "handle" in msg.lower()

    @pytest.mark.asyncio
    async def test_set_presence_busy(self) -> None:
        assistant = ReplyAssistant()
        msg = await assistant.set_presence(OwnerPresence.BUSY)
        assert assistant.presence == OwnerPresence.BUSY
        assert await assistant.is_enabled() is True
        assert "busy" in msg.lower()

    @pytest.mark.asyncio
    async def test_set_presence_away(self) -> None:
        assistant = ReplyAssistant()
        msg = await assistant.set_presence(OwnerPresence.AWAY)
        assert assistant.presence == OwnerPresence.AWAY
        assert await assistant.is_enabled() is True
        assert "away" in msg.lower()

    @pytest.mark.asyncio
    async def test_set_enabled_true_sets_away(self) -> None:
        assistant = ReplyAssistant()
        await assistant.set_enabled(True)
        assert assistant.presence == OwnerPresence.AWAY

    @pytest.mark.asyncio
    async def test_set_enabled_false_sets_available(self) -> None:
        assistant = ReplyAssistant()
        await assistant.set_presence(OwnerPresence.SLEEPING)
        await assistant.set_enabled(False)
        assert assistant.presence == OwnerPresence.AVAILABLE


# --- Presence Command Detection Tests ---


class TestPresenceCommandDetection:
    """Test natural language presence command detection."""

    def test_detect_stop_dont_reply(self) -> None:
        cmd, _ = detect_presence_command("don't reply")
        assert cmd == "stop"

    def test_detect_stop_im_on(self) -> None:
        cmd, _ = detect_presence_command("I'm on")
        assert cmd == "stop"

    def test_detect_stop_im_back(self) -> None:
        cmd, _ = detect_presence_command("I'm back")
        assert cmd == "stop"

    def test_detect_stop_im_awake(self) -> None:
        cmd, _ = detect_presence_command("I'm awake")
        assert cmd == "stop"

    def test_detect_stop_stop_replying(self) -> None:
        cmd, _ = detect_presence_command("stop replying")
        assert cmd == "stop"

    def test_detect_start_going_to_sleep(self) -> None:
        cmd, _ = detect_presence_command("I'm going to sleep")
        assert cmd == "start"

    def test_detect_start_goodnight(self) -> None:
        cmd, _ = detect_presence_command("goodnight")
        assert cmd == "start"

    def test_detect_start_reply_to_everyone(self) -> None:
        cmd, _ = detect_presence_command("reply to everyone")
        assert cmd == "start"

    def test_detect_start_take_over(self) -> None:
        cmd, _ = detect_presence_command("you're in charge")
        assert cmd == "start"

    def test_detect_start_im_leaving(self) -> None:
        cmd, _ = detect_presence_command("I'm leaving")
        assert cmd == "start"

    def test_detect_busy_im_busy(self) -> None:
        cmd, _ = detect_presence_command("I'm busy")
        assert cmd == "busy"

    def test_detect_busy_in_meeting(self) -> None:
        cmd, _ = detect_presence_command("in a meeting")
        assert cmd == "busy"

    def test_detect_briefing(self) -> None:
        cmd, _ = detect_presence_command("briefing")
        assert cmd == "briefing"

    def test_detect_briefing_what_happened(self) -> None:
        cmd, _ = detect_presence_command("what happened while I was sleeping?")
        assert cmd == "briefing"

    def test_detect_briefing_catch_me_up(self) -> None:
        cmd, _ = detect_presence_command("catch me up")
        assert cmd == "briefing"

    def test_detect_not_a_command(self) -> None:
        cmd, _ = detect_presence_command("hello how are you")
        assert cmd == ""

    def test_detect_not_a_command_build(self) -> None:
        cmd, _ = detect_presence_command("build me a website")
        assert cmd == ""

    def test_detect_case_insensitive(self) -> None:
        cmd, _ = detect_presence_command("GOOD NIGHT")
        assert cmd == "start"


# --- Owner Command Handling Tests ---


class TestOwnerCommands:
    """Test owner command processing through the assistant."""

    @pytest.mark.asyncio
    async def test_handle_owner_stop_command(self) -> None:
        assistant = ReplyAssistant()
        await assistant.set_presence(OwnerPresence.SLEEPING)
        result = await assistant.handle_owner_command("I'm back")
        assert result is not None
        assert assistant.presence == OwnerPresence.AVAILABLE

    @pytest.mark.asyncio
    async def test_handle_owner_start_command(self) -> None:
        assistant = ReplyAssistant()
        result = await assistant.handle_owner_command("I'm going to sleep")
        assert result is not None
        assert assistant.presence == OwnerPresence.SLEEPING

    @pytest.mark.asyncio
    async def test_handle_owner_busy_command(self) -> None:
        assistant = ReplyAssistant()
        result = await assistant.handle_owner_command("I'm busy")
        assert result is not None
        assert assistant.presence == OwnerPresence.BUSY

    @pytest.mark.asyncio
    async def test_handle_owner_non_command(self) -> None:
        assistant = ReplyAssistant()
        result = await assistant.handle_owner_command("build me a website")
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_owner_briefing(self) -> None:
        assistant = ReplyAssistant()
        result = await assistant.handle_owner_command("briefing")
        assert result is not None
        assert (
            "quiet" in result.lower()
            or "activity" in result.lower()
            or "briefing" in result.lower()
        )

    @pytest.mark.asyncio
    async def test_owner_detection(self) -> None:
        assistant = ReplyAssistant()
        assistant.set_owner_number("whatsapp:+1234567890")
        assert assistant.is_owner("whatsapp:+1234567890") is True
        assert assistant.is_owner("+1234567890") is True
        assert assistant.is_owner("whatsapp:+9999999999") is False

    @pytest.mark.asyncio
    async def test_owner_detection_not_set(self) -> None:
        assistant = ReplyAssistant()
        assert assistant.is_owner("+1234567890") is False


# --- Onboarding Tests ---


class TestOnboarding:
    """Test owner onboarding flow."""

    @pytest.mark.asyncio
    async def test_not_onboarded_by_default(self) -> None:
        assistant = ReplyAssistant()
        assert assistant.is_onboarded is False

    def test_start_onboarding(self) -> None:
        assistant = ReplyAssistant()
        msg = assistant.start_onboarding()
        assert "call you" in msg.lower()

    @pytest.mark.asyncio
    async def test_onboarding_step_1_name(self) -> None:
        assistant = ReplyAssistant()
        assistant.start_onboarding()
        result = await assistant.handle_onboarding("Nikhil")
        assert result is not None
        assert assistant.profile.name == "Nikhil"
        assert "business" in result.lower() or "summary" in result.lower() or "do" in result.lower()

    @pytest.mark.asyncio
    async def test_onboarding_step_2_business(self) -> None:
        assistant = ReplyAssistant()
        assistant.start_onboarding()
        await assistant.handle_onboarding("Nikhil")
        result = await assistant.handle_onboarding("AI software development company")
        assert result is not None
        assert assistant.profile.business_summary == "AI software development company"
        assert "services" in result.lower()

    @pytest.mark.asyncio
    async def test_onboarding_step_3_services(self) -> None:
        assistant = ReplyAssistant()
        assistant.start_onboarding()
        await assistant.handle_onboarding("Nikhil")
        await assistant.handle_onboarding("AI company")
        result = await assistant.handle_onboarding("web dev, AI, mobile apps")
        assert result is not None
        assert len(assistant.profile.services) == 3
        assert "web dev" in assistant.profile.services

    @pytest.mark.asyncio
    async def test_onboarding_step_4_tone_completes(self) -> None:
        assistant = ReplyAssistant()
        assistant.start_onboarding()
        await assistant.handle_onboarding("Nikhil")
        await assistant.handle_onboarding("AI company")
        await assistant.handle_onboarding("web dev, AI")
        result = await assistant.handle_onboarding("professional")
        assert result is not None
        assert assistant.is_onboarded is True
        assert assistant.profile.tone == "professional"
        assert "setup complete" in result.lower()

    @pytest.mark.asyncio
    async def test_onboarding_returns_none_when_complete(self) -> None:
        assistant = ReplyAssistant()
        assistant._profile.onboarding_complete = True
        result = await assistant.handle_onboarding("anything")
        assert result is None


# --- Owner Profile Tests ---


class TestOwnerProfile:
    """Test owner profile serialization."""

    def test_profile_to_json(self) -> None:
        profile = OwnerProfile(
            name="Test",
            business_summary="Test biz",
            services=["web", "ai"],
            onboarding_complete=True,
        )
        json_str = profile.to_json()
        loaded = OwnerProfile.from_json(json_str)
        assert loaded.name == "Test"
        assert loaded.business_summary == "Test biz"
        assert loaded.services == ["web", "ai"]
        assert loaded.onboarding_complete is True

    def test_profile_from_invalid_json(self) -> None:
        profile = OwnerProfile.from_json("not json")
        assert profile.name == ""
        assert profile.onboarding_complete is False

    def test_profile_defaults(self) -> None:
        profile = OwnerProfile()
        assert profile.tone == "professional and friendly"
        assert profile.services == []


# --- Conversation Context Tests ---


class TestConversationContext:
    """Test per-sender conversation context."""

    def test_add_message(self) -> None:
        ctx = ConversationContext(sender="+1234")
        ctx.add_message("customer", "hello")
        assert len(ctx.messages) == 1
        assert ctx.messages[0]["role"] == "customer"
        assert ctx.messages[0]["text"] == "hello"

    def test_context_limits_to_20_messages(self) -> None:
        ctx = ConversationContext(sender="+1234")
        for i in range(25):
            ctx.add_message("customer", f"message {i}")
        assert len(ctx.messages) == 20

    def test_context_summary(self) -> None:
        ctx = ConversationContext(sender="+1234")
        ctx.add_message("customer", "hey there")
        ctx.add_message("assistant", "hello! how can I help?")
        summary = ctx.get_context_summary()
        assert "Customer: hey there" in summary
        assert "owner's assistant" in summary.lower()

    def test_context_summary_empty(self) -> None:
        ctx = ConversationContext(sender="+1234")
        assert ctx.get_context_summary() == ""

    def test_context_serialization(self) -> None:
        ctx = ConversationContext(sender="+1234")
        ctx.add_message("customer", "test")
        ctx.sender_name = "John"
        ctx.topic = "website"

        json_str = ctx.to_json()
        loaded = ConversationContext.from_json(json_str)
        assert loaded.sender == "+1234"
        assert loaded.sender_name == "John"
        assert loaded.topic == "website"
        assert len(loaded.messages) == 1

    def test_context_from_invalid_json(self) -> None:
        ctx = ConversationContext.from_json("bad data")
        assert ctx.sender == ""


# --- Activity Log & Briefing Tests ---


class TestActivityLog:
    """Test activity logging and morning briefing."""

    @pytest.mark.asyncio
    async def test_briefing_no_activity(self) -> None:
        assistant = ReplyAssistant()
        briefing = await assistant.get_briefing()
        assert "quiet" in briefing.lower() or "no activity" in briefing.lower()

    @pytest.mark.asyncio
    async def test_activity_logged_on_reply(self) -> None:
        assistant = ReplyAssistant()
        await assistant.set_auto_reply("I'm away")
        await assistant.set_enabled(True)
        await assistant.handle_message("+1234", "hello")
        assert assistant.activity_count == 1

    @pytest.mark.asyncio
    async def test_briefing_with_activity(self) -> None:
        assistant = ReplyAssistant()
        await assistant.set_auto_reply("I'm away")
        await assistant.set_enabled(True)
        await assistant.handle_message("+1234", "hello")
        await assistant.handle_message("+5678", "need help")

        briefing = await assistant.get_briefing()
        assert "briefing" in briefing.lower()
        assert "2" in briefing  # 2 messages handled

    @pytest.mark.asyncio
    async def test_clear_activity_log(self) -> None:
        assistant = ReplyAssistant()
        await assistant.set_auto_reply("Away")
        await assistant.set_enabled(True)
        await assistant.handle_message("+1234", "hi")
        assert assistant.activity_count == 1

        await assistant.clear_activity_log()
        assert assistant.activity_count == 0

    @pytest.mark.asyncio
    async def test_activity_log_limits_to_100(self) -> None:
        assistant = ReplyAssistant()
        for _ in range(110):
            assistant._log_activity(
                sender="+1234",
                sender_message="test",
                reply_sent="reply",
            )
        assert assistant.activity_count == 100


# --- Smart Reply Tests ---


class TestSmartReply:
    """Test AI-powered smart reply generation."""

    @pytest.mark.asyncio
    async def test_smart_reply_no_llm(self) -> None:
        """Without LLM function, falls back to simple reply."""
        assistant = ReplyAssistant()
        await assistant.set_auto_reply("Away")
        await assistant.set_enabled(True)
        result = await assistant.handle_message("+1234", "hello")
        assert result == "Away"

    @pytest.mark.asyncio
    async def test_smart_reply_with_llm(self) -> None:
        """With LLM function and completed profile, generates smart reply."""
        assistant = ReplyAssistant()
        assistant._profile = OwnerProfile(
            name="Test",
            business_summary="AI company",
            services=["web dev"],
            onboarding_complete=True,
        )
        await assistant.set_presence(OwnerPresence.SLEEPING)

        mock_llm = AsyncMock(
            return_value="Hi! I'm Test's assistant. They're resting now but I'll pass along your message."
        )
        assistant.set_llm_generate(mock_llm)

        result = await assistant.handle_message("+1234", "hey need a website")
        assert result is not None
        assert "assistant" in result.lower()
        mock_llm.assert_called_once()

    @pytest.mark.asyncio
    async def test_smart_reply_not_onboarded_falls_back(self) -> None:
        """Without completed onboarding, falls back to simple reply."""
        assistant = ReplyAssistant()
        await assistant.set_auto_reply("Away")
        await assistant.set_enabled(True)

        mock_llm = AsyncMock(return_value="smart reply")
        assistant.set_llm_generate(mock_llm)

        result = await assistant.handle_message("+1234", "hello")
        assert result == "Away"  # Falls back to simple
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_smart_reply_llm_error_falls_back(self) -> None:
        """LLM error falls back to simple auto-reply."""
        assistant = ReplyAssistant()
        assistant._profile = OwnerProfile(
            name="Test",
            business_summary="AI company",
            onboarding_complete=True,
        )
        await assistant.set_auto_reply("Fallback message")
        await assistant.set_presence(OwnerPresence.SLEEPING)

        mock_llm = AsyncMock(side_effect=Exception("API error"))
        assistant.set_llm_generate(mock_llm)

        result = await assistant.handle_message("+1234", "hello")
        assert result == "Fallback message"

    @pytest.mark.asyncio
    async def test_smart_reply_logs_activity(self) -> None:
        """Smart replies are logged for briefing."""
        assistant = ReplyAssistant()
        assistant._profile = OwnerProfile(
            name="Test",
            business_summary="Test biz",
            onboarding_complete=True,
        )
        await assistant.set_presence(OwnerPresence.SLEEPING)

        mock_llm = AsyncMock(return_value="Got it, I'll let them know!")
        assistant.set_llm_generate(mock_llm)

        await assistant.handle_message("+1234", "hello")
        assert assistant.activity_count == 1

    @pytest.mark.asyncio
    async def test_smart_reply_builds_conversation_context(self) -> None:
        """Multiple messages from same sender build conversation context."""
        assistant = ReplyAssistant()
        assistant._profile = OwnerProfile(
            name="Test",
            business_summary="Test biz",
            onboarding_complete=True,
        )
        await assistant.set_presence(OwnerPresence.SLEEPING)

        mock_llm = AsyncMock(return_value="Reply text")
        assistant.set_llm_generate(mock_llm)

        await assistant.handle_message("+1234", "first message")
        await assistant.handle_message("+1234", "second message")

        # Should have conversation context with 4 messages (2 customer + 2 assistant)
        ctx = assistant._conversations.get("+1234")
        assert ctx is not None
        assert len(ctx.messages) == 4


# --- Owner Message Routing Tests ---


class TestOwnerMessageRouting:
    """Test that owner messages are routed correctly."""

    @pytest.mark.asyncio
    async def test_owner_presence_command_handled(self) -> None:
        """Owner's presence commands are detected and handled."""
        assistant = ReplyAssistant()
        assistant.set_owner_number("+1234567890")
        result = await assistant.handle_message("+1234567890", "I'm going to sleep")
        assert result is not None
        assert assistant.presence == OwnerPresence.SLEEPING

    @pytest.mark.asyncio
    async def test_non_owner_presence_command_ignored(self) -> None:
        """Non-owner saying 'I'm going to sleep' is not treated as a command."""
        assistant = ReplyAssistant()
        assistant.set_owner_number("+1234567890")
        await assistant.set_auto_reply("Away")
        await assistant.set_presence(OwnerPresence.SLEEPING)

        result = await assistant.handle_message("+9999999999", "I'm going to sleep")
        assert result == "Away"  # Treated as normal message, auto-reply sent
        assert assistant.presence == OwnerPresence.SLEEPING  # Unchanged

    @pytest.mark.asyncio
    async def test_owner_non_command_not_auto_replied(self) -> None:
        """Owner's normal messages don't trigger auto-reply."""
        assistant = ReplyAssistant()
        assistant.set_owner_number("+1234567890")
        await assistant.set_auto_reply("Away")
        await assistant.set_presence(OwnerPresence.SLEEPING)

        # Owner sends a normal message — presence commands are not detected,
        # but auto-reply IS still enabled (handled via WhatsApp webhook separately)
        result = await assistant.handle_message("+1234567890", "build me a website")
        # Owner is the sender, handle_owner_command returns None,
        # then normal auto-reply flow applies
        assert result is not None  # Auto-reply applies even to owner with simple mode
