"""Reply assistant — 24/7 smart auto-reply on owner's behalf.

Enhanced autonomous reply assistant that:
1. Onboards the owner (name, business, tone preferences)
2. Tracks owner presence (awake/sleeping/busy/away)
3. Auto-replies to messages with context-aware AI responses
4. Detects build tasks and queues them for execution
5. Logs all overnight activity for morning briefing
6. Owner controls everything via natural language commands

Owner presence commands (via WhatsApp):
- "don't reply" / "i'm on" / "stop replying" -> pauses auto-reply
- "i'm going to sleep" / "goodnight" / "reply to everyone" -> enables auto-reply
- "i'm back" / "i'm awake" -> pauses auto-reply
- "reply to [name]" -> reply to specific person
- "briefing" / "what happened" -> morning briefing
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, ClassVar

import structlog

logger = structlog.get_logger()

# Memory namespace constants
REPLY_NAMESPACE = "autoreply"
REPLY_MESSAGE_KEY = "message"
REPLY_ENABLED_KEY = "enabled"
PROFILE_NAMESPACE = "owner_profile"
ACTIVITY_NAMESPACE = "reply_activity"
CONVERSATION_NAMESPACE = "reply_conversations"


class OwnerPresence(str, Enum):
    """Owner's current availability state."""

    AVAILABLE = "available"  # Owner is online, no auto-reply
    SLEEPING = "sleeping"  # Owner is asleep, full auto-reply
    BUSY = "busy"  # Owner is busy, auto-reply with "busy" context
    AWAY = "away"  # Owner is away, auto-reply with "away" context


@dataclass
class OwnerProfile:
    """Owner's profile for personalized replies."""

    name: str = ""
    business_summary: str = ""
    tone: str = "professional and friendly"
    services: list[str] = field(default_factory=list)
    greeting_name: str = ""  # What customers call the owner
    auto_reply_style: str = "helpful"  # helpful, brief, detailed
    onboarding_complete: bool = False

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> OwnerProfile:
        try:
            d = json.loads(data)
            return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        except (json.JSONDecodeError, TypeError):
            return cls()


@dataclass
class ActivityEntry:
    """A single activity log entry."""

    timestamp: float
    sender: str
    sender_message: str
    reply_sent: str
    action_type: str = "reply"  # reply, task_queued, task_delivered
    task_id: str = ""
    task_result: str = ""


@dataclass
class ConversationContext:
    """Per-sender conversation context for smart replies."""

    sender: str
    messages: list[dict[str, str]] = field(default_factory=list)
    last_active: float = 0.0
    sender_name: str = ""
    topic: str = ""

    def add_message(self, role: str, text: str) -> None:
        self.messages.append({"role": role, "text": text, "time": str(time.time())})
        # Keep last 20 messages for context
        if len(self.messages) > 20:
            self.messages = self.messages[-20:]
        self.last_active = time.time()

    def get_context_summary(self) -> str:
        if not self.messages:
            return ""
        lines = []
        for msg in self.messages[-10:]:
            role = "Customer" if msg["role"] == "customer" else "You (owner's assistant)"
            lines.append(f"{role}: {msg['text'][:200]}")
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(
            {
                "sender": self.sender,
                "messages": self.messages,
                "last_active": self.last_active,
                "sender_name": self.sender_name,
                "topic": self.topic,
            }
        )

    @classmethod
    def from_json(cls, data: str) -> ConversationContext:
        try:
            d = json.loads(data)
            ctx = cls(sender=d.get("sender", ""))
            ctx.messages = d.get("messages", [])
            ctx.last_active = d.get("last_active", 0.0)
            ctx.sender_name = d.get("sender_name", "")
            ctx.topic = d.get("topic", "")
            return ctx
        except (json.JSONDecodeError, TypeError):
            return cls(sender="")


# Presence detection patterns
_STOP_PATTERNS = [
    r"\b(don'?t reply|stop repl(y|ying)|i'?m on|i'?m here|i'?m back|i'?m awake)\b",
    r"\b(stop auto.?reply|pause|i'?ll handle|i got it|i got this)\b",
    r"\b(no more replies|take a break|stand down)\b",
]

_START_PATTERNS = [
    r"\b(i'?m going to sleep|good\s?night|going to bed|i'?m sleeping)\b",
    r"\b(reply to (everyone|anyone|all)|start reply|enable reply)\b",
    r"\b(i'?m (leaving|away|out|gone|offline))\b",
    r"\b(handle (everything|messages|it)|take over|you'?re in charge)\b",
    r"\b(auto.?reply on|activate)\b",
]

_BUSY_PATTERNS = [
    r"\b(i'?m busy|in a meeting|do not disturb|dnd)\b",
    r"\b(busy right now|can'?t talk)\b",
]

_BRIEFING_PATTERNS = [
    r"\b(briefing|what happened|morning report|overnight|summary)\b",
    r"\b(what did (you|i) miss|catch me up|updates?)\b",
]


def detect_presence_command(text: str) -> tuple[str, str]:
    """Detect owner presence commands from natural language.

    Returns:
        (command_type, extra_info) where command_type is one of:
        "stop", "start", "busy", "briefing", "" (not a command)
    """
    lower = text.strip().lower()

    # Check briefing first (most specific)
    for pattern in _BRIEFING_PATTERNS:
        if re.search(pattern, lower):
            return ("briefing", "")

    # Check stop patterns
    for pattern in _STOP_PATTERNS:
        if re.search(pattern, lower):
            return ("stop", "")

    # Check busy patterns
    for pattern in _BUSY_PATTERNS:
        if re.search(pattern, lower):
            return ("busy", "")

    # Check start patterns
    for pattern in _START_PATTERNS:
        if re.search(pattern, lower):
            return ("start", "")

    return ("", "")


class ReplyAssistant:
    """24/7 smart auto-reply assistant.

    Manages owner presence, generates context-aware replies,
    detects build tasks, and provides morning briefings.

    Usage:
        assistant = ReplyAssistant(memory_store)
        await assistant.load_profile()

        # Owner says "I'm going to sleep"
        await assistant.set_presence(OwnerPresence.SLEEPING)

        # Customer messages come in
        reply = await assistant.handle_message("+1234", "hey, need a website")
        # -> AI-generated contextual reply on owner's behalf

        # Morning: owner asks for briefing
        briefing = await assistant.get_briefing()
        # -> "While you were sleeping: 3 messages, 1 task delivered..."
    """

    def __init__(self, memory_store: Any | None = None) -> None:
        self._store = memory_store
        # In-memory state
        self._message: str = ""
        self._enabled: bool = False
        self._presence: OwnerPresence = OwnerPresence.AVAILABLE
        self._profile: OwnerProfile = OwnerProfile()
        self._conversations: dict[str, ConversationContext] = {}
        self._activity_log: list[ActivityEntry] = []
        self._task_queue: Any = None  # TaskQueue for build task detection
        self._llm_generate: Any = None  # Async function for LLM reply generation
        self._onboarding_step: int = 0  # Current onboarding question index
        self._owner_number: str = ""  # Owner's WhatsApp number

    def set_task_queue(self, queue: Any) -> None:
        """Set task queue for build task detection and execution."""
        self._task_queue = queue

    def set_llm_generate(self, fn: Any) -> None:
        """Set the LLM generation function for smart replies.

        fn should be: async def generate(prompt: str) -> str
        """
        self._llm_generate = fn

    def set_owner_number(self, number: str) -> None:
        """Set the owner's WhatsApp number for identifying owner commands."""
        self._owner_number = number

    # --- Presence Management ---

    @property
    def presence(self) -> OwnerPresence:
        return self._presence

    async def set_presence(self, presence: OwnerPresence) -> str:
        """Set owner presence and return confirmation message.

        Returns a human-friendly confirmation string.
        """
        old = self._presence
        self._presence = presence

        if self._store:
            await self._store.set(REPLY_NAMESPACE, "presence", presence.value)  # type: ignore[union-attr]

        # Enable/disable auto-reply based on presence
        if presence == OwnerPresence.AVAILABLE:
            self._enabled = False
        else:
            self._enabled = True

        if self._store:
            await self._store.set(  # type: ignore[union-attr]
                REPLY_NAMESPACE, REPLY_ENABLED_KEY, str(self._enabled).lower()
            )

        logger.info(
            "autoreply.presence_changed",
            old=old.value,
            new=presence.value,
            enabled=self._enabled,
        )

        confirmations = {
            OwnerPresence.AVAILABLE: "Auto-reply paused. I'll let you handle messages.",
            OwnerPresence.SLEEPING: "Got it, rest well! I'll handle all messages and tasks while you sleep.",
            OwnerPresence.BUSY: "Noted. I'll let people know you're busy and handle what I can.",
            OwnerPresence.AWAY: "I'll take care of messages while you're away.",
        }
        return confirmations.get(presence, f"Presence set to {presence.value}.")

    async def load_presence(self) -> None:
        """Load presence from persistent store."""
        if not self._store:
            return
        val = await self._store.get(REPLY_NAMESPACE, "presence")  # type: ignore[union-attr]
        if val:
            try:
                self._presence = OwnerPresence(val)
                self._enabled = self._presence != OwnerPresence.AVAILABLE
            except ValueError:
                pass

    # --- Owner Profile / Onboarding ---

    ONBOARDING_QUESTIONS: ClassVar[list[str]] = [
        "What should I call you? (your name or nickname)",
        "What do you do? Give me a short summary of your business or work.",
        "What services do you offer? (comma-separated, e.g., web development, design, consulting)",
        "How should I reply to your customers? (professional, casual, friendly, brief)",
    ]

    @property
    def profile(self) -> OwnerProfile:
        return self._profile

    @property
    def is_onboarded(self) -> bool:
        return self._profile.onboarding_complete

    async def load_profile(self) -> None:
        """Load owner profile from persistent store."""
        if not self._store:
            return
        data = await self._store.get(PROFILE_NAMESPACE, "profile")  # type: ignore[union-attr]
        if data:
            self._profile = OwnerProfile.from_json(data)

    async def save_profile(self) -> None:
        """Save owner profile to persistent store."""
        if self._store:
            await self._store.set(  # type: ignore[union-attr]
                PROFILE_NAMESPACE, "profile", self._profile.to_json()
            )

    async def handle_onboarding(self, text: str) -> str | None:
        """Process onboarding answers. Returns next question or None if done.

        Returns None if onboarding is already complete.
        """
        if self._profile.onboarding_complete:
            return None

        step = self._onboarding_step

        if step == 0:
            # They answered: name
            self._profile.name = text.strip()
            self._profile.greeting_name = text.strip()
            self._onboarding_step = 1
            await self.save_profile()
            return self.ONBOARDING_QUESTIONS[1]

        elif step == 1:
            # They answered: business summary
            self._profile.business_summary = text.strip()
            self._onboarding_step = 2
            await self.save_profile()
            return self.ONBOARDING_QUESTIONS[2]

        elif step == 2:
            # They answered: services
            services = [s.strip() for s in text.split(",") if s.strip()]
            self._profile.services = services
            self._onboarding_step = 3
            await self.save_profile()
            return self.ONBOARDING_QUESTIONS[3]

        elif step == 3:
            # They answered: reply tone
            self._profile.tone = text.strip().lower()
            self._profile.auto_reply_style = text.strip().lower()
            self._profile.onboarding_complete = True
            self._onboarding_step = 4
            await self.save_profile()
            return (
                f"Setup complete!\n\n"
                f"Name: {self._profile.name}\n"
                f"Business: {self._profile.business_summary[:100]}\n"
                f"Services: {', '.join(self._profile.services)}\n"
                f"Reply style: {self._profile.tone}\n\n"
                f"I'm ready to handle your messages. Commands:\n"
                f"  \"I'm going to sleep\" - I'll reply to everyone\n"
                f'  "Don\'t reply" / "I\'m on" - I\'ll stop\n'
                f'  "Briefing" - What happened while you were away'
            )

        return None

    def start_onboarding(self) -> str:
        """Start the onboarding flow. Returns the first question."""
        self._onboarding_step = 0
        return "Let's set up your 24/7 reply assistant!\n\n" + self.ONBOARDING_QUESTIONS[0]

    # --- Backward-compatible simple auto-reply ---

    async def set_auto_reply(self, message: str) -> None:
        """Set the auto-reply message (backward compatible)."""
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
        if enabled:
            self._presence = OwnerPresence.AWAY
        else:
            self._presence = OwnerPresence.AVAILABLE
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

    # --- Smart Message Handling ---

    def is_owner(self, sender: str) -> bool:
        """Check if the sender is the owner."""
        if not self._owner_number:
            return False
        # Normalize for comparison
        s = sender.replace("whatsapp:", "").strip()
        o = self._owner_number.replace("whatsapp:", "").strip()
        return s == o

    async def handle_owner_command(self, text: str) -> str | None:
        """Process owner's natural language commands.

        Returns a response string if it was a command, None otherwise.
        """
        cmd_type, _ = detect_presence_command(text)

        if cmd_type == "stop":
            return await self.set_presence(OwnerPresence.AVAILABLE)

        if cmd_type == "start":
            return await self.set_presence(OwnerPresence.SLEEPING)

        if cmd_type == "busy":
            return await self.set_presence(OwnerPresence.BUSY)

        if cmd_type == "briefing":
            return await self.get_briefing()

        # Not a presence command
        return None

    async def handle_message(self, sender: str, text: str) -> str | None:
        """Handle an incoming message. Returns auto-reply if enabled, else None.

        Smart routing:
        - If sender is owner -> check for presence commands
        - If auto-reply disabled -> return None
        - If auto-reply enabled -> generate context-aware reply

        Args:
            sender: The sender identifier (phone number, user ID, etc.).
            text: The incoming message text.

        Returns:
            The auto-reply message if enabled and configured, else None.
        """
        # Owner commands take priority
        if self.is_owner(sender):
            cmd_reply = await self.handle_owner_command(text)
            if cmd_reply:
                return cmd_reply

        # Check if auto-reply is active
        if not await self.is_enabled():
            return None

        # Try smart AI reply first
        smart_reply = await self._generate_smart_reply(sender, text)
        if smart_reply:
            # Log the activity
            self._log_activity(
                sender=sender,
                sender_message=text,
                reply_sent=smart_reply,
                action_type="reply",
            )
            return smart_reply

        # Fallback to simple auto-reply message
        reply = await self.get_auto_reply()
        if not reply:
            return None

        logger.info("autoreply.triggered", sender=sender, text_preview=text[:50])
        self._log_activity(
            sender=sender,
            sender_message=text,
            reply_sent=reply,
            action_type="reply",
        )
        return reply

    async def _generate_smart_reply(self, sender: str, text: str) -> str | None:
        """Generate a context-aware reply using the owner's profile and conversation history."""
        if not self._llm_generate:
            return None

        if not self._profile.onboarding_complete:
            return None

        # Get or create conversation context
        ctx = self._get_conversation(sender)
        ctx.add_message("customer", text)

        # Build the prompt
        prompt = self._build_reply_prompt(ctx, text)

        try:
            reply = await self._llm_generate(prompt)
            if reply:
                reply = reply.strip()
                ctx.add_message("assistant", reply)
                # Persist conversation
                await self._save_conversation(sender, ctx)
                return reply
        except Exception as exc:
            logger.error("autoreply.llm_error", error=str(exc))

        return None

    def _build_reply_prompt(self, ctx: ConversationContext, latest_message: str) -> str:
        """Build a prompt for generating a smart reply."""
        profile = self._profile
        presence_context = {
            OwnerPresence.SLEEPING: "The owner is currently sleeping. Handle messages warmly and professionally.",
            OwnerPresence.BUSY: "The owner is currently busy. Keep replies brief and let them know the owner will get back to them.",
            OwnerPresence.AWAY: "The owner is currently away. Handle messages professionally.",
            OwnerPresence.AVAILABLE: "The owner is available but auto-reply is on.",
        }

        conversation_history = ctx.get_context_summary()

        prompt = f"""You are {profile.name}'s personal AI assistant, replying to messages on their behalf.

OWNER PROFILE:
- Name: {profile.name}
- Business: {profile.business_summary}
- Services: {", ".join(profile.services) if profile.services else "various"}
- Reply tone: {profile.tone}

STATUS: {presence_context.get(self._presence, "Available")}

{"CONVERSATION HISTORY:" + chr(10) + conversation_history + chr(10) if conversation_history else ""}
LATEST MESSAGE FROM CUSTOMER:
{latest_message}

INSTRUCTIONS:
- Reply as if you are {profile.name}'s assistant, on their behalf
- Be {profile.tone}
- If they ask about services, reference: {", ".join(profile.services) if profile.services else profile.business_summary}
- If they want something built/created, say you'll pass it to {profile.name} and they'll get it done
- Keep replies concise (2-4 sentences for simple messages)
- Don't reveal you are an AI unless directly asked
- If the owner is sleeping, mention they'll follow up when available
- Use WhatsApp-friendly formatting (no markdown headers, use * for bold)

Reply:"""

        return prompt

    # --- Conversation Context ---

    def _get_conversation(self, sender: str) -> ConversationContext:
        """Get or create conversation context for a sender."""
        if sender not in self._conversations:
            self._conversations[sender] = ConversationContext(sender=sender)
        return self._conversations[sender]

    async def _save_conversation(self, sender: str, ctx: ConversationContext) -> None:
        """Persist conversation context."""
        if self._store:
            key = f"conv_{sender.replace(':', '_').replace('+', '')}"
            await self._store.set(  # type: ignore[union-attr]
                CONVERSATION_NAMESPACE, key, ctx.to_json()
            )

    async def load_conversation(self, sender: str) -> ConversationContext:
        """Load conversation context from store."""
        if self._store:
            key = f"conv_{sender.replace(':', '_').replace('+', '')}"
            data = await self._store.get(CONVERSATION_NAMESPACE, key)  # type: ignore[union-attr]
            if data:
                ctx = ConversationContext.from_json(data)
                self._conversations[sender] = ctx
                return ctx
        return self._get_conversation(sender)

    # --- Activity Log & Briefing ---

    def _log_activity(
        self,
        sender: str,
        sender_message: str,
        reply_sent: str,
        action_type: str = "reply",
        task_id: str = "",
        task_result: str = "",
    ) -> None:
        """Log an activity entry for the morning briefing."""
        entry = ActivityEntry(
            timestamp=time.time(),
            sender=sender,
            sender_message=sender_message,
            reply_sent=reply_sent,
            action_type=action_type,
            task_id=task_id,
            task_result=task_result,
        )
        self._activity_log.append(entry)
        # Keep last 100 entries
        if len(self._activity_log) > 100:
            self._activity_log = self._activity_log[-100:]

        logger.info(
            "autoreply.activity",
            action=action_type,
            sender=sender[:20],
        )

    async def get_briefing(self) -> str:
        """Generate a morning briefing of overnight activity.

        Returns a human-friendly summary of what happened while the owner was away.
        """
        if not self._activity_log:
            return "No activity while you were away. All quiet!"

        # Group by type
        replies = [e for e in self._activity_log if e.action_type == "reply"]
        tasks_queued = [e for e in self._activity_log if e.action_type == "task_queued"]
        tasks_delivered = [e for e in self._activity_log if e.action_type == "task_delivered"]

        # Unique senders
        unique_senders = set(e.sender for e in self._activity_log)

        lines = ["*Morning Briefing*\n"]

        lines.append(f"Messages handled: {len(replies)}")
        lines.append(f"People who reached out: {len(unique_senders)}")

        if tasks_queued:
            lines.append(f"Tasks queued: {len(tasks_queued)}")
        if tasks_delivered:
            lines.append(f"Tasks delivered: {len(tasks_delivered)}")

        lines.append("")

        # Show conversation summaries
        if replies:
            lines.append("*Conversations:*")
            seen_senders: set[str] = set()
            for entry in replies:
                if entry.sender in seen_senders:
                    continue
                seen_senders.add(entry.sender)
                sender_msgs = [e for e in replies if e.sender == entry.sender]
                sender_display = entry.sender.replace("whatsapp:", "")
                lines.append(
                    f"  {sender_display}: {len(sender_msgs)} message(s)"
                    f' - "{sender_msgs[0].sender_message[:60]}"'
                )

        if tasks_delivered:
            lines.append("\n*Delivered:*")
            for entry in tasks_delivered:
                lines.append(
                    f"  Delivered to {entry.sender.replace('whatsapp:', '')}: "
                    f"{entry.task_result[:80]}"
                )

        lines.append("\n_I'm ready for the day!_")

        return "\n".join(lines)

    async def clear_activity_log(self) -> None:
        """Clear the activity log (typically after morning briefing)."""
        count = len(self._activity_log)
        self._activity_log.clear()
        logger.info("autoreply.log_cleared", entries=count)

    @property
    def activity_count(self) -> int:
        """Number of entries in the activity log."""
        return len(self._activity_log)
