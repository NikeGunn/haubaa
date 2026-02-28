"""Hauba CLI — AI Workstation entry point.

All execution flows through CopilotEngine (GitHub Copilot SDK).
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

# Force UTF-8 on Windows to avoid cp1252 UnicodeEncodeError with Rich
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

console = Console()


@app.command()
def init() -> None:
    """Initialize Hauba — creates ~/.hauba/ and runs setup wizard."""
    from hauba.core.setup import ensure_hauba_dirs

    console.print(
        Panel(
            "[bold cyan]Hauba — AI Workstation[/bold cyan]\n"
            "Build software, edit video, process data, and more.",
            title="Welcome",
            border_style="cyan",
        )
    )

    ensure_hauba_dirs()
    console.print("[green]+[/green] Created ~/.hauba/ directory structure")

    from hauba.core.config import ConfigManager

    config = ConfigManager()

    name = Prompt.ask("[bold]Your name[/bold]", default="Developer")
    config.settings.owner_name = name

    provider = Prompt.ask(
        "[bold]LLM provider[/bold]",
        choices=["anthropic", "openai", "ollama", "deepseek"],
        default="anthropic",
    )
    config.settings.llm.provider = provider

    if provider == "ollama":
        config.settings.llm.base_url = "http://localhost:11434"
        model = Prompt.ask("[bold]Ollama model[/bold]", default="llama3.1")
        config.settings.llm.model = model
        config.settings.llm.api_key = "ollama"
    else:
        api_key = Prompt.ask(f"[bold]{provider} API key[/bold]", password=True)
        api_key = api_key.strip()
        if provider == "openai" and api_key.startswith("sk-"):
            for prefix in ("sk-proj-", "sk-"):
                if api_key.startswith(prefix):
                    second = api_key.find(prefix, len(prefix))
                    if second > 0:
                        api_key = api_key[:second]
                        console.print(
                            "[yellow]Note: Detected duplicate paste — trimmed to single key.[/yellow]"
                        )
                    break
        config.settings.llm.api_key = api_key

        if provider == "anthropic":
            model = Prompt.ask("[bold]Model[/bold]", default="claude-sonnet-4-5-20250929")
        elif provider == "openai":
            model = Prompt.ask("[bold]Model[/bold]", default="gpt-4o")
        else:
            model = Prompt.ask("[bold]Model[/bold]", default="deepseek-chat")
        config.settings.llm.model = model

    config.save()
    console.print("[green]+[/green] Configuration saved to ~/.hauba/settings.json")

    # Test Copilot SDK availability
    console.print("[dim]Checking Copilot SDK...[/dim]")
    try:
        from hauba.engine.copilot_engine import CopilotEngine

        engine = CopilotEngine.__new__(CopilotEngine)
        if hasattr(engine, "is_available") and CopilotEngine.__dict__.get("is_available"):
            # Check if import works
            try:
                import copilot  # noqa: F401

                console.print("[green]+[/green] Copilot SDK is installed")
            except ImportError:
                console.print(
                    "[yellow]![/yellow] Copilot SDK not found. Install: pip install github-copilot-sdk"
                )
        else:
            console.print("[green]+[/green] Engine check complete")
    except Exception:
        console.print("[green]+[/green] Configuration saved")

    console.print()
    console.print(
        Panel(
            f"[bold green]Hauba is ready![/bold green]\n\n"
            f"  Owner: {name}\n"
            f"  Provider: {provider}\n"
            f"  Model: {config.settings.llm.model}\n\n"
            f'  Run: [bold]hauba run "build me a hello world app"[/bold]',
            border_style="green",
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
) -> None:
    """Run a task with the Hauba AI Workstation.

    Powered by the Copilot SDK engine (production-tested, BYOK).
    """
    _check_init()
    asyncio.run(_run_task(task, workspace, continue_session))


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


async def _run_task(task: str, workspace_path: str = "", continue_session: bool = False) -> None:
    """Execute a task using the CopilotEngine."""
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

    # Show streaming events with rich formatting
    def on_event(event: object) -> None:
        etype = getattr(event, "type", "")
        data = getattr(event, "data", None)

        if etype == "assistant.message_delta":
            if isinstance(data, dict) and data.get("delta_content"):
                console.print(data["delta_content"], end="")
            elif data is not None and hasattr(data, "delta_content"):
                delta = data.delta_content  # type: ignore[union-attr]
                if delta:
                    console.print(delta, end="")
        elif etype == "tool.execution_start":
            tool_name = ""
            tool_input = ""
            if isinstance(data, dict):
                tool_name = data.get("name", str(data))
                tool_input = str(data.get("input", ""))[:120]
            else:
                tool_name = str(data) if data else ""
            if tool_name:
                console.print(
                    f"\n  [bold yellow]> {tool_name}[/bold yellow] [dim]{tool_input}[/dim]"
                )
        elif etype == "tool.execution_complete":
            if isinstance(data, dict) and data.get("output"):
                output = str(data["output"])[:200]
                for line in output.split("\n")[:3]:
                    if line.strip():
                        console.print(f"  [dim]  {line}[/dim]")

    engine.on_event(on_event)

    skill_info = ""
    if skill_context:
        skill_lines = [ln for ln in skill_context.split("\n") if ln.startswith("### ")]
        if skill_lines:
            names = [ln.replace("### ", "").split(" (")[0] for ln in skill_lines[:3]]
            skill_info = f"\n  Skills: {', '.join(names)}"

    console.print(
        Panel(
            f"[bold cyan]Hauba AI Workstation[/bold cyan] (Copilot SDK)\n"
            f"  Provider: {config.settings.llm.provider} | Model: {config.settings.llm.model}\n"
            f"  Workspace: {ws_path}{skill_info}",
            border_style="cyan",
        )
    )

    # Check for --continue session resumption
    session_id = None
    if continue_session:
        session_id = CopilotEngine.load_last_session()
        if session_id:
            console.print(f"[dim]Resuming session: {session_id[:12]}...[/dim]")
        else:
            console.print("[dim]No previous session found, starting fresh.[/dim]")

    try:
        result = await engine.execute(task, timeout=600.0, session_id=session_id)
        console.print()
        if result.success:
            console.print(
                Panel(
                    f"[bold green]Task completed[/bold green]\n\n{result.output[:2000]}",
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel(
                    f"[bold red]Task failed[/bold red]\n\n{result.error}",
                    border_style="red",
                )
            )
        console.print(f"[dim]  Workspace: {ws_path}[/dim]")
    finally:
        await engine.stop()


@app.command()
def status() -> None:
    """Show status of Hauba configuration."""
    _check_init()
    from hauba.core.config import ConfigManager

    config = ConfigManager()
    console.print(
        Panel(
            f"[bold]Owner:[/bold] {config.settings.owner_name}\n"
            f"[bold]Provider:[/bold] {config.settings.llm.provider}\n"
            f"[bold]Model:[/bold] {config.settings.llm.model}",
            title="Hauba Status",
            border_style="blue",
        )
    )


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
        console.print(f"[green]+ Set {key} = {value}[/green]")
    else:
        val = cfg.get(key)
        if val is not None:
            console.print(f"[bold]{key}:[/bold] {val}")
        else:
            console.print(f"[red]Unknown key: {key}[/red]")


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


def _check_init() -> None:
    """Ensure Hauba has been initialized."""
    from hauba.core.constants import SETTINGS_FILE

    if not SETTINGS_FILE.exists():
        console.print("[red]Hauba not initialized. Run 'hauba init' first.[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
