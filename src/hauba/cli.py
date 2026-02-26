"""Hauba CLI — the main entry point."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

# Lazy: skill_app import kept here but skills/cli.py itself is now lightweight
from hauba.skills.cli import skill_app

app = typer.Typer(
    name="hauba",
    help="Your AI Engineering Team — In One Command",
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
            "[bold cyan]Hauba — AI Agent Operating System[/bold cyan]\n"
            "Setting up your AI engineering team...",
            title="Welcome",
            border_style="cyan",
        )
    )

    # Create directory structure
    ensure_hauba_dirs()
    console.print("[green]+[/green] Created ~/.hauba/ directory structure")

    # Interactive setup
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
        # Sanitize: if the key was pasted multiple times, extract just the first one
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

    # Test API connection
    console.print("[dim]Testing API connection...[/dim]")
    success, message = asyncio.run(_test_api(config))
    if success:
        console.print(f"[green]+[/green] {message}")
    else:
        console.print(f"[yellow]![/yellow] API test failed: {message}")
        console.print("[dim]  You can still proceed — check your API key if tasks fail.[/dim]")

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


async def _test_api(config: object) -> tuple[bool, str]:
    """Test the LLM API connection."""
    from hauba.brain.llm import LLMRouter

    try:
        llm = LLMRouter(config)  # type: ignore[arg-type]
        return await llm.test_connection()
    except Exception as exc:
        return False, str(exc)


@app.command()
def run(
    task: str = typer.Argument(..., help="Task description for your AI team"),
    workspace: str = typer.Option(
        "",
        "--workspace",
        "-w",
        help="Output directory for generated files (default: ./hauba-output/)",
    ),
    legacy: bool = typer.Option(
        False,
        "--legacy",
        help="Use legacy litellm-based Director agent instead of Copilot SDK engine",
    ),
) -> None:
    """Run a task with your AI engineering team.

    By default uses the Copilot SDK engine (production-tested, BYOK).
    Use --legacy for the original litellm-based Director agent.
    """
    _check_init()
    if legacy:
        asyncio.run(_run_task_legacy(task, workspace))
    else:
        asyncio.run(_run_task_engine(task, workspace))


async def _run_task_engine(task: str, workspace_path: str = "") -> None:
    """Execute a task using the Copilot SDK engine (new default)."""
    from hauba.core.config import ConfigManager
    from hauba.engine.copilot_engine import CopilotEngine
    from hauba.engine.types import EngineConfig, ProviderType

    config = ConfigManager()

    # Map hauba config to engine config
    provider_map = {
        "anthropic": ProviderType.ANTHROPIC,
        "openai": ProviderType.OPENAI,
        "ollama": ProviderType.OLLAMA,
        "deepseek": ProviderType.OPENAI,  # DeepSeek is OpenAI-compatible
    }
    provider = provider_map.get(config.settings.llm.provider, ProviderType.ANTHROPIC)

    # DeepSeek needs a custom base URL
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

    engine = CopilotEngine(engine_config)

    if not engine.is_available:
        console.print(
            "[yellow]Copilot CLI not found. Install with: npm install -g @github/copilot[/yellow]"
        )
        console.print("[dim]Falling back to legacy Director agent...[/dim]")
        await _run_task_legacy(task, workspace_path)
        return

    # Show streaming events
    def on_event(event):
        if event.type == "assistant.message_delta":
            data = event.data
            if hasattr(data, "delta_content") and data.delta_content:
                console.print(data.delta_content, end="")
        elif event.type == "tool.execution_start":
            console.print(f"\n[dim]  Tool: {event.data}[/dim]")

    engine.on_event(on_event)

    console.print(
        Panel(
            f"[bold cyan]Hauba AI Engineer[/bold cyan] (Copilot SDK Engine)\n"
            f"  Provider: {config.settings.llm.provider} | Model: {config.settings.llm.model}\n"
            f"  Workspace: {ws_path}",
            border_style="cyan",
        )
    )

    try:
        result = await engine.execute(task, timeout=600.0)
        console.print()  # newline after streaming
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


async def _run_task_legacy(task: str, workspace_path: str = "") -> None:
    """Execute a task using the legacy Director agent (litellm-based)."""
    from hauba.agents.director import DirectorAgent
    from hauba.core.config import ConfigManager
    from hauba.core.events import EventEmitter
    from hauba.ui.terminal import TerminalUI

    config = ConfigManager()
    events = EventEmitter()
    ui = TerminalUI(console, events)

    # Determine workspace directory
    workspace = Path(workspace_path).resolve() if workspace_path else Path.cwd() / "hauba-output"
    workspace.mkdir(parents=True, exist_ok=True)

    director = DirectorAgent(config=config, events=events, workspace=workspace)

    await ui.show_task_start(task)
    result = await director.run(task)
    await ui.show_task_result(result)

    # Show stats
    stats = director._llm.stats
    if stats["call_count"] > 0:
        console.print(
            f"[dim]  LLM calls: {stats['call_count']} | "
            f"Tokens: {stats['total_tokens']:,} | "
            f"Cost: ${stats['total_cost']:.4f}[/dim]"
        )
    console.print(f"[dim]  Workspace: {workspace}[/dim]")


@app.command()
def status() -> None:
    """Show status of running agents and recent tasks."""
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
    """Voice conversation loop: listen -> process -> speak."""
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

            from hauba.agents.director import DirectorAgent
            from hauba.core.config import ConfigManager
            from hauba.core.events import EventEmitter

            config = ConfigManager()
            events = EventEmitter()
            director = DirectorAgent(config=config, events=events)
            result = await director.run(text)

            response = result.value if result.success else f"Error: {result.error}"
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
    """Start the Hauba AI Engineer API server (BYOK)."""
    asyncio.run(_serve_api(host, port))


async def _serve_api(host: str, port: int) -> None:
    """Start the AI Engineer API with Copilot SDK backend."""
    try:
        import uvicorn

        from hauba.api.server import create_app
    except ImportError as e:
        console.print(f"[red]Missing dependencies: {e}[/red]")
        console.print("[dim]Run: pip install hauba[web] github-copilot-sdk[/dim]")
        return

    app = create_app()
    console.print(
        Panel(
            f"[bold cyan]Hauba AI Engineer API[/bold cyan]\n\n"
            f"  Endpoint: http://{host}:{port}\n"
            f"  Docs: http://{host}:{port}/docs\n\n"
            f"  [green]BYOK: Users bring their own API key.[/green]\n"
            f"  [dim]Hauba owner pays nothing for LLM usage.[/dim]",
            border_style="cyan",
        )
    )
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


@app.command(name="engine-run")
def engine_run(
    task: str = typer.Argument(..., help="Task description"),
    provider: str = typer.Option("anthropic", "--provider", "-p", help="LLM provider"),
    api_key: str = typer.Option("", "--api-key", "-k", help="API key (or use env var)"),
    model: str = typer.Option("", "--model", "-m", help="Model to use"),
    workspace: str = typer.Option("", "--workspace", "-w", help="Output directory"),
) -> None:
    """Run a task using the Copilot SDK engine (BYOK)."""
    asyncio.run(_engine_run(task, provider, api_key, model, workspace))


async def _engine_run(task: str, provider: str, api_key: str, model: str, workspace: str) -> None:
    """Execute a task using the Copilot Engine."""
    from hauba.engine.copilot_engine import CopilotEngine
    from hauba.engine.types import EngineConfig, ProviderType

    # Resolve API key from arg or environment
    if not api_key:
        env_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "azure": "AZURE_OPENAI_KEY",
        }
        env_var = env_map.get(provider, "")
        api_key = os.environ.get(env_var, "")
        if not api_key and provider != "ollama":
            console.print(f"[red]No API key provided. Use --api-key or set {env_var}[/red]")
            raise typer.Exit(1)

    # Default models per provider
    if not model:
        model_map = {
            "anthropic": "claude-sonnet-4-5-20250514",
            "openai": "gpt-4o",
            "azure": "gpt-4o",
            "ollama": "qwen2.5-coder:32b",
        }
        model = model_map.get(provider, "claude-sonnet-4-5-20250514")

    ws_path = Path(workspace).resolve() if workspace else Path.cwd() / "hauba-output"
    ws_path.mkdir(parents=True, exist_ok=True)

    config = EngineConfig(
        provider=ProviderType(provider),
        api_key=api_key,
        model=model,
        working_directory=str(ws_path),
    )

    engine = CopilotEngine(config)

    # Show events in real-time
    def on_event(event):
        if event.type == "assistant.message_delta":
            # Streaming text
            data = event.data
            if hasattr(data, "delta_content") and data.delta_content:
                console.print(data.delta_content, end="")
        elif event.type == "tool.execution_start":
            console.print(f"\n[dim]Tool: {event.data}[/dim]")
        elif event.type.startswith("engine."):
            console.print(f"[dim]{event.type}[/dim]")

    engine.on_event(on_event)

    console.print(
        Panel(
            f"[bold cyan]Hauba Engine[/bold cyan] (Copilot SDK)\n"
            f"  Provider: {provider} | Model: {model}\n"
            f"  Workspace: {ws_path}",
            border_style="cyan",
        )
    )

    try:
        result = await engine.execute(task, timeout=600.0)
        console.print()  # newline after streaming
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
    finally:
        await engine.stop()


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
    from hauba.ui.terminal import TerminalUI

    compose_path = Path(file).resolve()
    try:
        compose_config = parse_compose_file(compose_path)
    except Exception as exc:
        console.print(f"[red]Compose error: {exc}[/red]")
        raise typer.Exit(1)

    config = ConfigManager()
    events = EventEmitter()
    ui = TerminalUI(console, events)

    console.print(
        f"[bold cyan]Compose:[/bold cyan] Team '{compose_config.team}' "
        f"with {len(compose_config.agents)} agent(s)"
    )

    runner = ComposeRunner(config=config, events=events, compose=compose_config)
    await ui.show_task_start(task)
    result = await runner.run(task)
    await ui.show_task_result(result)


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
