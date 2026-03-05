"""Copilot Engine — the single execution brain for Hauba AI Workstation.

Powered by the GitHub Copilot SDK. This is the ONLY execution engine in Hauba.

Capabilities:
- BYOK (Bring Your Own Key) — user brings their API key, Hauba owner pays nothing
- Production-tested agent runtime (planning, tool invocation, file edits, git)
- Infinite sessions with automatic context compaction
- Session persistence for resuming interrupted tasks
- Streaming events for real-time UI updates
- Full AI Workstation: software, video, data, ML, docs, automation
- Interactive plan review — agent plans, user confirms before execution
- Human escalation — agent asks user for API keys, billing, credentials
- Multi-turn conversation — session stays open for follow-ups
- Delivery channels — notify via WhatsApp, Telegram, Discord on completion

Architecture:
    User Request → CopilotEngine → Copilot SDK → Agent Runtime
                                                      ↓
                                           (bash, files, git, web)
                                                      ↓
                                        on_user_input_request (human escalation)
                                                      ↓
                                        Plan → Confirm → Execute → Deliver
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from hauba.engine.types import EngineConfig, EngineEvent, EngineResult

logger = structlog.get_logger()


# --- Interactive handler types ---

# Called when the agent wants to ask the user a question (API key, confirm, etc.)
UserInputCallback = Callable[
    [str, list[str], bool],  # question, choices, allow_freeform
    Awaitable[str],  # answer
]

# Called when a plan is detected, receives plan text, returns True to proceed
PlanReviewCallback = Callable[
    [str],  # plan_text
    Awaitable[bool],  # approved
]

# Called when the task is complete, receives output text
DeliveryCallback = Callable[
    [str, str],  # output, session_id
    Awaitable[None],
]


@dataclass
class PlanState:
    """Persistent plan state — saved to disk so it survives interruptions."""

    task: str = ""
    plan_text: str = ""
    approved: bool = False
    session_id: str = ""
    timestamp: float = 0.0
    workspace: str = ""
    files_created: list[str] = field(default_factory=list)

    def save(self, path: Path) -> None:
        """Save plan state to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "task": self.task,
                    "plan_text": self.plan_text,
                    "approved": self.approved,
                    "session_id": self.session_id,
                    "timestamp": self.timestamp,
                    "workspace": self.workspace,
                    "files_created": self.files_created,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    @staticmethod
    def load(path: Path) -> PlanState | None:
        """Load plan state from disk."""
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return PlanState(**data)
        except Exception:
            return None


class CopilotEngine:
    """The single execution brain for Hauba AI Workstation.

    Wraps the GitHub Copilot SDK to provide a professional AI workstation
    that can build software, edit videos, process data, train ML models,
    generate documents, scrape websites, and automate workflows.

    Now supports:
    - Interactive plan review (plan → confirm → execute)
    - Human escalation (ask_user for API keys, billing, credentials)
    - Multi-turn conversation (send follow-up messages to the session)
    - Delivery channel notification on completion

    Example:
        >>> config = EngineConfig(
        ...     provider=ProviderType.ANTHROPIC,
        ...     api_key="sk-ant-...",
        ...     model="claude-sonnet-4-5",
        ... )
        >>> engine = CopilotEngine(config)
        >>> engine.set_user_input_handler(my_input_handler)
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

        # Interactive callbacks
        self._user_input_handler: UserInputCallback | None = None
        self._plan_review_handler: PlanReviewCallback | None = None
        self._delivery_handler: DeliveryCallback | None = None

        # Browser tool instance (reused across tool calls)
        self._browser_tool: Any = None

        # Plan tracking
        self._plan_state: PlanState | None = None
        self._plan_detected = asyncio.Event()

    # --- Public API for wiring interactive handlers ---

    def set_user_input_handler(self, handler: UserInputCallback) -> None:
        """Set the callback for when the agent asks the user a question.

        This fires for API key requests, billing confirmations, credential
        prompts, and any other human escalation. The Copilot SDK's ask_user
        tool triggers this.
        """
        self._user_input_handler = handler

    def set_plan_review_handler(self, handler: PlanReviewCallback) -> None:
        """Set the callback for plan review before execution starts."""
        self._plan_review_handler = handler

    def set_delivery_handler(self, handler: DeliveryCallback) -> None:
        """Set the callback for delivering results (WhatsApp, Telegram, Discord)."""
        self._delivery_handler = handler

    @property
    def is_available(self) -> bool:
        """Check if the Copilot SDK is available."""
        try:
            import copilot  # noqa: F401

            return True
        except ImportError:
            return False

    @property
    def session(self) -> Any:
        """Access the active Copilot session for multi-turn conversation."""
        return self._session

    @property
    def plan_state(self) -> PlanState | None:
        """Get the current plan state."""
        return self._plan_state

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

        The flow is:
        1. Create session with on_user_input_request wired up
        2. Send instruction → agent plans
        3. Agent's plan is captured via session events
        4. If plan_review_handler is set, pause and wait for user confirmation
        5. On confirmation, agent proceeds to execute
        6. On completion, delivery_handler is called if set

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
        self._plan_detected.clear()
        self._plan_state = PlanState(
            task=instruction,
            timestamp=time.time(),
            workspace=self._config.working_directory or ".",
        )

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

            if self._plan_state:
                self._plan_state.session_id = self._session.session_id

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

            # Persist plan state
            if self._plan_state:
                self._plan_state.approved = True
                plan_path = self._get_plan_state_path()
                if plan_path:
                    self._plan_state.save(plan_path)

            # Deliver results via channels if handler is set
            if self._delivery_handler and result.success:
                try:
                    await self._delivery_handler(result.output, result.session_id or "")
                except Exception as e:
                    logger.warning("engine.delivery_failed", error=str(e))

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

    async def send_message(self, message: str, *, timeout: float = 300.0) -> EngineResult:
        """Send a follow-up message to the active session.

        This enables multi-turn conversation. After the initial execute(),
        the user can send follow-ups like "ok proceed", "change the database
        to PostgreSQL", "add tests", etc.

        Args:
            message: The follow-up message text.
            timeout: Maximum wait time.

        Returns:
            EngineResult with the agent's response.
        """
        if not self._session:
            return EngineResult.fail("No active session. Run execute() first.")

        try:
            self._emit_event(
                EngineEvent(
                    type="engine.message_sent",
                    data={"message": message[:200]},
                    timestamp=time.time(),
                )
            )

            response = await self._session.send_and_wait(
                {"prompt": message},
                timeout=timeout,
            )

            output = ""
            if response and hasattr(response, "data"):
                data = response.data
                if hasattr(data, "content") and data.content:
                    output = data.content

            # Persist session
            if self._config.session_persist:
                self._save_session(self._session.session_id)

            return EngineResult.ok(
                output=output,
                session_id=self._session.session_id,
            )

        except TimeoutError:
            return EngineResult.fail(f"Response timed out after {timeout}s.")
        except Exception as e:
            logger.error("engine.send_message_error", error=str(e))
            return EngineResult.fail(str(e))

    def _build_session_config(self, system_message: str | None = None) -> dict[str, Any]:
        """Build the Copilot session config with BYOK provider and Hauba system prompt."""

        def _approve_all(request: Any, _context: Any) -> dict[str, Any]:
            """Auto-approve all permission requests (shell, write, read, etc.)."""
            return {"kind": "approved", "rules": []}

        config: dict[str, Any] = {
            "model": self._config.model,
            "provider": self._config.to_provider_config(),
            "on_permission_request": _approve_all,
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

        # Inject Hauba custom tools for full internet and system access
        custom_tools = self._build_custom_tools()
        if custom_tools:
            config["tools"] = custom_tools

        # Wire up the on_user_input_request handler for human escalation
        if self._user_input_handler:
            handler = self._user_input_handler

            async def _handle_user_input(
                request: dict[str, Any], _context: dict[str, str]
            ) -> dict[str, Any]:
                question = request.get("question", "The agent needs your input:")
                choices = request.get("choices", [])
                allow_freeform = request.get("allowFreeform", True)

                self._emit_event(
                    EngineEvent(
                        type="engine.human_escalation",
                        data={
                            "question": question,
                            "choices": choices,
                            "allow_freeform": allow_freeform,
                        },
                        timestamp=time.time(),
                    )
                )

                answer = await handler(question, choices, allow_freeform)

                return {
                    "answer": answer,
                    "wasFreeform": bool(not choices or answer not in choices),
                }

            config["on_user_input_request"] = _handle_user_input

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

### HUMAN ESCALATION

When you need information from the user, USE the ask_user tool. Examples:
- Need an API key → ask_user("Which API key should I use for Stripe?")
- Need billing confirmation → ask_user("This will incur costs. Proceed?", ["Yes", "No"])
- Need credentials → ask_user("What are the database credentials?")
- Need provider choice → ask_user("Which provider?", ["OpenAI", "Anthropic", "Ollama"])
- Need confirmation → ask_user("I've created the plan. Ready to proceed?", ["Yes, start", "No, modify"])

NEVER guess API keys, passwords, or credentials. ALWAYS ask the user.

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

### WEB ACCESS (INTERNET BROWSING) — FULL POWER

You have FULL unrestricted internet access through dedicated tools. Use them liberally:

1. **hauba_web_search**: Search the web (DuckDuckGo, free, no API key).
   Use this FIRST to research anything before implementing.

2. **hauba_web_fetch**: Read ANY URL — docs, APIs, GitHub repos, web pages.
   Converts HTML to readable text automatically.

3. **hauba_browser**: Full Playwright browser automation with persistent sessions.
   Navigate, click, type, extract, screenshot, scroll, run JavaScript.
   Sessions persist cookies/state. Use for dynamic sites, login flows, SPAs.

4. **hauba_send_email**: Send emails via Brevo API (free, 300/day).
   Use to send notifications, reports, or results.

5. **Bash tools**: You can also use curl, wget, httpx, requests via bash.
   `curl -LO "https://example.com/file.zip"` for downloads.

ALWAYS research before implementing unfamiliar technologies:
- Search for API documentation and examples
- Fetch and read official docs before coding
- Download dependencies, assets, and data files
- Verify solutions against real documentation
- Browse dynamic websites when static fetch isn't enough

### DESKTOP APPLICATION CONTROL

You can control desktop applications through bash and Python:
- **Blender**: Use `blender --background --python script.py` for 3D rendering
- **GIMP**: Use `gimp -i -b '(script-fu-command)'` for image editing
- **FFmpeg**: Use `ffmpeg` for video/audio processing
- **LibreOffice**: Use `libreoffice --headless --convert-to` for document conversion
- Any CLI tool installed on the user's machine is available to you

### PERSISTENT MEMORY

You have persistent memory across tasks. Use the workspace directory to:
- Write notes (e.g., `notes.md`) to remember context between conversations
- Read previous notes to continue where you left off
- Store learned patterns, API endpoints, and useful references
- Keep a `TODO.md` for multi-session projects

If you discover something important, write it down so you can reference it later.

### RULES

- Always use the tools available to you (bash, files, git)
- Never hallucinate file contents — read files before modifying them
- Verify your work after each step
- If something fails, analyze the error and try a different approach (max 3 retries)
- Write clean commit messages if using git
- Do NOT skip the verification step
- When installing packages, use `pip install` in the workspace
- For web apps, always include a README with setup instructions
- USE THE INTERNET to research before building — don't guess
"""
        if self._skill_context:
            prompt += f"\n### SKILL GUIDANCE\n\n{self._skill_context}\n"

        return prompt

    def _build_custom_tools(self) -> list[Any]:
        """Build custom tools that give CopilotEngine full internet and system access.

        These tools extend the Copilot SDK's built-in tools with Hauba's
        web search, web fetch, and browser automation capabilities.
        The agent can use these to research, browse websites, scrape data,
        and interact with any web service — all inside the sandbox.
        """
        tools: list[Any] = []

        try:
            from copilot import Tool
        except ImportError:
            return tools

        # Helper: extract params from ToolInvocation (SDK passes an object, not a dict)
        def _get_params(invocation: Any) -> dict[str, Any]:
            if isinstance(invocation, dict):
                return invocation
            if hasattr(invocation, "input"):
                inp = invocation.input
                return inp if isinstance(inp, dict) else {}
            if hasattr(invocation, "params"):
                p = invocation.params
                return p if isinstance(p, dict) else {}
            return {}

        # Helper: wrap result as ToolResult if needed by the SDK
        def _wrap_result(text: str) -> Any:
            try:
                from copilot import ToolResult as CopilotToolResult

                return CopilotToolResult(text)
            except (ImportError, TypeError):
                return text

        # Tool 1: Web Search (DuckDuckGo — no API key, free)
        async def _handle_web_search(invocation: Any) -> Any:
            params = _get_params(invocation)
            try:
                from hauba.tools.web import WebSearchTool

                tool = WebSearchTool()
                result = await tool.execute(
                    query=params.get("query", ""),
                    num_results=params.get("num_results", 5),
                )
                text = result.output if result.success else f"Search failed: {result.error}"
            except Exception as exc:
                text = f"Search error: {exc}"
            return _wrap_result(text)

        tools.append(
            Tool(
                name="hauba_web_search",
                description=(
                    "Search the web using DuckDuckGo. Returns titles, snippets, and URLs. "
                    "Use this to research technologies, find documentation, look up APIs, "
                    "and discover solutions before implementing."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query",
                        },
                        "num_results": {
                            "type": "integer",
                            "description": "Number of results (default: 5)",
                        },
                    },
                    "required": ["query"],
                },
                handler=_handle_web_search,
            )
        )

        # Tool 2: Web Fetch (read any URL as text)
        async def _handle_web_fetch(invocation: Any) -> Any:
            params = _get_params(invocation)
            try:
                from hauba.tools.fetch import WebFetchTool

                tool = WebFetchTool()
                result = await tool.execute(
                    url=params.get("url", ""),
                    extract_text=params.get("extract_text", True),
                )
                text = result.output if result.success else f"Fetch failed: {result.error}"
            except Exception as exc:
                text = f"Fetch error: {exc}"
            return _wrap_result(text)

        tools.append(
            Tool(
                name="hauba_web_fetch",
                description=(
                    "Fetch any URL and return its content as readable text. "
                    "Supports HTML (converted to text), JSON, and plain text. "
                    "Use this to read documentation, API responses, GitHub repos, "
                    "and any web page content."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to fetch",
                        },
                        "extract_text": {
                            "type": "boolean",
                            "description": "Extract readable text from HTML (default: true)",
                        },
                    },
                    "required": ["url"],
                },
                handler=_handle_web_fetch,
            )
        )

        # Tool 3: Browser Automation (Playwright — full web interaction)
        async def _handle_browser(invocation: Any) -> Any:
            params = _get_params(invocation)
            try:
                from hauba.tools.browser import BrowserTool

                if self._browser_tool is None:
                    self._browser_tool = BrowserTool(headless=True, stealth=True)

                result = await self._browser_tool.execute(**params)
                text = result.output if result.success else f"Browser error: {result.error}"
            except Exception as exc:
                text = f"Browser error: {exc}"
            return _wrap_result(text)

        tools.append(
            Tool(
                name="hauba_browser",
                description=(
                    "Full browser automation with persistent sessions. "
                    "Actions: navigate (url), click (selector), type (selector, text), "
                    "extract (selector — get text), screenshot (path), wait (selector), "
                    "scroll (direction), evaluate (JavaScript). "
                    "Sessions persist cookies and state across actions. "
                    "Use this to interact with web apps, fill forms, scrape dynamic content, "
                    "and automate any website interaction."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": [
                                "navigate",
                                "click",
                                "type",
                                "extract",
                                "screenshot",
                                "wait",
                                "scroll",
                                "evaluate",
                            ],
                            "description": "Browser action to perform",
                        },
                        "url": {
                            "type": "string",
                            "description": "URL for navigate action",
                        },
                        "selector": {
                            "type": "string",
                            "description": "CSS selector for click/type/extract/wait",
                        },
                        "text": {
                            "type": "string",
                            "description": "Text for type action",
                        },
                        "script": {
                            "type": "string",
                            "description": "JavaScript for evaluate action",
                        },
                        "direction": {
                            "type": "string",
                            "description": "Scroll direction: up, down, top, bottom",
                        },
                        "path": {
                            "type": "string",
                            "description": "File path for screenshot action",
                        },
                    },
                    "required": ["action"],
                },
                handler=_handle_browser,
            )
        )

        # Tool 4: Send Email (Brevo API — free)
        async def _handle_send_email(invocation: Any) -> Any:
            params = _get_params(invocation)
            try:
                from hauba.services.email import EmailService

                svc = EmailService()
                if not svc.configure():
                    return _wrap_result(
                        "Email not configured. Set HAUBA_EMAIL_API_KEY (Brevo, free) "
                        "and HAUBA_EMAIL_FROM environment variables."
                    )
                success = await svc.send(
                    to=params.get("to", ""),
                    subject=params.get("subject", ""),
                    body=params.get("body", ""),
                )
                text = "Email sent successfully." if success else "Failed to send email."
            except Exception as exc:
                text = f"Email error: {exc}"
            return _wrap_result(text)

        tools.append(
            Tool(
                name="hauba_send_email",
                description=(
                    "Send an email via Brevo API (free, 300/day). "
                    "Use this to send notifications, reports, or results to the user."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "Recipient email address",
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject line",
                        },
                        "body": {
                            "type": "string",
                            "description": "Email body text",
                        },
                    },
                    "required": ["to", "subject", "body"],
                },
                handler=_handle_send_email,
            )
        )

        logger.info("engine.custom_tools_loaded", count=len(tools))
        return tools

    def _handle_session_event(self, event: Any) -> None:
        """Handle events from the Copilot session and forward as EngineEvents."""
        event_type = str(event.type.value) if hasattr(event.type, "value") else str(event.type)

        engine_event = EngineEvent(
            type=event_type,
            data=event.data if hasattr(event, "data") else None,
            timestamp=time.time(),
        )
        self._emit_event(engine_event)

        # Track plan changes
        if event_type == "session.plan_changed" and self._plan_state is not None:
            data = event.data if hasattr(event, "data") else None
            if data:
                plan_text = ""
                if hasattr(data, "content") and data.content:
                    plan_text = data.content
                elif hasattr(data, "summary") and data.summary:
                    plan_text = data.summary
                elif isinstance(data, dict):
                    plan_text = data.get("content", data.get("summary", ""))
                if plan_text:
                    self._plan_state.plan_text = plan_text
                    self._plan_detected.set()

        # Track file creation
        if event_type == "session.workspace_file_changed" and self._plan_state is not None:
            data = event.data if hasattr(event, "data") else None
            if data:
                path = ""
                if hasattr(data, "path") and data.path:
                    path = data.path
                elif isinstance(data, dict):
                    path = data.get("path", "")
                if path and path not in self._plan_state.files_created:
                    self._plan_state.files_created.append(path)

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

    def _get_plan_state_path(self) -> Path | None:
        """Get the path for persisting plan state."""
        try:
            from hauba.core.constants import HAUBA_HOME

            return HAUBA_HOME / "last_plan.json"
        except Exception:
            return None

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

    @staticmethod
    def load_last_plan() -> PlanState | None:
        """Load the last saved plan state."""
        try:
            from hauba.core.constants import HAUBA_HOME

            return PlanState.load(HAUBA_HOME / "last_plan.json")
        except Exception:
            return None

    async def __aenter__(self) -> CopilotEngine:
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()
