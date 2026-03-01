"""WhatsApp Webhook Bot — AI agent interaction via Twilio WhatsApp.

When a user sends a message on WhatsApp, Twilio POSTs to our webhook.
We ACK immediately (200), then process the message in the background
using CopilotEngine and reply via the Twilio REST API.

Design decisions:
- Immediate 200 ACK: Twilio times out at 15s, AI takes 10-60s
- Per-user sessions: each phone number gets its own CopilotEngine session
- Background processing: asyncio.create_task for non-blocking
- Message splitting: WhatsApp has 1600-char limit
- Dedup: Twilio retries on timeout, we track MessageSid
- Session cleanup: idle sessions >30 min are destroyed
- BYOK exception: WhatsApp users can't send API keys via chat,
  so server owner provides HAUBA_LLM_API_KEY env var
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()

# Greeting message when a user first messages Hauba
GREETING = (
    "*Hauba AI Engineering Co.*\n"
    "_Your AI engineering team. Ready to build._\n\n"
    "We're not a chatbot. We're the engineering team you haven't hired yet.\n\n"
    "Tell us what to ship:\n"
    "  - SaaS apps, APIs & full-stack products\n"
    "  - Data pipelines, dashboards & analytics\n"
    "  - ML models, training & deployment\n"
    "  - Video editing & media processing\n"
    "  - DevOps, CI/CD & infrastructure\n"
    "  - Docs, scripts & workflow automation\n\n"
    "Just describe what you need. We plan, build, test, and deliver.\n\n"
    "Commands:\n"
    "  /help  - Show this menu\n"
    "  /new   - Start a fresh project\n"
    "  /reset - Clear session history\n\n"
    "_One message. Production code. hauba.tech_"
)

# Max WhatsApp message length
MAX_MSG_LEN = 1600

# Idle session timeout (30 minutes)
SESSION_TIMEOUT = 1800.0

# Task execution timeout — configurable via HAUBA_TASK_TIMEOUT env var
# Default: 300s (5 min). Building real apps takes time.
TASK_TIMEOUT = float(os.environ.get("HAUBA_TASK_TIMEOUT", "300"))

# Progress update interval — how often to send "still working" messages
PROGRESS_INTERVAL = 30.0


@dataclass
class UserSession:
    """Per-user engine session state."""

    engine: Any = None
    last_active: float = 0.0
    message_count: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    is_first: bool = True


class WhatsAppBot:
    """Self-contained WhatsApp bot that processes messages via CopilotEngine.

    Usage in server.py:
        bot = WhatsAppBot()
        if bot.configure():
            # Wire up /whatsapp/webhook endpoint
    """

    def __init__(self) -> None:
        self._account_sid: str = ""
        self._auth_token: str = ""
        self._api_key: str = ""
        self._provider: str = ""
        self._model: str = ""
        self._sessions: dict[str, UserSession] = {}
        self._seen_sids: set[str] = set()
        self._max_seen: int = 10000
        self._twilio_client: Any = None
        self._from_number: str = "whatsapp:+14155238886"
        self._cleanup_task: asyncio.Task[None] | None = None
        self._task_queue: Any = None  # TaskQueue instance (set by server.py)

    def set_task_queue(self, queue: Any) -> None:
        """Set the task queue for Queue + Poll architecture.

        When set, build tasks are queued for the user's local agent
        instead of being executed on the server.
        """
        self._task_queue = queue

    def configure(self) -> bool:
        """Load configuration from environment variables.

        Required:
            TWILIO_ACCOUNT_SID — Twilio Account SID
            TWILIO_AUTH_TOKEN  — Twilio Auth Token
            HAUBA_LLM_API_KEY  — LLM API key (server owner provides)

        Optional:
            HAUBA_LLM_PROVIDER — "anthropic" (default), "openai", "ollama"
            HAUBA_LLM_MODEL    — Model name (default: claude-sonnet-4-5-20250514)
            TWILIO_WHATSAPP_NUMBER — From number (default: sandbox number)

        Returns True if all required vars are present.
        """
        self._account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self._auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self._api_key = os.environ.get("HAUBA_LLM_API_KEY", "")
        self._provider = os.environ.get("HAUBA_LLM_PROVIDER", "anthropic")
        self._model = os.environ.get("HAUBA_LLM_MODEL", "claude-sonnet-4-5-20250514")
        from_num = os.environ.get("TWILIO_WHATSAPP_NUMBER", "")
        if from_num:
            self._from_number = from_num

        if not self._account_sid or not self._auth_token or not self._api_key:
            logger.info(
                "whatsapp_bot.not_configured",
                has_sid=bool(self._account_sid),
                has_token=bool(self._auth_token),
                has_key=bool(self._api_key),
            )
            return False

        try:
            from twilio.rest import Client as TwilioClient  # type: ignore[import-untyped]

            self._twilio_client = TwilioClient(self._account_sid, self._auth_token)
        except ImportError:
            logger.warning("whatsapp_bot.twilio_not_installed")
            return False

        logger.info("whatsapp_bot.configured", provider=self._provider)
        return True

    def validate_signature(self, url: str, params: dict[str, str], signature: str) -> bool:
        """Validate Twilio request signature to prevent spoofing.

        Args:
            url: The full webhook URL.
            params: The POST form parameters.
            signature: The X-Twilio-Signature header value.

        Returns:
            True if the signature is valid.
        """
        try:
            from twilio.request_validator import RequestValidator  # type: ignore[import-untyped]

            validator = RequestValidator(self._auth_token)
            return validator.validate(url, params, signature)
        except ImportError:
            # If twilio isn't installed, skip validation
            return True
        except Exception:
            return False

    async def handle_message(
        self,
        body: str,
        from_number: str,
        message_sid: str = "",
    ) -> None:
        """Process an incoming WhatsApp message in the background.

        This method is called from the webhook endpoint after ACK.
        It runs in a background task so the webhook returns immediately.

        Args:
            body: The message text from the user.
            from_number: The sender's WhatsApp number (whatsapp:+...).
            message_sid: Twilio MessageSid for dedup.
        """
        # Dedup — Twilio retries on webhook timeout
        if message_sid:
            if message_sid in self._seen_sids:
                logger.debug("whatsapp_bot.dedup", sid=message_sid)
                return
            self._seen_sids.add(message_sid)
            # Prevent unbounded growth
            if len(self._seen_sids) > self._max_seen:
                self._seen_sids = set(list(self._seen_sids)[-5000:])

        # Normalize number
        if not from_number.startswith("whatsapp:"):
            from_number = f"whatsapp:{from_number}"

        # Handle commands
        lower = body.strip().lower()
        if lower in ("/help", "help", "/start"):
            await self._send_reply(from_number, GREETING)
            return
        if lower in ("/new", "/reset", "/clear"):
            await self._destroy_session(from_number)
            if self._task_queue:
                self._task_queue.clear_owner(from_number)
            await self._send_reply(
                from_number,
                "Session cleared. Send a new task to get started.",
            )
            return
        if lower in ("/status", "status"):
            await self._send_status(from_number)
            return

        # Get or create user session
        session = self._get_or_create_session(from_number)

        async with session.lock:
            session.last_active = time.time()
            session.message_count += 1

            # Send greeting on first interaction
            if session.is_first:
                session.is_first = False
                await self._send_reply(from_number, GREETING)
                await asyncio.sleep(0.5)

            # Route: build tasks → queue, chat → lightweight LLM response
            if self._is_build_task(body):
                await self._queue_build_task(from_number, body)
            else:
                # Simple chat/greeting — use server LLM key (lightweight)
                await self._send_reply(from_number, "_Processing your request..._")
                try:
                    response = await self._process_with_progress(session, body, from_number)
                    chunks = self.split_message(response)
                    for chunk in chunks:
                        await self._send_reply(from_number, chunk)
                        if len(chunks) > 1:
                            await asyncio.sleep(0.3)
                except Exception as exc:
                    logger.error(
                        "whatsapp_bot.process_error",
                        from_number=from_number,
                        error=str(exc),
                    )
                    await self._send_reply(
                        from_number,
                        f"Sorry, something went wrong: {str(exc)[:200]}\n\n"
                        "Send /new to start a fresh session.",
                    )

    @staticmethod
    def _is_build_task(body: str) -> bool:
        """Detect if a message is a build/engineering task vs simple chat.

        Build tasks are routed to the queue for local execution.
        Simple chat (greetings, questions, status) uses the server LLM key.
        """
        lower = body.strip().lower()

        # Short messages are usually chat
        if len(lower) < 15:
            return False

        # Build keywords
        build_keywords = [
            "build",
            "create",
            "make",
            "develop",
            "implement",
            "code",
            "write",
            "generate",
            "deploy",
            "setup",
            "install",
            "add",
            "fix",
            "update",
            "refactor",
            "migrate",
            "scrape",
            "crawl",
            "automate",
            "train",
            "process",
            "edit video",
            "convert",
            "transform",
            "analyze",
            "api",
            "app",
            "website",
            "dashboard",
            "database",
            "saas",
            "rest",
            "crud",
            "auth",
            "stripe",
        ]
        return any(kw in lower for kw in build_keywords)

    async def _queue_build_task(self, from_number: str, body: str) -> None:
        """Queue a build task for the user's local agent.

        If no task queue is configured, falls back to direct execution.
        """
        if not self._task_queue:
            # Fallback: no queue configured, run on server
            session = self._get_or_create_session(from_number)
            await self._send_reply(from_number, "_Processing your request..._")
            try:
                response = await self._process_with_progress(session, body, from_number)
                chunks = self.split_message(response)
                for chunk in chunks:
                    await self._send_reply(from_number, chunk)
                    if len(chunks) > 1:
                        await asyncio.sleep(0.3)
            except Exception as exc:
                await self._send_reply(
                    from_number,
                    f"Error: {str(exc)[:200]}\nSend /new to start fresh.",
                )
            return

        try:
            task = self._task_queue.submit(
                owner_id=from_number,
                instruction=body,
                channel="whatsapp",
                channel_address=from_number,
            )
            await self._send_reply(
                from_number,
                f"*Task Queued*\n\n"
                f"_{body[:200]}_\n\n"
                f"Your task is queued for your local Hauba agent.\n\n"
                f"Make sure `hauba agent` is running on your machine.\n"
                f"It will pick up this task and build it locally.\n\n"
                f"Commands:\n"
                f"  /status — Check task progress\n"
                f"  /clear  — Cancel all tasks\n\n"
                f"_Task ID: {task.task_id[:8]}_",
            )
        except ValueError as exc:
            await self._send_reply(from_number, f"Error: {exc}")

    async def _send_status(self, from_number: str) -> None:
        """Send task status summary to the user."""
        if not self._task_queue:
            await self._send_reply(from_number, "No task queue configured.")
            return

        tasks = self._task_queue.get_owner_tasks(from_number)
        if not tasks:
            await self._send_reply(from_number, "No tasks found. Send a task to get started.")
            return

        lines = ["*Your Tasks*\n"]
        status_emoji = {
            "queued": "⏳",
            "claimed": "🔄",
            "running": "⚡",
            "completed": "✅",
            "failed": "❌",
            "expired": "⏰",
        }
        for t in tasks[-5:]:  # Show last 5
            emoji = status_emoji.get(t.status, "❓")
            line = f"{emoji} {t.instruction[:60]}"
            if t.progress:
                line += f"\n   _{t.progress}_"
            lines.append(line)

        await self._send_reply(from_number, "\n".join(lines))

    async def _process_with_progress(
        self, session: UserSession, body: str, from_number: str
    ) -> str:
        """Run the message through CopilotEngine with periodic progress updates.

        Sends "still working..." messages every PROGRESS_INTERVAL seconds
        so the user knows the agent hasn't stalled.
        """
        progress_messages = [
            "_Still working on it..._",
            "_Making progress — hang tight..._",
            "_Building your project..._",
            "_Almost there — finalizing..._",
            "_Wrapping up the implementation..._",
        ]

        stop_progress = asyncio.Event()
        progress_idx = 0

        async def _send_progress() -> None:
            """Send periodic progress updates while the engine works."""
            nonlocal progress_idx
            while not stop_progress.is_set():
                try:
                    await asyncio.wait_for(stop_progress.wait(), timeout=PROGRESS_INTERVAL)
                    return  # stop_progress was set
                except TimeoutError:
                    msg = progress_messages[progress_idx % len(progress_messages)]
                    await self._send_reply(from_number, msg)
                    progress_idx += 1

        progress_task = asyncio.create_task(_send_progress())

        try:
            result = await self._execute_with_engine(session, body)
        finally:
            stop_progress.set()
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass

        if result.success:
            return result.output or "Task completed successfully."

        # Better timeout error message
        error = result.error or "Unknown error"
        if "timed out" in error.lower():
            return (
                "The task is taking longer than expected.\n\n"
                "This can happen with larger projects. You can:\n"
                "  1. Send your request again — I'll continue where I left off\n"
                "  2. Try a simpler version first (e.g., just the HTML)\n"
                "  3. Send /new to start fresh\n\n"
                f"_Technical: {error}_"
            )
        return f"Error: {error}"

    async def _execute_with_engine(self, session: UserSession, body: str) -> Any:
        """Run the message through CopilotEngine."""
        from hauba.engine.copilot_engine import CopilotEngine
        from hauba.engine.types import EngineConfig, ProviderType

        provider_map = {
            "anthropic": ProviderType.ANTHROPIC,
            "openai": ProviderType.OPENAI,
            "ollama": ProviderType.OLLAMA,
        }
        provider = provider_map.get(self._provider, ProviderType.ANTHROPIC)

        base_url = None
        if self._provider == "ollama":
            base_url = "http://localhost:11434/v1"

        timeout = TASK_TIMEOUT

        if session.engine is None:
            config = EngineConfig(
                provider=provider,
                api_key=self._api_key,
                model=self._model,
                base_url=base_url,
            )
            session.engine = CopilotEngine(config)
            return await session.engine.execute(body, timeout=timeout)
        else:
            # Follow-up message to existing session
            if session.engine.session:
                return await session.engine.send_message(body, timeout=timeout)
            else:
                return await session.engine.execute(body, timeout=timeout)

    async def _send_reply(self, to_number: str, text: str) -> None:
        """Send a WhatsApp reply via Twilio REST API."""
        if not self._twilio_client:
            logger.warning("whatsapp_bot.no_client")
            return

        # Ensure whatsapp: prefix on from number
        from_num = self._from_number
        if not from_num.startswith("whatsapp:"):
            from_num = f"whatsapp:{from_num}"

        try:
            self._twilio_client.messages.create(
                body=text[:MAX_MSG_LEN],
                from_=from_num,
                to=to_number,
            )
        except Exception as exc:
            logger.error(
                "whatsapp_bot.send_failed",
                to=to_number,
                error=str(exc),
            )

    def _get_or_create_session(self, from_number: str) -> UserSession:
        """Get existing session or create new one for this user."""
        if from_number not in self._sessions:
            self._sessions[from_number] = UserSession(
                last_active=time.time(),
            )
        return self._sessions[from_number]

    async def _destroy_session(self, from_number: str) -> None:
        """Destroy a user's session and clean up engine."""
        session = self._sessions.pop(from_number, None)
        if session and session.engine:
            try:
                await session.engine.stop()
            except Exception:
                pass

    async def cleanup_idle_sessions(self) -> int:
        """Remove sessions idle for more than SESSION_TIMEOUT.

        Returns the number of sessions cleaned up.
        """
        now = time.time()
        idle_numbers = [
            num for num, sess in self._sessions.items() if now - sess.last_active > SESSION_TIMEOUT
        ]

        for num in idle_numbers:
            await self._destroy_session(num)

        if idle_numbers:
            logger.info(
                "whatsapp_bot.cleanup",
                removed=len(idle_numbers),
                remaining=len(self._sessions),
            )

        return len(idle_numbers)

    async def start_cleanup_loop(self) -> None:
        """Start a background loop that cleans up idle sessions every 5 minutes."""

        async def _loop() -> None:
            while True:
                await asyncio.sleep(300)
                try:
                    await self.cleanup_idle_sessions()
                except Exception as exc:
                    logger.error("whatsapp_bot.cleanup_error", error=str(exc))

        self._cleanup_task = asyncio.create_task(_loop())

    @staticmethod
    def split_message(text: str, max_len: int = MAX_MSG_LEN) -> list[str]:
        """Split a long message into WhatsApp-safe chunks.

        Tries to split at paragraph boundaries first, then sentences,
        then hard-wraps at max_len.

        Args:
            text: The full message text.
            max_len: Maximum chunk length (default 1600).

        Returns:
            List of message chunks, each <= max_len chars.
        """
        if len(text) <= max_len:
            return [text]

        chunks: list[str] = []
        remaining = text

        while remaining:
            if len(remaining) <= max_len:
                chunks.append(remaining)
                break

            # Try paragraph break
            cut = remaining[:max_len].rfind("\n\n")
            if cut > max_len // 3:
                chunks.append(remaining[:cut].rstrip())
                remaining = remaining[cut:].lstrip()
                continue

            # Try sentence break
            for sep in (". ", ".\n", "! ", "? "):
                cut = remaining[:max_len].rfind(sep)
                if cut > max_len // 3:
                    chunks.append(remaining[: cut + 1].rstrip())
                    remaining = remaining[cut + 1 :].lstrip()
                    break
            else:
                # Try line break
                cut = remaining[:max_len].rfind("\n")
                if cut > max_len // 3:
                    chunks.append(remaining[:cut].rstrip())
                    remaining = remaining[cut:].lstrip()
                else:
                    # Hard wrap
                    chunks.append(remaining[:max_len])
                    remaining = remaining[max_len:]

        return chunks

    @property
    def session_count(self) -> int:
        """Number of active user sessions."""
        return len(self._sessions)
