"""Copilot Engine — production-grade agentic runtime powered by GitHub Copilot SDK.

This is the core execution engine for Hauba. It wraps the Copilot SDK to provide:
- BYOK (Bring Your Own Key) — user brings their API key, Hauba owner pays nothing
- Production-tested agent runtime (planning, tool invocation, file edits, git)
- Infinite sessions with automatic context compaction
- Custom tools via Hauba's TaskLedger integration
- Streaming events for real-time UI updates

Architecture:
    User Request → CopilotEngine → Copilot SDK → Copilot CLI Server → Agent Runtime
                                                                         ↓
                                                              (bash, files, git, web)
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import structlog

from hauba.engine.types import EngineConfig, EngineEvent, EngineResult

logger = structlog.get_logger()


def _find_copilot_cli() -> str | None:
    """Auto-detect the Copilot CLI binary location."""
    # 1. Check PATH for copilot / copilot.cmd / copilot.exe
    for name in ("copilot", "copilot.cmd", "copilot.exe"):
        path = shutil.which(name)
        if path:
            return path

    # 2. Check npm global install location
    if sys.platform == "win32":
        npm_prefix = os.environ.get("APPDATA", "")
        candidates = [
            os.path.join(npm_prefix, "npm", "copilot.cmd"),
            os.path.join(npm_prefix, "npm", "copilot"),
        ]
    else:
        candidates = [
            "/usr/local/bin/copilot",
            os.path.expanduser("~/.npm-global/bin/copilot"),
        ]

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    return None


class CopilotEngine:
    """Production-grade agentic engine powered by Copilot SDK.

    This engine provides:
    - BYOK support (Anthropic, OpenAI, Azure, Ollama)
    - Full agentic loop (planning, tool use, file edits, git)
    - Infinite sessions with automatic context compaction
    - Real-time event streaming
    - Custom Hauba tools (TaskLedger verification)

    Example:
        >>> config = EngineConfig(
        ...     provider=ProviderType.ANTHROPIC,
        ...     api_key="sk-ant-...",
        ...     model="claude-sonnet-4.5",
        ... )
        >>> engine = CopilotEngine(config)
        >>> result = await engine.execute("Build a REST API with auth")
        >>> print(result.output)
    """

    def __init__(self, config: EngineConfig) -> None:
        self._config = config
        self._client: Any = None
        self._session: Any = None
        self._events: list[EngineEvent] = []
        self._event_handlers: list[Callable[[EngineEvent], None]] = []
        self._cli_path = config.copilot_cli_path or _find_copilot_cli()

    @property
    def is_available(self) -> bool:
        """Check if the Copilot CLI is available."""
        return self._cli_path is not None

    async def start(self) -> None:
        """Initialize the Copilot SDK client and verify connection."""
        try:
            from copilot import CopilotClient
        except ImportError:
            raise RuntimeError("Copilot SDK not installed. Run: pip install github-copilot-sdk")

        if not self._cli_path:
            raise RuntimeError(
                "Copilot CLI not found. Install with: npm install -g @github/copilot\n"
                "Or provide copilot_cli_path in EngineConfig."
            )

        logger.info("engine.starting", cli_path=self._cli_path)

        self._client = CopilotClient({"cli_path": self._cli_path})
        await self._client.start()

        # Verify connection
        ping = await self._client.ping("hauba-engine")
        logger.info("engine.connected", ping=ping.message)

    async def stop(self) -> None:
        """Shut down the engine and clean up resources."""
        if self._session:
            try:
                await self._session.destroy()
            except Exception:
                pass
            self._session = None

        if self._client:
            try:
                await self._client.stop()
            except Exception:
                pass
            self._client = None

        logger.info("engine.stopped")

    def on_event(self, handler: Callable[[EngineEvent], None]) -> Callable[[], None]:
        """Subscribe to engine events for real-time streaming.

        Returns an unsubscribe function.
        """
        self._event_handlers.append(handler)

        def unsubscribe() -> None:
            if handler in self._event_handlers:
                self._event_handlers.remove(handler)

        return unsubscribe

    def _emit_event(self, event: EngineEvent) -> None:
        """Emit an event to all handlers."""
        self._events.append(event)
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.warning("engine.event_handler_error", error=str(e))

    async def execute(
        self,
        instruction: str,
        *,
        timeout: float = 300.0,
        system_message: str | None = None,
        session_id: str | None = None,
    ) -> EngineResult:
        """Execute a task using the Copilot agentic runtime.

        This is the main entry point. It creates a Copilot session with BYOK
        credentials, injects Hauba's system prompt and skills, sends the
        instruction, and waits for the agent to complete.

        Args:
            instruction: What to build/do (plain English).
            timeout: Maximum execution time in seconds (default: 5 minutes).
            system_message: Optional system message to append.
            session_id: Optional session ID to resume a previous session.

        Returns:
            EngineResult with success/failure, output, events, and session ID.
        """
        if not self._client:
            await self.start()

        self._events.clear()
        self._emit_event(EngineEvent(type="engine.task_started", timestamp=time.time()))

        try:
            # Build session config
            session_config = self._build_session_config(system_message)

            # Create or resume session
            if session_id:
                self._session = await self._client.resume_session(session_id, session_config)
                logger.info("engine.session_resumed", session_id=session_id)
            else:
                self._session = await self._client.create_session(session_config)
                logger.info(
                    "engine.session_created",
                    session_id=self._session.session_id,
                )

            # Subscribe to all session events
            self._session.on(self._handle_session_event)

            # Send instruction and wait for completion
            self._emit_event(
                EngineEvent(
                    type="engine.executing",
                    data={"instruction": instruction[:200]},
                    timestamp=time.time(),
                )
            )

            response = await self._session.send_and_wait(
                {"prompt": instruction},
                timeout=timeout,
            )

            # Extract result
            output = ""
            if response and hasattr(response, "data"):
                data = response.data
                if hasattr(data, "content") and data.content:
                    output = data.content

            self._emit_event(
                EngineEvent(
                    type="engine.task_completed",
                    data={"output_length": len(output)},
                    timestamp=time.time(),
                )
            )

            return EngineResult.ok(
                output=output,
                session_id=self._session.session_id,
            )

        except TimeoutError:
            self._emit_event(EngineEvent(type="engine.timeout", timestamp=time.time()))
            return EngineResult.fail(
                f"Task timed out after {timeout}s. The agent may still be working."
            )
        except Exception as e:
            logger.error("engine.execute_error", error=str(e))
            self._emit_event(
                EngineEvent(
                    type="engine.error",
                    data={"error": str(e)},
                    timestamp=time.time(),
                )
            )
            return EngineResult.fail(str(e))

    def _build_session_config(self, system_message: str | None = None) -> dict[str, Any]:
        """Build the Copilot session config with BYOK provider and Hauba system prompt."""
        from copilot import PermissionHandler

        config: dict[str, Any] = {
            "model": self._config.model,
            "provider": self._config.to_provider_config(),
            "on_permission_request": PermissionHandler.approve_all,
            "streaming": self._config.streaming,
        }

        # Set working directory
        if self._config.working_directory:
            config["working_directory"] = str(Path(self._config.working_directory).resolve())

        # Build system message
        hauba_system = self._build_hauba_system_prompt()
        if system_message:
            hauba_system += f"\n\n{system_message}"

        config["system_message"] = {
            "mode": "append",
            "content": hauba_system,
        }

        # Add skill directories
        if self._config.skill_directories:
            config["skill_directories"] = self._config.skill_directories

        # Add bundled skills directory
        bundled_skills = Path(__file__).parent.parent / "bundled_skills"
        if bundled_skills.exists():
            dirs = config.get("skill_directories", [])
            dirs.append(str(bundled_skills))
            config["skill_directories"] = dirs

        # Infinite sessions for long-running tasks
        config["infinite_sessions"] = {
            "enabled": True,
            "background_compaction_threshold": 0.80,
            "buffer_exhaustion_threshold": 0.95,
        }

        return config

    def _build_hauba_system_prompt(self) -> str:
        """Build the Hauba AI Engineer system prompt.

        This prompt transforms the generic Copilot agent into a professional
        AI software engineer that follows Hauba's execution protocol.
        """
        return """## You are Hauba AI Engineer

You are a professional AI software engineer powered by Hauba. You ship production-ready code.

### EXECUTION PROTOCOL (MANDATORY)

Follow this 5-phase protocol for every task:

**Phase 1: UNDERSTAND**
- Read the instruction carefully
- Identify what needs to be built, fixed, or changed
- List the technologies and files involved

**Phase 2: PLAN**
- Break the task into concrete steps
- Identify dependencies between steps
- Consider edge cases and error handling

**Phase 3: IMPLEMENT**
- Write clean, production-ready code
- Follow best practices for the language/framework
- Handle errors properly
- Write secure code (no hardcoded secrets, proper input validation)

**Phase 4: VERIFY**
- After writing code, verify it compiles/runs
- Run any existing tests
- Check that the output matches the requirements
- Fix any issues found

**Phase 5: DELIVER**
- Summarize what was done
- List files created/modified
- Note any follow-up tasks or considerations

### RULES
- Always use the tools available to you (bash, files, git)
- Never hallucinate file contents — read files before modifying them
- Verify your work after each step
- If something fails, try a different approach (max 3 retries)
- Write clean commit messages if using git
- Do NOT skip the verification step
"""

    def _handle_session_event(self, event: Any) -> None:
        """Handle events from the Copilot session and forward as EngineEvents."""
        event_type = str(event.type.value) if hasattr(event.type, "value") else str(event.type)

        engine_event = EngineEvent(
            type=event_type,
            data=event.data if hasattr(event, "data") else None,
            timestamp=time.time(),
        )
        self._emit_event(engine_event)

    async def __aenter__(self) -> CopilotEngine:
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()
