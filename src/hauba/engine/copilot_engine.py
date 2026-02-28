"""Copilot Engine — the single execution brain for Hauba AI Workstation.

Powered by the GitHub Copilot SDK. This is the ONLY execution engine in Hauba.

Capabilities:
- BYOK (Bring Your Own Key) — user brings their API key, Hauba owner pays nothing
- Production-tested agent runtime (planning, tool invocation, file edits, git)
- Infinite sessions with automatic context compaction
- Session persistence for resuming interrupted tasks
- Streaming events for real-time UI updates
- Full AI Workstation: software, video, data, ML, docs, automation

Architecture:
    User Request → CopilotEngine → Copilot SDK → Agent Runtime
                                                      ↓
                                           (bash, files, git, web)
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import structlog

from hauba.engine.types import EngineConfig, EngineEvent, EngineResult

logger = structlog.get_logger()


class CopilotEngine:
    """The single execution brain for Hauba AI Workstation.

    Wraps the GitHub Copilot SDK to provide a professional AI workstation
    that can build software, edit videos, process data, train ML models,
    generate documents, scrape websites, and automate workflows.

    Example:
        >>> config = EngineConfig(
        ...     provider=ProviderType.ANTHROPIC,
        ...     api_key="sk-ant-...",
        ...     model="claude-sonnet-4-5",
        ... )
        >>> engine = CopilotEngine(config)
        >>> result = await engine.execute("Build a REST API with auth")
        >>> print(result.output)
    """

    def __init__(self, config: EngineConfig, skill_context: str = "") -> None:
        self._config = config
        self._skill_context = skill_context
        self._client: Any = None
        self._session: Any = None
        self._events: list[EngineEvent] = []
        self._event_handlers: list[Callable[[EngineEvent], None]] = []

    @property
    def is_available(self) -> bool:
        """Check if the Copilot SDK is available."""
        try:
            import copilot  # noqa: F401

            return True
        except ImportError:
            return False

    async def start(self) -> None:
        """Initialize the Copilot SDK client and verify connection."""
        try:
            from copilot import CopilotClient
        except ImportError:
            raise RuntimeError("Copilot SDK not installed. Run: pip install github-copilot-sdk")

        client_options: dict[str, Any] = {}
        if self._config.copilot_cli_path:
            client_options["cli_path"] = self._config.copilot_cli_path

        logger.info("engine.starting")

        self._client = CopilotClient(client_options or None)
        await self._client.start()

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
            session_config = self._build_session_config(system_message)

            if session_id:
                self._session = await self._client.resume_session(session_id, session_config)
                logger.info("engine.session_resumed", session_id=session_id)
            else:
                self._session = await self._client.create_session(session_config)
                logger.info(
                    "engine.session_created",
                    session_id=self._session.session_id,
                )

            self._session.on(self._handle_session_event)

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

            result = EngineResult.ok(
                output=output,
                session_id=self._session.session_id,
            )

            # Persist session for --continue support
            if self._config.session_persist:
                self._save_session(self._session.session_id)

            return result

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

        if self._config.working_directory:
            config["working_directory"] = str(Path(self._config.working_directory).resolve())

        hauba_system = self._build_hauba_system_prompt()
        if system_message:
            hauba_system += f"\n\n{system_message}"

        config["system_message"] = {
            "mode": "append",
            "content": hauba_system,
        }

        if self._config.skill_directories:
            config["skill_directories"] = self._config.skill_directories

        bundled_skills = Path(__file__).parent.parent / "bundled_skills"
        if bundled_skills.exists():
            dirs = config.get("skill_directories", [])
            dirs.append(str(bundled_skills))
            config["skill_directories"] = dirs

        config["infinite_sessions"] = {
            "enabled": True,
            "background_compaction_threshold": 0.80,
            "buffer_exhaustion_threshold": 0.95,
        }

        return config

    def _build_hauba_system_prompt(self) -> str:
        """Build the Hauba AI Workstation system prompt.

        This prompt transforms the Copilot SDK agent into a professional
        AI workstation capable of software engineering, video editing,
        data processing, ML, document generation, and automation.
        """
        prompt = """## You are Hauba AI Workstation

You are a professional AI workstation powered by Hauba. You don't just write code — you build
real software, edit videos, process data, train ML models, generate documents, scrape websites,
and automate workflows. You are the smartest AI engineer in the market.

You MUST use your tools (bash, files, git) to actually create files and produce real outputs.
Never just describe what you would do — DO IT by calling tools.

### CAPABILITIES

You can handle ANY task that can be done with Python and command-line tools:
- **Software Engineering**: Build full-stack apps, APIs, databases, deployments
- **Video Editing**: Trim, concatenate, add effects/subtitles using MoviePy
- **Data Processing**: Analyze CSV/Excel/JSON with pandas, create visualizations
- **Machine Learning**: Train models with scikit-learn, evaluate, serialize, huggingface integration
- **Document Generation**: Create PDFs, presentations, spreadsheets
- **Web Scraping**: Extract data from websites with BeautifulSoup/Playwright
- **Automation**: Build scripts, CLI tools, batch processors
- **Image Processing**: Manipulate images with Pillow

### EXECUTION PROTOCOL (MANDATORY)

Follow this 5-phase protocol for EVERY task:

**Phase 1: UNDERSTAND**
- Read the instruction carefully — what exactly needs to be built or done?
- Identify technologies, files, and dependencies involved
- Check if the task requires installing Python packages

**Phase 2: PLAN**
- Break the task into concrete, ordered steps
- Identify dependencies between steps
- If a matched skill has a Playbook section, follow its milestones
- Consider edge cases and error handling

**Phase 3: IMPLEMENT**
- Install required Python packages: `pip install <package>` as needed
- Write clean, production-ready code
- Follow best practices for the language/framework
- Handle errors properly — no silent failures
- Write secure code (no hardcoded secrets, proper input validation)
- Create ALL necessary files — no placeholders, no TODOs, no stubs

**Phase 4: VERIFY**
- After creating files, verify they exist and have correct content
- Run code to confirm it works (compile, execute, test)
- Check that output matches requirements
- Fix any issues found — max 3 retries per step

**Phase 5: DELIVER**
- Summarize what was accomplished
- List all files created/modified
- Note any setup steps or follow-up tasks

### TOOL INSTALLATION

When a task requires a Python package you don't have:
1. Install it: `pip install moviepy pandas scikit-learn pillow reportlab beautifulsoup4`
2. Verify the install: `python -c "import <package>; print('OK')"`
3. Proceed with the task

Common packages by domain:
- Video: moviepy, imageio[ffmpeg]
- Data: pandas, matplotlib, seaborn, plotly, openpyxl
- ML: scikit-learn, joblib, numpy, huggingface transformers
- Images: Pillow, cairosvg
- Documents: reportlab, python-pptx, openpyxl, jinja2, weasyprint
- Web scraping: beautifulsoup4, requests, lxml
- Automation: click, typer, schedule

### RULES

- Always use the tools available to you (bash, files, git)
- Never hallucinate file contents — read files before modifying them
- Verify your work after each step
- If something fails, analyze the error and try a different approach (max 3 retries)
- Write clean commit messages if using git
- Do NOT skip the verification step
- When installing packages, use `pip install` in the workspace
- For web apps, always include a README with setup instructions
"""
        if self._skill_context:
            prompt += f"\n### SKILL GUIDANCE\n\n{self._skill_context}\n"

        return prompt

    def _handle_session_event(self, event: Any) -> None:
        """Handle events from the Copilot session and forward as EngineEvents."""
        event_type = str(event.type.value) if hasattr(event.type, "value") else str(event.type)

        engine_event = EngineEvent(
            type=event_type,
            data=event.data if hasattr(event, "data") else None,
            timestamp=time.time(),
        )
        self._emit_event(engine_event)

    def _save_session(self, session_id: str) -> None:
        """Save session ID for --continue support."""
        try:
            from hauba.core.constants import LAST_SESSION_FILE

            LAST_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
            LAST_SESSION_FILE.write_text(
                json.dumps({"session_id": session_id, "timestamp": time.time()}),
                encoding="utf-8",
            )
        except Exception as e:
            logger.debug("engine.session_save_failed", error=str(e))

    @staticmethod
    def load_last_session() -> str | None:
        """Load the last saved session ID for --continue support."""
        try:
            from hauba.core.constants import LAST_SESSION_FILE

            if LAST_SESSION_FILE.exists():
                data = json.loads(LAST_SESSION_FILE.read_text(encoding="utf-8"))
                return data.get("session_id")
        except Exception:
            pass
        return None

    async def __aenter__(self) -> CopilotEngine:
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()
