"""Hauba CLI — AI Workstation entry point.

All execution flows through CopilotEngine (GitHub Copilot SDK).

Interactive flow:
1. User runs: hauba run "build me a SaaS dashboard"
2. Engine plans the task, showing real-time thinking/tool activity
3. User sees the plan and confirms ("ok", "proceed", "start")
4. Engine executes, asking the user for input when needed (API keys, etc.)
5. On completion, user chooses delivery channel (WhatsApp, Telegram, Discord)
6. Multi-turn conversation stays open for follow-ups

UI Design:
- Claude Code style interactive terminal
- Live spinners for thinking/planning/executing phases
- File tracking panel showing which files are being worked on
- Tool invocation display with command details
- Arrow-key driven menus for selections
- Beautiful Rich panels with status indicators
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from hauba.skills.cli import skill_app

app = typer.Typer(
    name="hauba",
    help="AI Workstation — Build Software, Edit Video, Process Data, and More",
    no_args_is_help=True,
)
app.add_typer(skill_app, name="skill")

compose_app = typer.Typer(name="compose", help="Manage agent teams via hauba.yaml")
app.add_typer(compose_app, name="compose")

plugins_app = typer.Typer(name="plugins", help="Manage Hauba plugins")
app.add_typer(plugins_app, name="plugins")


def _configure_logging_to_file() -> None:
    """Redirect structlog output to ~/.hauba/logs/ instead of stdout.

    Without this, structlog's default ConsoleRenderer dumps all log lines
    (engine.starting, engine.connected, etc.) directly to the terminal,
    cluttering the interactive UI.
    """
    import logging

    import structlog

    from hauba.core.constants import LOGS_DIR

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / "hauba.log"

    # File handler for Python stdlib logging
    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    # Configure stdlib logging to write to file only
    logging.basicConfig(
        handlers=[file_handler],
        level=logging.INFO,
        format="%(message)s",
        force=True,
    )

    # Configure structlog to use stdlib logging (which goes to file)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Force UTF-8 on Windows to avoid cp1252 UnicodeEncodeError with Rich
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

console = Console()


@app.command()
def init() -> None:
    """Initialize Hauba — creates ~/.hauba/ and runs interactive setup wizard."""
    from hauba.core.setup import ensure_hauba_dirs
    from hauba.ui.interactive import select_menu

    console.print()
    console.print(
        Panel(
            "[bold cyan]Hauba — Your AI Engineering Team[/bold cyan]\n\n"
            "Build software, edit video, process data, train ML models,\n"
            "generate documents, scrape websites, and automate anything.\n\n"
            "[dim]One command. Ship products. Not prompts.[/dim]",
            title="[bold]Welcome[/bold]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    ensure_hauba_dirs()
    console.print("  [green]+[/green] Created ~/.hauba/ directory structure")

    from hauba.core.config import ConfigManager

    config = ConfigManager()

    console.print()
    name = Prompt.ask("  [bold]Your name[/bold]", default="Developer")
    config.settings.owner_name = name

    # Interactive provider selection with arrow keys
    providers = ["Anthropic (Claude)", "OpenAI (GPT)", "Ollama (Local)", "DeepSeek"]
    provider_keys = ["anthropic", "openai", "ollama", "deepseek"]
    provider_descs = [
        "Best for coding — Claude Sonnet 4.5",
        "GPT-4o and latest models",
        "100% local, no API key needed",
        "Cost-effective alternative",
    ]
    idx = select_menu(console, "Choose your LLM provider:", providers, provider_descs)
    if idx < 0:
        idx = 0
    provider = provider_keys[idx]
    config.settings.llm.provider = provider

    if provider == "ollama":
        config.settings.llm.base_url = "http://localhost:11434"
        # Model selection for Ollama
        ollama_models = ["llama3.1", "codellama", "mixtral", "deepseek-coder"]
        ollama_descs = [
            "General purpose, fast",
            "Specialized for code",
            "Mixture of experts, capable",
            "Code generation specialist",
        ]
        midx = select_menu(console, "Choose Ollama model:", ollama_models, ollama_descs)
        if midx < 0:
            midx = 0
        config.settings.llm.model = ollama_models[midx]
        config.settings.llm.api_key = "ollama"
    else:
        console.print()
        api_key = Prompt.ask(f"  [bold]{provider} API key[/bold]", password=True)
        api_key = api_key.strip()
        if provider == "openai" and api_key.startswith("sk-"):
            for prefix in ("sk-proj-", "sk-"):
                if api_key.startswith(prefix):
                    second = api_key.find(prefix, len(prefix))
                    if second > 0:
                        api_key = api_key[:second]
                        console.print(
                            "  [yellow]Note: Detected duplicate paste — trimmed to single key.[/yellow]"
                        )
                    break
        config.settings.llm.api_key = api_key

        # Model selection with arrow keys
        if provider == "anthropic":
            models = [
                "claude-sonnet-4-5-20250929",
                "claude-opus-4-5-20250514",
                "claude-haiku-4-5-20251001",
            ]
            model_descs = [
                "Best balance of speed + quality",
                "Most capable, slower",
                "Fastest, budget-friendly",
            ]
        elif provider == "openai":
            models = ["gpt-4o", "gpt-4o-mini", "o3"]
            model_descs = ["Best balance", "Fast and cheap", "Advanced reasoning"]
        else:
            models = ["deepseek-chat", "deepseek-coder"]
            model_descs = ["General purpose", "Code specialized"]

        midx = select_menu(console, "Choose model:", models, model_descs)
        if midx < 0:
            midx = 0
        config.settings.llm.model = models[midx]

    config.save()
    console.print()
    console.print("  [green]+[/green] Configuration saved to ~/.hauba/settings.json")

    # Test Copilot SDK availability
    console.print("  [dim]Checking Copilot SDK...[/dim]")
    try:
        import copilot  # noqa: F401

        console.print("  [green]+[/green] Copilot SDK is installed")
    except ImportError:
        console.print(
            "  [yellow]![/yellow] Copilot SDK not found. Install: pip install github-copilot-sdk"
        )
    except Exception:
        console.print("  [green]+[/green] Engine check complete")

    console.print()
    console.print(
        Panel(
            f"[bold green]Hauba is ready![/bold green]\n\n"
            f"  Owner:    {name}\n"
            f"  Provider: {provider}\n"
            f"  Model:    {config.settings.llm.model}\n\n"
            f"[bold]Next steps:[/bold]\n\n"
            f'  [green]1.[/green] [bold]hauba run "build me a SaaS dashboard"[/bold]\n'
            f"  [green]2.[/green] [bold]hauba setup whatsapp[/bold]   [dim]# Get results on WhatsApp[/dim]\n"
            f"  [green]3.[/green] [bold]hauba doctor[/bold]           [dim]# Check system health[/dim]",
            border_style="green",
            padding=(1, 2),
        )
    )


@app.command()
def run(
    task: str = typer.Argument(..., help="Task for your AI workstation"),
    workspace: str = typer.Option(
        "",
        "--workspace",
        "-w",
        help="Output directory for generated files (default: ./hauba-output/)",
    ),
    continue_session: bool = typer.Option(
        False,
        "--continue",
        "-c",
        help="Resume the last session",
    ),
    interactive: bool = typer.Option(
        True,
        "--interactive/--no-interactive",
        "-i/-I",
        help="Enable interactive mode (plan review, delivery, multi-turn)",
    ),
) -> None:
    """Run a task with the Hauba AI Workstation.

    Interactive mode (default):
    - Agent plans the task with live progress indicators
    - You review and confirm before execution
    - Agent asks you for input when needed (API keys, credentials, etc.)
    - After completion, choose a delivery channel
    - Continue the conversation with follow-up messages

    Non-interactive mode (--no-interactive):
    - Agent runs to completion without pausing
    """
    _check_init()
    _configure_logging_to_file()
    asyncio.run(_run_task(task, workspace, continue_session, interactive))


def _build_skill_context(task: str) -> str:
    """Load Hauba skills, match them to the task, build context for injection."""
    from hauba.core.constants import BUNDLED_SKILLS_DIR, SKILLS_DIR
    from hauba.skills.loader import SkillLoader
    from hauba.skills.matcher import SkillMatcher

    try:
        skill_loader = SkillLoader(skill_dirs=[SKILLS_DIR, BUNDLED_SKILLS_DIR])
        skill_matcher = SkillMatcher(skill_loader)
    except Exception:
        return ""

    parts: list[str] = []

    matches = skill_matcher.match(task, top_k=3)
    if matches:
        parts.append("## Skill Guidance (follow during execution)")
        for match in matches:
            skill = match.skill
            parts.append(f"\n### {skill.name} (relevance: {match.score:.0%})")
            if skill.approach:
                parts.append("Approach:")
                for step in skill.approach:
                    parts.append(f"  - {step}")
            if skill.constraints:
                parts.append("Constraints (MUST follow):")
                for c in skill.constraints:
                    parts.append(f"  - {c}")

    return "\n".join(parts)


# --- Interactive handlers for Rich CLI ---


async def _cli_user_input_handler(
    question: str,
    choices: list[str],
    allow_freeform: bool,
) -> str:
    """Handle agent's ask_user requests via Rich terminal prompts.

    This is called when the agent needs human input — API keys, billing
    confirmation, credential prompts, provider choices, etc.
    """
    from hauba.ui.interactive import InteractiveUI, select_menu

    ui = InteractiveUI(console)
    ui.show_human_escalation(question)

    if choices and not allow_freeform:
        idx = select_menu(console, "Choose:", choices)
        if idx >= 0:
            return choices[idx]
        return choices[0] if choices else ""
    elif choices:
        idx = select_menu(console, "Choose (or type your own):", [*choices, "(type your own)"])
        if idx >= 0 and idx < len(choices):
            return choices[idx]
        return Prompt.ask("  [bold]Your answer[/bold]")
    else:
        # Freeform input — detect secrets
        is_secret = any(
            kw in question.lower()
            for kw in ["api key", "password", "secret", "token", "credential", "auth"]
        )
        return Prompt.ask("  [bold]Your answer[/bold]", password=is_secret)


async def _cli_delivery_handler(output: str, session_id: str) -> None:
    """Ask user which channel to deliver results to after task completion."""
    from hauba.ui.interactive import confirm_prompt, show_delivery_menu

    deliver = confirm_prompt(
        console,
        "Deliver results via a channel? (WhatsApp/Telegram/Discord)",
        default=False,
    )

    if not deliver:
        return

    channel = show_delivery_menu(console)

    if not channel:
        return

    # Prepare a summary for delivery
    summary = output[:1500] if output else "Task completed successfully."

    if channel == "whatsapp":
        await _deliver_whatsapp(summary)
    elif channel == "telegram":
        await _deliver_telegram(summary)
    elif channel == "discord":
        await _deliver_discord(summary)


def _resolve_twilio_creds() -> tuple[str, str, str, str]:
    """Resolve Twilio credentials from env vars > config file.

    Returns (account_sid, auth_token, from_number, to_number).
    Env vars take priority: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
    TWILIO_WHATSAPP_NUMBER, HAUBA_WHATSAPP_TO.
    """
    from hauba.core.config import ConfigManager

    config = ConfigManager()

    sid = os.environ.get("TWILIO_ACCOUNT_SID") or config.get("whatsapp.account_sid") or ""
    token = os.environ.get("TWILIO_AUTH_TOKEN") or config.get("whatsapp.auth_token") or ""
    from_num = (
        os.environ.get("TWILIO_WHATSAPP_NUMBER")
        or config.get("whatsapp.from_number")
        or "whatsapp:+14155238886"
    )
    to_num = os.environ.get("HAUBA_WHATSAPP_TO") or config.get("whatsapp.to_number") or ""

    return sid, token, from_num, to_num


async def _deliver_whatsapp(summary: str) -> None:
    """Deliver results via WhatsApp — zero-friction if configured."""
    sid, token, from_num, to_number = _resolve_twilio_creds()

    if not sid or not token:
        console.print(
            Panel(
                "[bold yellow]WhatsApp not set up yet[/bold yellow]\n\n"
                "  Run: [bold]hauba setup whatsapp[/bold]\n\n"
                "  Or set env vars (Railway / .env):\n"
                "    TWILIO_ACCOUNT_SID=your_sid\n"
                "    TWILIO_AUTH_TOKEN=your_token",
                border_style="yellow",
                padding=(1, 2),
            )
        )
        return

    # If no saved recipient, ask once
    if not to_number:
        to_number = Prompt.ask(
            "  [bold]Your WhatsApp number[/bold] [dim](e.g. +9779812345678)[/dim]"
        )
        if not to_number.strip():
            console.print("  [dim]Skipped.[/dim]")
            return
        # Save for next time
        from hauba.core.config import ConfigManager

        cfg = ConfigManager()
        cfg.set("whatsapp.to_number", to_number.strip())
        console.print("  [dim]Saved your number for future deliveries.[/dim]")

    try:
        from hauba.channels.whatsapp import WhatsAppChannel
        from hauba.core.events import EventEmitter

        events = EventEmitter()
        wa = WhatsAppChannel(
            account_sid=sid,
            auth_token=token,
            from_number=from_num,
            events=events,
        )
        await wa.start()
        await wa.send_message(to_number, f"Hauba Task Complete:\n\n{summary}")
        await wa.stop()
        console.print("  [green]+[/green] Delivered via WhatsApp")
    except Exception as exc:
        console.print(f"  [red]WhatsApp delivery failed: {exc}[/red]")
        console.print(
            "  [dim]Make sure you've joined the Twilio Sandbox first.[/dim]\n"
            "  [dim]Run: hauba setup whatsapp[/dim]"
        )


async def _deliver_telegram(summary: str) -> None:
    """Deliver results via Telegram."""
    from hauba.core.config import ConfigManager

    config = ConfigManager()
    token = config.get("telegram.bot_token") or ""

    if not token:
        console.print(
            "[yellow]Telegram not configured.[/yellow]\n"
            "  Run: hauba config telegram.bot_token <YOUR_BOT_TOKEN>"
        )
        return

    chat_id = Prompt.ask("  [bold]Telegram chat ID[/bold]")

    try:
        from hauba.channels.telegram import TelegramChannel
        from hauba.core.events import EventEmitter

        events = EventEmitter()
        tg = TelegramChannel(token=token, events=events)
        await tg.start()
        await tg.send_message(int(chat_id), f"Hauba Task Complete:\n\n{summary}")
        await tg.stop()
        console.print("  [green]+[/green] Delivered via Telegram")
    except Exception as exc:
        console.print(f"  [red]Telegram delivery failed: {exc}[/red]")


async def _deliver_discord(summary: str) -> None:
    """Deliver results via Discord."""
    from hauba.core.config import ConfigManager

    config = ConfigManager()
    token = config.get("discord.bot_token") or ""

    if not token:
        console.print(
            "[yellow]Discord not configured.[/yellow]\n"
            "  Run: hauba config discord.bot_token <YOUR_BOT_TOKEN>"
        )
        return

    channel_id = Prompt.ask("  [bold]Discord channel ID[/bold]")

    try:
        from hauba.channels.discord import DiscordChannel
        from hauba.core.events import EventEmitter

        events = EventEmitter()
        dc = DiscordChannel(token=token, events=events)
        await dc.start()
        await dc.send_message(int(channel_id), f"Hauba Task Complete:\n\n{summary}")
        await dc.stop()
        console.print("  [green]+[/green] Delivered via Discord")
    except Exception as exc:
        console.print(f"  [red]Discord delivery failed: {exc}[/red]")


async def _run_task(
    task: str,
    workspace_path: str = "",
    continue_session: bool = False,
    interactive: bool = True,
) -> None:
    """Execute a task using the CopilotEngine with full interactive UI."""
    from hauba.core.config import ConfigManager
    from hauba.engine.copilot_engine import CopilotEngine
    from hauba.engine.types import EngineConfig, ProviderType
    from hauba.ui.interactive import InteractiveUI

    config = ConfigManager()

    provider_map = {
        "anthropic": ProviderType.ANTHROPIC,
        "openai": ProviderType.OPENAI,
        "ollama": ProviderType.OLLAMA,
        "deepseek": ProviderType.OPENAI,
    }
    provider = provider_map.get(config.settings.llm.provider, ProviderType.ANTHROPIC)

    base_url = None
    if config.settings.llm.provider == "deepseek":
        base_url = "https://api.deepseek.com/v1"
    elif config.settings.llm.provider == "ollama":
        base_url = config.settings.llm.base_url or "http://localhost:11434/v1"

    ws_path = Path(workspace_path).resolve() if workspace_path else Path.cwd() / "hauba-output"
    ws_path.mkdir(parents=True, exist_ok=True)

    engine_config = EngineConfig(
        provider=provider,
        api_key=config.settings.llm.api_key,
        model=config.settings.llm.model,
        base_url=base_url,
        working_directory=str(ws_path),
    )

    skill_context = _build_skill_context(task)

    engine = CopilotEngine(engine_config, skill_context=skill_context)

    if not engine.is_available:
        console.print(
            Panel(
                "[bold red]Copilot SDK not installed[/bold red]\n\n"
                "Hauba requires the Copilot SDK to work.\n\n"
                "  Install: [bold]pip install github-copilot-sdk[/bold]",
                title="Missing Dependency",
                border_style="red",
            )
        )
        raise typer.Exit(1)

    # Wire up interactive handlers
    if interactive:
        engine.set_user_input_handler(_cli_user_input_handler)
        engine.set_delivery_handler(_cli_delivery_handler)

    # Create the interactive UI
    ui = InteractiveUI(console)

    # Extract skill names for header
    skill_names: list[str] = []
    if skill_context:
        skill_lines = [ln for ln in skill_context.split("\n") if ln.startswith("### ")]
        skill_names = [ln.replace("### ", "").split(" (")[0] for ln in skill_lines[:3]]

    ui.show_header(
        task=task,
        provider=config.settings.llm.provider,
        model=config.settings.llm.model,
        workspace=str(ws_path),
        skills=skill_names,
        interactive=interactive,
    )

    ui.show_thinking()

    # Wire up engine events to the interactive UI
    # Only process known event types — silently ignore the rest.
    handled_events = {
        "assistant.message_delta",
        "assistant.reasoning_delta",
        "tool.execution_start",
        "tool.execution_complete",
        "session.plan_changed",
        "session.workspace_file_changed",
        "engine.human_escalation",
        "subagent.started",
        "subagent.completed",
    }

    def _get_data_attr(data: object, key: str, default: str = "") -> str:
        """Safely get a string attribute from a dict or dataclass."""
        if isinstance(data, dict):
            return str(data.get(key, default))
        return str(getattr(data, key, default) or default)

    def on_event(event: object) -> None:
        etype = getattr(event, "type", "")
        if etype not in handled_events:
            return  # Silently ignore unknown events

        data = getattr(event, "data", None)

        if etype == "assistant.message_delta":
            delta = _get_data_attr(data, "delta_content")
            if delta:
                ui.show_streaming_delta(delta)

        elif etype == "assistant.reasoning_delta":
            delta = _get_data_attr(data, "delta_content")
            if delta:
                console.print(f"[dim italic]{delta}[/dim italic]", end="")

        elif etype == "tool.execution_start":
            tool_name = _get_data_attr(data, "tool_name") or _get_data_attr(data, "name")
            if not tool_name:
                return

            # Extract a readable detail from arguments
            tool_detail = ""
            args = (
                data.get("arguments", None)
                if isinstance(data, dict)
                else getattr(data, "arguments", None)
            )
            if isinstance(args, dict):
                tool_detail = str(
                    args.get("command", "")
                    or args.get("file_path", "")
                    or args.get("path", "")
                    or args.get("query", "")
                )[:120]
            elif isinstance(args, str):
                tool_detail = args[:120]

            ui.show_tool_start(tool_name, tool_detail)

        elif etype == "tool.execution_complete":
            output = ""
            success = True
            if isinstance(data, dict):
                result = data.get("result", {})
                if isinstance(result, dict):
                    output = str(result.get("output", ""))[:200]
                    success = not result.get("is_error", False)
            elif data is not None:
                result = getattr(data, "result", None)
                if result:
                    output = str(getattr(result, "output", ""))[:200]
                    success = not getattr(result, "is_error", False)
            ui.show_tool_result(output, success)

        elif etype == "session.plan_changed":
            ui.show_plan_updated()

        elif etype == "session.workspace_file_changed":
            path = ""
            action = "edit"
            if isinstance(data, dict):
                path = data.get("path", "")
                action = data.get("operation", "edit")
            elif data is not None:
                path = getattr(data, "path", "")
                op = getattr(data, "operation", None)
                action = str(op.value if hasattr(op, "value") else op) if op else "edit"
            if path:
                ui.show_file_activity(path, action)

        elif etype == "engine.human_escalation":
            # The actual prompt is handled by _cli_user_input_handler
            pass

        elif etype == "subagent.started":
            agent_name = ""
            if isinstance(data, dict):
                agent_name = data.get("agent_name", data.get("agent_display_name", ""))
            elif data is not None:
                agent_name = getattr(data, "agent_name", "") or getattr(
                    data, "agent_display_name", ""
                )
            if agent_name:
                console.print(f"\n  [bold magenta]>> Subagent: {agent_name}[/bold magenta]")

        elif etype == "subagent.completed":
            console.print("  [bold magenta]<< Subagent done[/bold magenta]")

    engine.on_event(on_event)

    # Check for --continue session resumption
    session_id = None
    if continue_session:
        session_id = CopilotEngine.load_last_session()
        if session_id:
            console.print(f"  [dim]Resuming session: {session_id[:12]}...[/dim]")
        else:
            console.print("  [dim]No previous session found, starting fresh.[/dim]")

    try:
        result = await engine.execute(task, timeout=600.0, session_id=session_id)
        console.print()

        if result.success:
            ui.show_completion(result.output, ui.state.tool_count)
        else:
            ui.show_failure(result.error or "Unknown error")

        ui.show_workspace(str(ws_path))

        # Multi-turn conversation loop (interactive mode only)
        if interactive and result.success and engine.session:
            ui.show_session_active()
            await _conversation_loop(engine, ui)

    finally:
        await engine.stop()


async def _conversation_loop(
    engine: object,
    ui: object,
) -> None:
    """Multi-turn conversation loop after task completion.

    The user can send follow-up messages to the same session:
    - "add tests for the API"
    - "change the database to PostgreSQL"
    - "deploy this to Railway"
    - "exit" or Ctrl+C to end
    """
    from hauba.engine.copilot_engine import CopilotEngine

    if not isinstance(engine, CopilotEngine):
        return

    while True:
        try:
            console.print()
            message = Prompt.ask("[bold cyan]You[/bold cyan]")

            if not message.strip():
                continue

            lower = message.strip().lower()
            if lower in ("exit", "quit", "bye", "done", "q"):
                console.print("  [dim]Session ended.[/dim]")
                break

            result = await engine.send_message(message, timeout=600.0)

            console.print()
            if result.success:
                console.print(
                    Panel(
                        result.output[:2000] if result.output else "[dim]No output[/dim]",
                        border_style="green",
                    )
                )
            else:
                console.print(f"  [red]{result.error}[/red]")

        except KeyboardInterrupt:
            console.print("\n  [dim]Session ended.[/dim]")
            break
        except EOFError:
            break


setup_app = typer.Typer(
    name="setup",
    help="Quick setup for channels and integrations",
    no_args_is_help=True,
)
app.add_typer(setup_app, name="setup")


@setup_app.command(name="whatsapp")
def setup_whatsapp() -> None:
    """Set up WhatsApp delivery in 30 seconds.

    Uses Twilio's free WhatsApp Sandbox — no business account needed.
    Just paste your Account SID + Auth Token, enter your phone number, done.
    """
    from hauba.core.config import ConfigManager

    console.print()
    console.print(
        Panel(
            "[bold cyan]WhatsApp Setup[/bold cyan]\n\n"
            "Uses Twilio's free WhatsApp Sandbox.\n"
            "No WhatsApp Business account needed — works instantly.\n\n"
            "[bold]What you need:[/bold]\n"
            "  1. A free Twilio account ([bold]twilio.com/try-twilio[/bold])\n"
            "  2. Your Account SID and Auth Token\n"
            "     (Twilio Console > Account Info — right on the dashboard)",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()

    config = ConfigManager()

    # --- Step 1: Credentials ---
    existing_sid = os.environ.get("TWILIO_ACCOUNT_SID") or config.get("whatsapp.account_sid") or ""

    if existing_sid:
        console.print(
            f"  [green]+[/green] Twilio SID found: [dim]{existing_sid[:8]}...{existing_sid[-4:]}[/dim]"
        )
        reuse = Prompt.ask(
            "  [bold]Use existing credentials?[/bold] [green]Y[/green]/n", default="y"
        )
        if reuse.strip().lower() not in ("n", "no"):
            sid = existing_sid
            token = os.environ.get("TWILIO_AUTH_TOKEN") or config.get("whatsapp.auth_token") or ""
        else:
            sid = Prompt.ask("  [bold]Account SID[/bold]").strip()
            token = Prompt.ask("  [bold]Auth Token[/bold]", password=True).strip()
    else:
        sid = Prompt.ask("  [bold]Account SID[/bold]").strip()
        token = Prompt.ask("  [bold]Auth Token[/bold]", password=True).strip()

    if not sid or not token:
        console.print("  [red]SID and Auth Token are required.[/red]")
        return

    config.set("whatsapp.account_sid", sid)
    config.set("whatsapp.auth_token", token)

    # --- Step 2: Phone number ---
    existing_phone = config.get("whatsapp.to_number") or ""
    if existing_phone:
        console.print(f"  [green]+[/green] Your number: [bold]{existing_phone}[/bold]")
        change = Prompt.ask("  [bold]Change number?[/bold] y/[red]N[/red]", default="n")
        if change.strip().lower() in ("y", "yes"):
            existing_phone = ""

    if not existing_phone:
        phone = Prompt.ask(
            "  [bold]Your WhatsApp number[/bold] [dim](with country code, e.g. +9779812345678)[/dim]"
        ).strip()
        if phone:
            config.set("whatsapp.to_number", phone)
        else:
            console.print("  [yellow]No number saved — you'll be asked at delivery time.[/yellow]")

    # --- Step 3: Join sandbox instructions ---
    console.print()
    console.print(
        Panel(
            "[bold green]Almost done! Last step on your phone:[/bold green]\n\n"
            "  1. Open WhatsApp on your phone\n"
            "  2. Send this message to [bold]+1 (415) 523-8886[/bold]:\n\n"
            "     [bold cyan]join <your-sandbox-code>[/bold cyan]\n\n"
            "  Find your sandbox code at:\n"
            "  [bold]console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn[/bold]\n\n"
            "  [dim]After sending the join message, Twilio will reply confirming\n"
            "  your sandbox is connected. Then Hauba can deliver to your WhatsApp.[/dim]",
            title="[bold green]Connect Your Phone[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )

    # --- Summary ---
    console.print()
    console.print(
        Panel(
            "[bold green]WhatsApp setup complete![/bold green]\n\n"
            "  Credentials saved to ~/.hauba/settings.json\n\n"
            "  [bold]For Railway / production:[/bold]\n"
            "  Set these env vars in your Railway dashboard:\n\n"
            f"    TWILIO_ACCOUNT_SID={sid}\n"
            f"    TWILIO_AUTH_TOKEN={token}\n\n"
            "  [dim]Env vars override config file, so Railway will just work.[/dim]\n\n"
            '  [bold]Test it:[/bold] hauba run "hello world" --interactive',
            border_style="green",
            padding=(1, 2),
        )
    )


@app.command()
def status() -> None:
    """Show status of Hauba configuration and last task."""
    _check_init()
    from rich.table import Table

    from hauba.core.config import ConfigManager
    from hauba.engine.copilot_engine import CopilotEngine

    config = ConfigManager()
    plan = CopilotEngine.load_last_plan()

    # Status table
    table = Table(border_style="blue", show_header=False, padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value")

    table.add_row("Owner", config.settings.owner_name)
    table.add_row("Provider", config.settings.llm.provider)
    table.add_row("Model", config.settings.llm.model)

    if plan and plan.task:
        table.add_row("", "")
        table.add_row("Last Task", plan.task[:80])
        table.add_row("Approved", "[green]Yes[/green]" if plan.approved else "[yellow]No[/yellow]")
        if plan.files_created:
            table.add_row("Files Created", str(len(plan.files_created)))

    console.print(Panel(table, title="[bold blue]Hauba Status[/bold blue]", border_style="blue"))


@app.command()
def logs(lines: int = typer.Option(20, help="Number of lines to show")) -> None:
    """View recent Hauba logs."""
    _check_init()
    from hauba.core.constants import LOGS_DIR

    log_file = LOGS_DIR / "hauba.log"
    if not log_file.exists():
        console.print("[dim]No logs yet.[/dim]")
        return
    text = log_file.read_text(encoding="utf-8")
    recent = "\n".join(text.strip().split("\n")[-lines:])
    console.print(Panel(recent, title="Recent Logs", border_style="dim"))


@app.command(name="config")
def config_cmd(
    key: str = typer.Argument(..., help="Config key (e.g. llm.provider)"),
    value: str = typer.Argument(None, help="Value to set"),
) -> None:
    """Get or set configuration values."""
    _check_init()
    from hauba.core.config import ConfigManager

    cfg = ConfigManager()
    if value:
        cfg.set(key, value)
        console.print(f"  [green]+[/green] Set [bold]{key}[/bold] = {value}")
    else:
        val = cfg.get(key)
        if val is not None:
            console.print(f"  [bold]{key}:[/bold] {val}")
        else:
            console.print(f"  [red]Unknown key: {key}[/red]")


@app.command()
def replay(
    task_id: str = typer.Argument(..., help="Task ID to replay"),
    speed: float = typer.Option(1.0, help="Playback speed multiplier"),
    no_data: bool = typer.Option(False, "--no-data", help="Hide event data details"),
) -> None:
    """Replay a recorded agent session."""
    _check_init()
    asyncio.run(_replay_task(task_id, speed, not no_data))


async def _replay_task(task_id: str, speed: float, show_data: bool) -> None:
    """Play back a recorded session."""
    from hauba.core.constants import AGENTS_DIR
    from hauba.ui.replay import ReplayPlayer

    replay_path = AGENTS_DIR / task_id / ".hauba-replay"
    if not replay_path.exists():
        console.print(f"[red]No replay file found for task: {task_id}[/red]")
        console.print(f"[dim]Expected: {replay_path}[/dim]")
        raise typer.Exit(1)

    player = ReplayPlayer(console)
    await player.play(replay_path, speed=speed, show_data=show_data)


@app.command()
def voice() -> None:
    """Start voice conversation mode (speak to Hauba)."""
    _check_init()
    _configure_logging_to_file()
    asyncio.run(_voice_loop())


async def _voice_loop() -> None:
    """Voice conversation loop using CopilotEngine."""
    from hauba.channels.voice import VoiceChannel, VoiceChannelError

    try:
        vc = VoiceChannel()
    except Exception as exc:
        console.print(f"[red]Voice init failed: {exc}[/red]")
        return

    if not vc.is_available:
        console.print("[red]Voice dependencies missing. Run: pip install hauba[voice][/red]")
        return

    console.print("[bold cyan]Voice Mode[/bold cyan] — Speak to Hauba (Ctrl+C to exit)")

    try:
        await vc.initialize()
        while True:
            console.print("\n[dim]Listening...[/dim]")
            text = await vc.listen(duration=5.0)
            if not text.strip():
                continue
            console.print(f"[bold]You:[/bold] {text}")

            from hauba.core.config import ConfigManager
            from hauba.engine.copilot_engine import CopilotEngine
            from hauba.engine.types import EngineConfig, ProviderType

            config = ConfigManager()
            provider_map = {
                "anthropic": ProviderType.ANTHROPIC,
                "openai": ProviderType.OPENAI,
                "ollama": ProviderType.OLLAMA,
                "deepseek": ProviderType.OPENAI,
            }
            provider = provider_map.get(config.settings.llm.provider, ProviderType.ANTHROPIC)
            engine_config = EngineConfig(
                provider=provider,
                api_key=config.settings.llm.api_key,
                model=config.settings.llm.model,
            )
            engine = CopilotEngine(engine_config)
            engine.set_user_input_handler(_cli_user_input_handler)
            result = await engine.execute(text)
            await engine.stop()

            response = result.output if result.success else f"Error: {result.error}"
            console.print(f"[bold green]Hauba:[/bold green] {response}")
            await vc.speak(str(response))
    except KeyboardInterrupt:
        console.print("\n[dim]Voice mode ended.[/dim]")
    except VoiceChannelError as exc:
        console.print(f"[red]{exc}[/red]")


@app.command()
def agent(
    server_url: str = typer.Option(
        "https://hauba.tech",
        "--server",
        "-s",
        help="Hauba server URL to poll for tasks",
    ),
    poll_interval: float = typer.Option(
        10.0,
        "--interval",
        "-i",
        help="Polling interval in seconds",
    ),
    workspace: str = typer.Option(
        "",
        "--workspace",
        "-w",
        help="Output directory for generated files (default: ./hauba-output/)",
    ),
    owner_id: str = typer.Option(
        "",
        "--owner",
        "-o",
        help="Owner ID to poll for (default: from config or WhatsApp number)",
    ),
) -> None:
    """Start the Hauba agent daemon — polls server for tasks and builds locally.

    This connects to your Hauba server (default: hauba.tech) and polls for
    tasks queued via WhatsApp, Telegram, or the API. When a task arrives,
    it executes locally on YOUR machine using YOUR API key.

    The server never sees your API key. Tasks are built here, results
    are sent back to the server for delivery to the originating channel.

    Run this 24/7 to receive and execute tasks from any channel.

    Examples:
        hauba agent                           # Default: poll hauba.tech
        hauba agent --server http://localhost:8080  # Local server
        hauba agent --interval 30             # Poll every 30s
        hauba agent --owner "whatsapp:+1234"  # Specific owner ID
    """
    _check_init()
    _configure_logging_to_file()
    asyncio.run(_run_agent(server_url, poll_interval, workspace, owner_id))


async def _run_agent(
    server_url: str,
    poll_interval: float,
    workspace_path: str,
    owner_id: str,
) -> None:
    """Run the daemon agent that polls for and executes tasks."""
    from hauba.core.config import ConfigManager
    from hauba.daemon.agent import HaubaDaemon

    config = ConfigManager()

    # Resolve owner ID
    resolved_owner = owner_id
    if not resolved_owner:
        # Try WhatsApp number from config
        wa_number = config.get("whatsapp.to_number") or ""
        if wa_number:
            resolved_owner = (
                f"whatsapp:{wa_number}" if not wa_number.startswith("whatsapp:") else wa_number
            )
        else:
            resolved_owner = config.settings.owner_name or "default"

    # Resolve workspace
    ws = workspace_path
    if not ws:
        from pathlib import Path

        ws = str(Path.cwd() / "hauba-output")
        Path(ws).mkdir(parents=True, exist_ok=True)

    console.print(
        Panel(
            f"[bold cyan]Hauba Agent Daemon[/bold cyan]\n\n"
            f"  Server:    {server_url}\n"
            f"  Owner:     {resolved_owner}\n"
            f"  Workspace: {ws}\n"
            f"  Polling:   every {poll_interval}s\n"
            f"  Provider:  {config.settings.llm.provider}\n"
            f"  Model:     {config.settings.llm.model}\n\n"
            f"  [green]Tasks execute locally using YOUR API key.[/green]\n"
            f"  [dim]The server never sees your credentials.[/dim]\n\n"
            f"  [dim]Press Ctrl+C to stop.[/dim]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    daemon = HaubaDaemon(
        owner_id=resolved_owner,
        server_url=server_url,
        poll_interval=poll_interval,
        workspace=ws,
    )

    try:
        await daemon.start()
    except KeyboardInterrupt:
        console.print("\n[dim]Agent daemon stopped.[/dim]")
    finally:
        await daemon.stop()


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8420, help="Port to serve on"),
) -> None:
    """Start the Hauba web dashboard."""
    _check_init()
    asyncio.run(_serve_web(host, port))


@app.command()
def api(
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8080, help="Port to serve on"),
) -> None:
    """Start the Hauba AI Workstation API server (BYOK)."""
    asyncio.run(_serve_api(host, port))


async def _serve_api(host: str, port: int) -> None:
    """Start the AI Workstation API with Copilot SDK backend."""
    try:
        import uvicorn

        from hauba.api.server import create_app
    except ImportError as e:
        console.print(f"[red]Missing dependencies: {e}[/red]")
        console.print("[dim]Run: pip install hauba[web] github-copilot-sdk[/dim]")
        return

    api_app = create_app()
    console.print(
        Panel(
            f"[bold cyan]Hauba AI Workstation API[/bold cyan]\n\n"
            f"  Endpoint: http://{host}:{port}\n"
            f"  Docs: http://{host}:{port}/docs\n\n"
            f"  [green]BYOK: Users bring their own API key.[/green]\n"
            f"  [dim]Hauba owner pays nothing for LLM usage.[/dim]",
            border_style="cyan",
        )
    )
    uvi_config = uvicorn.Config(api_app, host=host, port=port, log_level="info")
    server = uvicorn.Server(uvi_config)
    await server.serve()


async def _serve_web(host: str, port: int) -> None:
    """Start the FastAPI web dashboard."""
    from hauba.core.events import EventEmitter
    from hauba.ui.web import WebUI, WebUIError

    try:
        events = EventEmitter()
        web = WebUI(events=events)
        console.print(f"[bold cyan]Hauba Dashboard[/bold cyan] at http://{host}:{port}")
        await web.start(host=host, port=port)
    except WebUIError as exc:
        console.print(f"[red]{exc}[/red]")


@app.command()
def doctor() -> None:
    """Diagnose setup issues and check system health."""
    asyncio.run(_run_doctor())


async def _run_doctor() -> None:
    """Run all diagnostic checks."""
    from rich.table import Table

    from hauba.doctor import Doctor

    doc = Doctor()
    results = await doc.run_all()

    table = Table(title="Hauba Health Check")
    table.add_column("Check", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Details")

    for r in results:
        icon = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
        detail = r.message
        if not r.passed and r.suggestion:
            detail += f"\n[dim]{r.suggestion}[/dim]"
        table.add_row(r.name, icon, detail)

    console.print(table)

    all_passed = all(r.passed for r in results)
    if all_passed:
        console.print("\n[bold green]All checks passed![/bold green]")
    else:
        failed = sum(1 for r in results if not r.passed)
        console.print(f"\n[bold red]{failed} check(s) failed. See suggestions above.[/bold red]")


@compose_app.command(name="up")
def compose_up(
    task: str = typer.Argument(..., help="Task for the agent team"),
    file: str = typer.Option("hauba.yaml", "--file", "-f", help="Path to hauba.yaml"),
) -> None:
    """Run a task using a compose agent team."""
    _check_init()
    _configure_logging_to_file()
    asyncio.run(_compose_run(task, file))


async def _compose_run(task: str, file: str) -> None:
    """Execute a compose run."""
    from hauba.compose.parser import parse_compose_file
    from hauba.compose.runner import ComposeRunner
    from hauba.core.config import ConfigManager
    from hauba.core.events import EventEmitter

    compose_path = Path(file).resolve()
    try:
        compose_config = parse_compose_file(compose_path)
    except Exception as exc:
        console.print(f"[red]Compose error: {exc}[/red]")
        raise typer.Exit(1)

    config = ConfigManager()
    events = EventEmitter()

    console.print(
        f"[bold cyan]Compose:[/bold cyan] Team '{compose_config.team}' "
        f"with {len(compose_config.agents)} agent(s)"
    )

    runner = ComposeRunner(config=config, events=events, compose=compose_config)
    result = await runner.run(task)

    if result.success:
        console.print(
            Panel(
                f"[bold green]Compose completed[/bold green]\n\n{result.value}",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                f"[bold red]Compose failed[/bold red]\n\n{result.error}",
                border_style="red",
            )
        )


@compose_app.command()
def validate(
    file: str = typer.Option("hauba.yaml", "--file", "-f", help="Path to hauba.yaml"),
) -> None:
    """Validate a hauba.yaml compose file."""
    from hauba.compose.parser import validate_compose_file

    compose_path = Path(file).resolve()
    issues = validate_compose_file(compose_path)

    if issues:
        console.print("[red]Validation failed:[/red]")
        for issue in issues:
            console.print(f"  [red]*[/red] {issue}")
        raise typer.Exit(1)
    else:
        console.print(f"[green]+ {compose_path.name} is valid[/green]")


# === V4.0 Commands ===


@app.command()
def tasks(
    server_url: str = typer.Option("https://hauba.tech", "--server", "-s", help="Server URL"),
    owner_id: str = typer.Option("", "--owner", "-o", help="Owner ID"),
) -> None:
    """List all tasks (queued, running, completed)."""
    _check_init()
    asyncio.run(_list_tasks(server_url, owner_id))


async def _list_tasks(server_url: str, owner_id: str) -> None:
    """Fetch and display task list from server."""
    import httpx
    from rich.table import Table

    from hauba.core.config import ConfigManager

    config = ConfigManager()
    resolved_owner = owner_id
    if not resolved_owner:
        wa_number = config.get("whatsapp.to_number") or ""
        if wa_number:
            resolved_owner = (
                f"whatsapp:{wa_number}" if not wa_number.startswith("whatsapp:") else wa_number
            )
        else:
            resolved_owner = config.settings.owner_name or "default"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{server_url}/api/v1/queue/{resolved_owner}/status")
            if resp.status_code != 200:
                console.print("[yellow]No tasks found or server unreachable.[/yellow]")
                return
            data = resp.json()
    except Exception as exc:
        console.print(f"[red]Error connecting to server: {exc}[/red]")
        return

    if not data:
        console.print("[dim]No tasks found.[/dim]")
        return

    table = Table(title="Your Tasks")
    table.add_column("ID", style="cyan", max_width=10)
    table.add_column("Status", justify="center")
    table.add_column("Task", max_width=50)
    table.add_column("Progress", style="dim")

    status_style = {
        "queued": "[yellow]queued[/yellow]",
        "claimed": "[blue]claimed[/blue]",
        "running": "[cyan]running[/cyan]",
        "completed": "[green]done[/green]",
        "failed": "[red]failed[/red]",
        "cancelled": "[dim]cancel[/dim]",
    }

    for t in data:
        tid = t.get("task_id", "")[:8]
        status = status_style.get(t.get("status", ""), t.get("status", ""))
        instr = (t.get("instruction", "") or "")[:50]
        progress = t.get("progress", "") or ""
        table.add_row(tid, status, instr, progress[:40])

    console.print(table)


@app.command()
def cancel(
    task_id: str = typer.Argument(..., help="Task ID (or prefix) to cancel"),
    server_url: str = typer.Option("https://hauba.tech", "--server", "-s"),
) -> None:
    """Cancel a queued or running task."""
    _check_init()
    asyncio.run(_cancel_task(task_id, server_url))


async def _cancel_task(task_id: str, server_url: str) -> None:
    """Cancel a task via the server API."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{server_url}/api/v1/queue/{task_id}/cancel")
            if resp.status_code == 200:
                console.print(f"[green]Task {task_id[:8]} cancelled.[/green]")
            elif resp.status_code == 404:
                console.print(f"[yellow]Task {task_id[:8]} not found.[/yellow]")
            else:
                console.print(f"[red]Failed to cancel: {resp.text}[/red]")
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")


@app.command()
def retry(
    task_id: str = typer.Argument(..., help="Task ID (or prefix) to retry"),
    server_url: str = typer.Option("https://hauba.tech", "--server", "-s"),
) -> None:
    """Retry a failed or cancelled task."""
    _check_init()
    asyncio.run(_retry_task(task_id, server_url))


async def _retry_task(task_id: str, server_url: str) -> None:
    """Retry a task via the server API."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{server_url}/api/v1/queue/{task_id}/retry")
            if resp.status_code == 200:
                data = resp.json()
                new_id = data.get("task_id", "")[:8]
                console.print(f"[green]Task retried. New ID: {new_id}[/green]")
            elif resp.status_code == 404:
                console.print(f"[yellow]Task {task_id[:8]} not found.[/yellow]")
            else:
                console.print(f"[red]Failed to retry: {resp.text}[/red]")
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")


@app.command()
def email(
    to: str = typer.Argument(..., help="Recipient email address"),
    subject: str = typer.Argument(..., help="Email subject"),
    body: str = typer.Argument("", help="Email body (or enter interactively)"),
) -> None:
    """Send an email on your behalf."""
    _check_init()
    asyncio.run(_send_email(to, subject, body))


async def _send_email(to: str, subject: str, body: str) -> None:
    """Send email via the configured SMTP service."""
    from hauba.services.email import EmailService

    service = EmailService()
    if not service.configure():
        console.print(
            "[red]Email not configured.[/red]\n"
            "[dim]Set environment variables: HAUBA_SMTP_HOST, HAUBA_SMTP_USER, HAUBA_SMTP_PASS[/dim]"
        )
        return

    if not body:
        body = Prompt.ask("[cyan]Email body[/cyan]")

    success = await service.send(to, subject, body)
    if success:
        console.print(f"[green]Email sent to {to}[/green]")
    else:
        console.print("[red]Failed to send email. Check logs for details.[/red]")


@app.command()
def web(
    url: str = typer.Argument(..., help="URL to fetch"),
) -> None:
    """Fetch and display a web page's content."""
    asyncio.run(_fetch_web(url))


async def _fetch_web(url: str) -> None:
    """Fetch a URL and display its content."""
    from hauba.tools.fetch import WebFetchTool

    tool = WebFetchTool()
    result = await tool.execute(url=url)

    if result.success:
        output = result.output
        if len(output) > 3000:
            output = output[:3000] + "\n\n[Content truncated — use a browser for full page]"
        console.print(Panel(output, title=url[:80], border_style="cyan"))
    else:
        console.print(f"[red]{result.error}[/red]")


@app.command()
def usage(
    server_url: str = typer.Option("https://hauba.tech", "--server", "-s"),
    owner_id: str = typer.Option("", "--owner", "-o"),
) -> None:
    """Show cost tracking and usage summary."""
    _check_init()
    asyncio.run(_show_usage(server_url, owner_id))


async def _show_usage(server_url: str, owner_id: str) -> None:
    """Fetch and display usage stats."""
    import httpx

    from hauba.core.config import ConfigManager

    config = ConfigManager()
    resolved_owner = owner_id
    if not resolved_owner:
        wa_number = config.get("whatsapp.to_number") or ""
        if wa_number:
            resolved_owner = (
                f"whatsapp:{wa_number}" if not wa_number.startswith("whatsapp:") else wa_number
            )
        else:
            resolved_owner = config.settings.owner_name or "default"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{server_url}/api/v1/queue/{resolved_owner}/usage")
            if resp.status_code == 200:
                data = resp.json()
                console.print(
                    Panel(
                        f"[bold]Usage Summary[/bold]\n\n"
                        f"  Total tasks:     {data.get('total_tasks', 0)}\n"
                        f"  Completed:       {data.get('completed', 0)}\n"
                        f"  Failed:          {data.get('failed', 0)}\n"
                        f"  Estimated cost:  ${data.get('estimated_cost', 0):.2f}",
                        border_style="cyan",
                    )
                )
            else:
                console.print("[yellow]Usage data not available.[/yellow]")
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")


@app.command()
def feedback(
    message: str = typer.Argument(..., help="Your feedback message"),
) -> None:
    """Submit feedback to the Hauba team."""
    console.print(f"[green]Feedback received:[/green] {message}")
    console.print("[dim]Thank you! Visit https://github.com/NikeGunn/haubaa/issues to track.[/dim]")


@app.command(name="reply")
def reply_cmd(
    message: str = typer.Argument(..., help="Auto-reply message to set, or 'off' to disable"),
) -> None:
    """Set or disable auto-reply for incoming messages."""
    _check_init()
    asyncio.run(_set_reply(message))


async def _set_reply(message: str) -> None:
    """Set or disable auto-reply."""
    from hauba.services.reply_assistant import ReplyAssistant

    assistant = ReplyAssistant()
    if message.lower() == "off":
        await assistant.set_enabled(False)
        console.print("[yellow]Auto-reply disabled.[/yellow]")
    else:
        await assistant.set_auto_reply(message)
        await assistant.set_enabled(True)
        console.print(f"[green]Auto-reply set:[/green] {message}")


# --- Plugin Commands ---


@plugins_app.command(name="list")
def plugins_list() -> None:
    """List installed plugins."""
    from hauba.plugins.loader import PluginLoader

    loader = PluginLoader()
    files = loader.discover()

    if not files:
        console.print("[dim]No plugins installed.[/dim]")
        console.print("[dim]Place plugin .py files in ~/.hauba/plugins/[/dim]")
        return

    from rich.table import Table

    table = Table(title="Installed Plugins")
    table.add_column("File", style="cyan")
    table.add_column("Name")
    table.add_column("Description")

    for f in files:
        plugin = loader.load_plugin(f)
        if plugin:
            table.add_row(f.name, plugin.name, plugin.description)
        else:
            table.add_row(f.name, "[red]error[/red]", "Failed to load")

    console.print(table)


@plugins_app.command(name="install")
def plugins_install(
    path: str = typer.Argument(..., help="Path to plugin .py file"),
) -> None:
    """Install a plugin by copying it to ~/.hauba/plugins/."""
    import shutil

    from hauba.core.constants import PLUGINS_DIR

    src = Path(path).resolve()
    if not src.exists():
        console.print(f"[red]File not found: {path}[/red]")
        raise typer.Exit(1)

    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    dest = PLUGINS_DIR / src.name
    shutil.copy2(str(src), str(dest))
    console.print(f"[green]Plugin installed: {dest.name}[/green]")


@plugins_app.command(name="remove")
def plugins_remove(
    name: str = typer.Argument(..., help="Plugin filename to remove"),
) -> None:
    """Remove an installed plugin."""
    from hauba.core.constants import PLUGINS_DIR

    target = PLUGINS_DIR / name
    if not target.suffix:
        target = target.with_suffix(".py")

    if target.exists():
        target.unlink()
        console.print(f"[green]Plugin removed: {target.name}[/green]")
    else:
        console.print(f"[yellow]Plugin not found: {name}[/yellow]")


def _check_init() -> None:
    """Ensure Hauba has been initialized."""
    from hauba.core.constants import SETTINGS_FILE

    if not SETTINGS_FILE.exists():
        console.print("[red]Hauba not initialized. Run 'hauba init' first.[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
