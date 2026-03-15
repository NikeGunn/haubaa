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
import webbrowser
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
    """Initialize Hauba — full setup wizard. No technical knowledge needed."""
    from hauba.core.config import ConfigManager
    from hauba.core.setup import ensure_hauba_dirs
    from hauba.ui.interactive import select_menu

    console.print()
    console.print(
        Panel(
            "[bold cyan]Hauba — Your AI Engineering Team[/bold cyan]\n\n"
            "Build software, edit video, process data, train ML models,\n"
            "generate documents, scrape websites, and automate anything.\n\n"
            "[dim]I'll guide you through setup. Takes under 2 minutes.[/dim]",
            title="[bold]Welcome[/bold]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    ensure_hauba_dirs()
    config = ConfigManager()

    # ── Name ──────────────────────────────────────────────────────────────
    console.print()
    name = Prompt.ask(
        "  [bold]Your name[/bold]",
        default=config.settings.owner_name or "Developer",
    )
    config.settings.owner_name = name

    # ── Step 1: LLM Provider ─────────────────────────────────────────────
    console.print()
    console.print("  [bold cyan]Step 1/3 — AI Provider[/bold cyan]")
    console.print(
        "  [dim]Hauba needs an AI provider to think and build. I'll help you pick one.[/dim]\n"
    )

    _ollama_available = _check_ollama_running()
    if _ollama_available:
        console.print("  [green]+[/green] Ollama detected locally (free, no API key needed)\n")

    providers = [
        "Anthropic (Claude Sonnet)" + ("" if _ollama_available else " [recommended]"),
        "OpenAI (GPT-4o)",
        "Ollama — 100% local, FREE" + (" [running]" if _ollama_available else " [needs install]"),
        "DeepSeek — cheap alternative",
        "I don't have a key — help me get one",
    ]
    provider_keys = ["anthropic", "openai", "ollama", "deepseek", "help"]
    provider_descs = [
        "Best for coding. ~$3/mo average.",
        "GPT-4o. ~$5/mo average.",
        "Runs on your machine. Zero cost, full privacy.",
        "Very cost-effective. ~$0.50/mo average.",
        "I'll open the right website for you.",
    ]
    idx = select_menu(console, "Which AI provider?", providers, provider_descs)
    if idx < 0:
        idx = 0
    provider = provider_keys[idx]

    if provider == "help":
        console.print()
        console.print(
            Panel(
                "[bold]Easiest options:[/bold]\n\n"
                "  [green]1. Free (Ollama)[/green] — runs on your computer, no account needed\n"
                "     Best if you have: 8 GB+ RAM\n\n"
                "  [yellow]2. Anthropic Claude[/yellow] — best quality, $5 free credit to start\n"
                "     Best if you want: the smartest results\n\n"
                "  [blue]3. DeepSeek[/blue] — very cheap, almost as good\n"
                "     Best if you want: low cost",
                border_style="cyan",
                padding=(1, 2),
            )
        )
        choice_opts = [
            "Ollama (free, local)",
            "Anthropic Claude ($5 free credit)",
            "DeepSeek (cheap)",
        ]
        choice_keys = ["ollama", "anthropic", "deepseek"]
        choice_descs = [
            "No account needed, runs on your PC",
            "Open browser → get key in 2 min",
            "Open browser → get key in 2 min",
        ]
        cidx = select_menu(console, "Pick what works for you:", choice_opts, choice_descs)
        if cidx < 0:
            cidx = 1
        provider = choice_keys[cidx]

        if provider in ("anthropic", "deepseek"):
            urls = {
                "anthropic": "https://console.anthropic.com/settings/keys",
                "deepseek": "https://platform.deepseek.com/api_keys",
            }
            console.print(f"\n  [dim]Opening {urls[provider]} in your browser...[/dim]")
            try:
                webbrowser.open(urls[provider])
            except Exception:
                console.print(f"  [yellow]Visit:[/yellow] {urls[provider]}")
            console.print("  [dim]Sign up → get API key → come back and paste it below.[/dim]\n")

    if provider == "ollama":
        config.settings.llm.provider = "ollama"
        config.settings.llm.base_url = "http://localhost:11434"
        config.settings.llm.api_key = "ollama"

        if not _ollama_available:
            console.print()
            console.print(
                Panel(
                    "[bold yellow]Ollama needs to be installed.[/bold yellow]\n\n"
                    "  [bold]Option A:[/bold] Auto-install (opens browser for Windows/Mac)\n"
                    "  [bold]Option B:[/bold] Skip — visit ollama.com later",
                    border_style="yellow",
                    padding=(1, 2),
                )
            )
            install_choice = Prompt.ask(
                "  [bold]Install Ollama now?[/bold] [green]Y[/green]/n", default="y"
            )
            if install_choice.strip().lower() not in ("n", "no"):
                _install_ollama(console)
            else:
                try:
                    webbrowser.open("https://ollama.com/download")
                except Exception:
                    pass
                console.print("  [dim]Visit ollama.com/download — then re-run hauba init.[/dim]")

        ollama_models = [
            "llama3.1",
            "codellama",
            "qwen2.5-coder",
            "deepseek-coder-v2",
        ]
        ollama_descs = [
            "General purpose, fast (4.7 GB)",
            "Specialized for code (3.8 GB)",
            "Excellent coder (4.7 GB)",
            "Best coding model (8.9 GB)",
        ]
        midx = select_menu(console, "Choose Ollama model:", ollama_models, ollama_descs)
        if midx < 0:
            midx = 0
        config.settings.llm.model = ollama_models[midx]
        _pull_ollama_model(console, config.settings.llm.model)

    else:
        provider_names = {
            "anthropic": "Anthropic",
            "openai": "OpenAI",
            "deepseek": "DeepSeek",
        }
        provider_urls = {
            "anthropic": "https://console.anthropic.com/settings/keys",
            "openai": "https://platform.openai.com/api-keys",
            "deepseek": "https://platform.deepseek.com/api_keys",
        }
        config.settings.llm.provider = provider

        existing_key = config.get("llm.api_key") or ""
        if existing_key:
            console.print(
                f"\n  [green]+[/green] Existing {provider_names.get(provider, provider)} key found."
            )
            reuse = Prompt.ask("  [bold]Use existing key?[/bold] [green]Y[/green]/n", default="y")
            if reuse.strip().lower() in ("n", "no"):
                existing_key = ""

        if not existing_key:
            console.print()
            url = provider_urls.get(provider, "")
            if url:
                open_b = Prompt.ask(
                    f"  [bold]Open "
                    f"{provider_names.get(provider, provider)}"
                    " in browser to get an API key?[/bold] [green]Y[/green]/n",
                    default="y",
                )
                if open_b.strip().lower() not in ("n", "no"):
                    try:
                        webbrowser.open(url)
                        console.print(
                            "  [dim]Browser opened — sign in, create a key, paste below.[/dim]\n"
                        )
                    except Exception:
                        console.print(f"  [yellow]Visit:[/yellow] {url}\n")

            api_key = Prompt.ask(
                f"  [bold]Paste your {provider_names.get(provider, provider)} API key[/bold]",
                password=True,
            )
            api_key = api_key.strip()

            if provider == "openai" and api_key.startswith("sk-"):
                for prefix in ("sk-proj-", "sk-"):
                    if api_key.startswith(prefix):
                        second = api_key.find(prefix, len(prefix))
                        if second > 0:
                            api_key = api_key[:second]
                            console.print("  [yellow]Note: Trimmed duplicate paste.[/yellow]")
                        break

            config.settings.llm.api_key = api_key

        model_map: dict[str, tuple[list[str], list[str]]] = {
            "anthropic": (
                [
                    "claude-sonnet-4-5-20250929",
                    "claude-opus-4-5-20250514",
                    "claude-haiku-4-5-20251001",
                ],
                [
                    "Best balance of speed + quality [recommended]",
                    "Most capable, slower",
                    "Fastest, budget-friendly",
                ],
            ),
            "openai": (
                ["gpt-4o", "gpt-4o-mini", "o3"],
                ["Best balance [recommended]", "Fast and cheap", "Advanced reasoning"],
            ),
            "deepseek": (
                ["deepseek-chat", "deepseek-coder"],
                ["General purpose [recommended]", "Code specialized"],
            ),
        }
        models, model_descs = model_map.get(provider, (["default"], ["Default model"]))
        midx = select_menu(
            console,
            f"Choose {provider_names.get(provider, provider)} model:",
            models,
            model_descs,
        )
        if midx < 0:
            midx = 0
        config.settings.llm.model = models[midx]

        _test_and_show_llm_key(
            console, provider, config.settings.llm.api_key, config.settings.llm.model
        )

    config.save()
    console.print()
    console.print("  [green]+[/green] LLM config saved")

    # ── Step 2: WhatsApp (optional) ───────────────────────────────────────
    console.print()
    console.print("  [bold cyan]Step 2/3 — WhatsApp Notifications (optional)[/bold cyan]")
    console.print("  [dim]Receive task results on WhatsApp. Free via Twilio Sandbox.[/dim]\n")
    if Prompt.ask(
        "  [bold]Set up WhatsApp?[/bold] y/[red]N[/red]", default="n"
    ).strip().lower() in ("y", "yes"):
        setup_whatsapp()
        console.print()
        owner_wa = Prompt.ask(
            "  [bold]Your WhatsApp number[/bold] "
            "[dim](with country code, e.g. +9779812345678 — makes you the bot owner)[/dim]",
            default=config.get("whatsapp.owner_number") or "",
        ).strip()
        if owner_wa:
            config.set("whatsapp.owner_number", owner_wa)
            console.print(
                "  [green]+[/green] Owner number saved — you control the bot from WhatsApp."
            )
    else:
        console.print("  [dim]Skipped. Run: hauba setup whatsapp[/dim]")

    # ── Step 3: Email (optional) ──────────────────────────────────────────
    console.print()
    console.print("  [bold cyan]Step 3/3 — Email Delivery (optional)[/bold cyan]")
    console.print(
        "  [dim]Send emails from Hauba. Free via Brevo (300/day, no credit card).[/dim]\n"
    )
    if Prompt.ask("  [bold]Set up email?[/bold] y/[red]N[/red]", default="n").strip().lower() in (
        "y",
        "yes",
    ):
        setup_email()
    else:
        console.print("  [dim]Skipped. Run: hauba setup email[/dim]")

    config.save()

    # ── LLM Engine check ─────────────────────────────────────────────────
    console.print()
    console.print("  [dim]Checking AI Engine...[/dim]")
    try:
        import litellm  # noqa: F401

        console.print("  [green]+[/green] LiteLLM engine is installed")
    except ImportError:
        console.print("  [yellow]![/yellow] LiteLLM not found. Install: pip install litellm")
    except Exception:
        console.print("  [green]+[/green] Engine check complete")

    # ── Summary ───────────────────────────────────────────────────────────
    wa_num = config.get("whatsapp.to_number") or ""
    email_key = config.get("email.brevo_api_key") or ""
    console.print()
    console.print(
        Panel(
            f"[bold green]Hauba is ready, {name}![/bold green]\n\n"
            f"  AI Provider : {config.settings.llm.provider} / {config.settings.llm.model}\n"
            f"  WhatsApp    : {'✅ ' + wa_num if wa_num else '❌ not set up'}\n"
            f"  Email       : {'✅ ready' if email_key else '❌ not set up'}\n\n"
            "[bold]Start building:[/bold]\n\n"
            '  [green]hauba run[/green] "build me a SaaS dashboard with auth"\n'
            '  [green]hauba run[/green] "scrape top 100 products from Amazon"\n'
            '  [green]hauba run[/green] "train an image classifier on my dataset"\n\n'
            "[dim]Need help?  hauba doctor | hauba --help[/dim]",
            border_style="green",
            padding=(1, 2),
        )
    )


def _check_ollama_running() -> bool:
    """Return True if Ollama HTTP API responds on localhost:11434."""
    try:
        import urllib.request

        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


def _install_ollama(con: Console) -> None:
    """Attempt to install Ollama on the current platform."""
    import subprocess

    con.print("  [dim]Installing Ollama...[/dim]")
    try:
        if sys.platform == "win32":
            con.print("  [yellow]Windows:[/yellow] Opening ollama.com/download in browser...")
            webbrowser.open("https://ollama.com/download/windows")
            con.print("  [dim]Download and run the installer, then re-run hauba init.[/dim]")
        elif sys.platform == "darwin":
            con.print("  [yellow]Mac:[/yellow] Opening ollama.com/download in browser...")
            webbrowser.open("https://ollama.com/download/mac")
            con.print("  [dim]Download and run the .dmg, then re-run hauba init.[/dim]")
        else:
            result = subprocess.run(
                "curl -fsSL https://ollama.com/install.sh | sh",
                shell=True,
                timeout=120,
            )
            if result.returncode == 0:
                con.print("  [green]+[/green] Ollama installed!")
            else:
                con.print("  [yellow]Install failed. Visit ollama.com/download[/yellow]")
    except Exception as exc:
        con.print(f"  [yellow]Auto-install failed: {exc}. Visit ollama.com/download[/yellow]")


def _pull_ollama_model(con: Console, model: str) -> None:
    """Pull an Ollama model."""
    import subprocess

    con.print(f"  [dim]Pulling {model}...[/dim]")
    try:
        result = subprocess.run(
            ["ollama", "pull", model],
            timeout=600,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            con.print(f"  [green]+[/green] Model {model} ready")
        else:
            con.print(f"  [yellow]Pull failed. Run: ollama pull {model}[/yellow]")
    except FileNotFoundError:
        con.print(f"  [yellow]Ollama not in PATH. Run: ollama pull {model}[/yellow]")
    except Exception as exc:
        con.print(f"  [yellow]Pull error: {exc}. Run: ollama pull {model}[/yellow]")


def _test_and_show_llm_key(con: Console, provider: str, api_key: str, model: str) -> None:
    """Make a minimal API call to verify the key and print pass/fail."""
    if not api_key or api_key == "ollama":
        return

    con.print("  [dim]Testing API key...[/dim]")
    try:
        import httpx

        headers: dict[str, str] = {}
        url = ""
        payload: dict = {}

        if provider == "anthropic":
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            payload = {
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 5,
                "messages": [{"role": "user", "content": "hi"}],
            }
        elif provider == "openai":
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "gpt-4o-mini",
                "max_tokens": 5,
                "messages": [{"role": "user", "content": "hi"}],
            }
        elif provider == "deepseek":
            url = "https://api.deepseek.com/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "deepseek-chat",
                "max_tokens": 5,
                "messages": [{"role": "user", "content": "hi"}],
            }

        if url:
            r = httpx.post(url, json=payload, headers=headers, timeout=15)
            if r.status_code in (200, 201):
                con.print("  [green]+[/green] API key works!")
            elif r.status_code == 401:
                con.print(
                    "  [red]✗ API key rejected (401).[/red] Double-check and re-run hauba init."
                )
            elif r.status_code == 429:
                con.print("  [yellow]✓ Key valid (rate-limited on test — that's fine).[/yellow]")
            else:
                con.print(f"  [yellow]API returned {r.status_code} — key may still work.[/yellow]")
    except Exception:
        con.print("  [dim]Key test skipped (no network). Continuing.[/dim]")


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
    Uses resolve() for consistent priority: env var → config file → default.
    """
    from hauba.core.config import resolve

    sid = resolve("TWILIO_ACCOUNT_SID", "whatsapp.account_sid")
    token = resolve("TWILIO_AUTH_TOKEN", "whatsapp.auth_token")
    from_num = resolve("TWILIO_WHATSAPP_NUMBER", "whatsapp.from_number", "whatsapp:+14155238886")
    to_num = resolve("HAUBA_WHATSAPP_TO", "whatsapp.to_number")

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
    """Execute a task using AgentEngine (V4 — custom agent loop)."""
    from hauba.core.config import ConfigManager
    from hauba.engine.agent_engine import AgentEngine
    from hauba.engine.types import EngineConfig, ProviderType

    config = ConfigManager()

    provider_map = {
        "anthropic": ProviderType.ANTHROPIC,
        "openai": ProviderType.OPENAI,
        "ollama": ProviderType.OLLAMA,
        "deepseek": ProviderType.DEEPSEEK,
        "google": ProviderType.GOOGLE,
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

    engine = AgentEngine(engine_config, skill_context=skill_context)

    if not engine.is_available:
        console.print(
            Panel(
                "[bold red]LiteLLM not installed[/bold red]\n\n"
                "Hauba V4 requires LiteLLM for LLM API calls.\n\n"
                "  Install: [bold]pip install litellm[/bold]",
                title="Missing Dependency",
                border_style="red",
            )
        )
        raise typer.Exit(1)

    console.print(
        Panel(
            f"[bold cyan]Hauba AI Workstation[/bold cyan]\n\n"
            f"  Task:     {task[:80]}\n"
            f"  Provider: {config.settings.llm.provider}\n"
            f"  Model:    {config.settings.llm.model}\n"
            f"  Output:   {ws_path}\n"
            f"  Engine:   Custom Agent Loop (V4)\n"
            + (
                f"  Skills:   {', '.join(s for s in skill_context.split('### ')[1:3] if s)[:80]}\n"
                if skill_context
                else ""
            ),
            border_style="cyan",
            padding=(1, 2),
        )
    )

    console.print("  [dim]Starting Hauba agent (10 tools, auto-compaction)...[/dim]")

    try:
        if interactive:
            # Use streaming for real-time output
            async for event in engine.execute_streamed(task, timeout=600.0):
                if event.type == "task_started":
                    console.print("  [green]Agent started[/green]")
                elif event.type == "text_delta":
                    # Stream text as it arrives
                    text = event.data.get("text", "")
                    if text:
                        console.print(text, end="")
                elif event.type == "tool_start":
                    tool = event.data.get("tool", "")
                    inp = event.data.get("input", "")[:100]
                    console.print(f"\n  [dim]> {tool}: {inp}[/dim]")
                elif event.type == "tool_end":
                    tool = event.data.get("tool", "")
                    success = event.data.get("success", False)
                    status = "[green]OK[/green]" if success else "[red]FAIL[/red]"
                    console.print(f"  [dim]< {tool}: {status}[/dim]")
                elif event.type == "compacting":
                    console.print("  [dim]Compacting context...[/dim]")
                elif event.type == "task_completed":
                    output = event.data.get("output", "")
                    turns = event.data.get("turns", 0)
                    console.print()
                    if output:
                        console.print(
                            Panel(
                                output[:3000] if len(output) > 3000 else output,
                                title=f"[bold green]Task Complete ({turns} turns)[/bold green]",
                                border_style="green",
                                padding=(1, 2),
                            )
                        )
                    else:
                        console.print(
                            f"  [green]Task completed in {turns} turns (no output)[/green]"
                        )
                elif event.type == "timeout":
                    console.print("  [red]Task timed out[/red]")
                elif event.type == "error":
                    console.print(f"  [red]Error: {event.data.get('error', 'Unknown')}[/red]")
        else:
            # Non-interactive: run to completion
            result = await engine.execute(task, timeout=600.0)
            console.print()
            if result.success:
                console.print(
                    Panel(
                        result.output[:3000] if result.output else "[dim]No output[/dim]",
                        title="[bold green]Task Complete[/bold green]",
                        border_style="green",
                        padding=(1, 2),
                    )
                )
            else:
                console.print(f"  [red]{result.error}[/red]")

        console.print(f"\n  [dim]Output directory: {ws_path}[/dim]")

        # Delivery prompt
        if interactive:
            await _cli_delivery_handler("Task completed", "")

    finally:
        await engine.stop()


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

    from hauba.core.config import resolve

    # --- Step 1: Credentials ---
    existing_sid = resolve("TWILIO_ACCOUNT_SID", "whatsapp.account_sid")

    if existing_sid:
        console.print(
            f"  [green]+[/green] Twilio SID found: [dim]{existing_sid[:8]}...{existing_sid[-4:]}[/dim]"
        )
        reuse = Prompt.ask(
            "  [bold]Use existing credentials?[/bold] [green]Y[/green]/n", default="y"
        )
        if reuse.strip().lower() not in ("n", "no"):
            sid = existing_sid
            token = resolve("TWILIO_AUTH_TOKEN", "whatsapp.auth_token")
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


@setup_app.command(name="email")
def setup_email() -> None:
    """Set up email delivery (Brevo — free, 300 emails/day, no credit card).

    Brevo (formerly Sendinblue) gives you 300 free emails/day.
    Just paste your API key and verified sender email.
    """
    from hauba.core.config import ConfigManager

    console.print()
    console.print(
        Panel(
            "[bold cyan]Email Setup — Brevo (Free)[/bold cyan]\n\n"
            "Brevo gives you 300 emails/day for free. No credit card.\n\n"
            "[bold]What you need:[/bold]\n"
            "  1. A free Brevo account ([bold]brevo.com[/bold])\n"
            "  2. Your API key (Settings > SMTP & API > API Keys)\n"
            "  3. A verified sender email address",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()

    config = ConfigManager()

    # Check existing config
    existing_key = config.get("email.brevo_api_key") or ""
    if existing_key:
        console.print(
            f"  [green]+[/green] Brevo key found: [dim]{existing_key[:8]}...{existing_key[-4:]}[/dim]"
        )
        reuse = Prompt.ask("  [bold]Use existing key?[/bold] [green]Y[/green]/n", default="y")
        if reuse.strip().lower() in ("n", "no"):
            existing_key = ""

    if not existing_key:
        api_key = Prompt.ask("  [bold]Brevo API Key[/bold]", password=True).strip()
        if not api_key:
            console.print("  [red]API key is required.[/red]")
            return
        config.set("email.brevo_api_key", api_key)

    # Sender email
    existing_from = config.get("email.from_email") or ""
    if existing_from:
        console.print(f"  [green]+[/green] Sender email: [bold]{existing_from}[/bold]")
        change = Prompt.ask("  [bold]Change?[/bold] y/[red]N[/red]", default="n")
        if change.strip().lower() in ("y", "yes"):
            existing_from = ""

    if not existing_from:
        from_email = Prompt.ask(
            "  [bold]Sender email[/bold] [dim](must be verified in Brevo)[/dim]"
        ).strip()
        if from_email:
            config.set("email.from_email", from_email)

    # Sender name (optional)
    from_name = config.get("email.from_name") or "Hauba AI"
    new_name = Prompt.ask("  [bold]Sender name[/bold]", default=from_name).strip()
    if new_name and new_name != from_name:
        config.set("email.from_name", new_name)

    console.print()
    console.print(
        Panel(
            "[bold green]Email setup complete![/bold green]\n\n"
            "  Credentials saved to ~/.hauba/settings.json\n\n"
            "  [bold]Test it:[/bold]\n"
            "  Send /email on WhatsApp, or use in a task.\n\n"
            "  [dim]300 free emails/day with Brevo. No credit card needed.[/dim]",
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

    config = ConfigManager()

    # Status table
    table = Table(border_style="blue", show_header=False, padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value")

    table.add_row("Owner", config.settings.owner_name)
    table.add_row("Provider", config.settings.llm.provider)
    table.add_row("Model", config.settings.llm.model)
    table.add_row("Engine", "Custom Agent Loop (V4)")

    # Check for litellm
    try:
        import litellm  # noqa: F401

        table.add_row("LiteLLM", "[green]installed[/green]")
    except ImportError:
        table.add_row("LiteLLM", "[red]not installed[/red]")

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
            from hauba.engine.agent_engine import AgentEngine
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
            engine = AgentEngine(engine_config)
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
    install: bool = typer.Option(
        False,
        "--install",
        help="Install daemon to auto-start on login (no need to manually run hauba agent)",
    ),
    uninstall: bool = typer.Option(
        False,
        "--uninstall",
        help="Remove auto-start daemon registration",
    ),
) -> None:
    """Start the Hauba agent daemon — polls server for tasks and builds locally.

    This connects to your Hauba server (default: hauba.tech) and polls for
    tasks queued via WhatsApp, Telegram, or the API. When a task arrives,
    it executes locally on YOUR machine using YOUR API key.

    The server never sees your API key. Tasks are built here, results
    are sent back to the server for delivery to the originating channel.

    Auto-start:
        hauba agent --install               # Auto-start on login (set it and forget it)
        hauba agent --uninstall             # Remove auto-start

    Manual:
        hauba agent                           # Default: poll hauba.tech
        hauba agent --server http://localhost:8080  # Local server
        hauba agent --interval 30             # Poll every 30s
        hauba agent --owner "whatsapp:+1234"  # Specific owner ID
    """
    _check_init()

    if install:
        from hauba.daemon.autostart import install_autostart, is_installed

        if is_installed():
            console.print("  [yellow]Hauba agent is already installed as auto-start.[/yellow]")
            console.print("  [dim]Use --uninstall to remove it first.[/dim]")
            return

        console.print("  [cyan]Installing Hauba agent as auto-start service...[/cyan]")
        success = install_autostart(
            server_url=server_url,
            workspace=workspace,
            owner_id=owner_id,
            poll_interval=poll_interval,
        )
        if success:
            console.print(
                Panel(
                    "[bold green]Hauba Agent Auto-Start Installed[/bold green]\n\n"
                    "The daemon will start automatically when you log in.\n"
                    "No need to open a terminal or run `hauba agent`.\n\n"
                    "Just send tasks via WhatsApp — they'll execute on this machine.\n\n"
                    "  [dim]To remove: hauba agent --uninstall[/dim]",
                    border_style="green",
                    padding=(1, 2),
                )
            )
        else:
            console.print("  [red]Failed to install auto-start. Check logs.[/red]")
        return

    if uninstall:
        from hauba.daemon.autostart import uninstall_autostart

        console.print("  [cyan]Removing Hauba agent auto-start...[/cyan]")
        success = uninstall_autostart()
        if success:
            console.print("  [green]Auto-start removed.[/green]")
        else:
            console.print("  [red]Failed to remove auto-start.[/red]")
        return

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
