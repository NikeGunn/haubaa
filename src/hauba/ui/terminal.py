"""Rich-based terminal UI for Hauba — Claude Code style output."""

from __future__ import annotations

import sys

import structlog
from rich.console import Console
from rich.panel import Panel

from hauba.core.constants import (
    EVENT_AGENT_EXECUTING,
    EVENT_AGENT_REVIEWING,
    EVENT_AGENT_THINKING,
    EVENT_TASK_COMPLETED,
    EVENT_TASK_FAILED,
    EVENT_TOOL_CALLED,
    EVENT_TOOL_RESULT,
)
from hauba.core.events import EventEmitter
from hauba.core.types import Event, Result

logger = structlog.get_logger()

# Use ASCII-safe symbols on Windows legacy console (cp1252 etc.)
_USE_ASCII = sys.platform == "win32" and not sys.stdout.encoding.lower().startswith("utf")

# Symbol map: Unicode → ASCII fallback
_SYM_BULLET = "*" if _USE_ASCII else "\u25cf"  # ●
_SYM_CHECK = "+" if _USE_ASCII else "\u2713"  # ✓
_SYM_CROSS = "x" if _USE_ASCII else "\u2717"  # ✗
_SYM_THINK = "~" if _USE_ASCII else "\u25d0"  # ◐
_SYM_PLAY = ">" if _USE_ASCII else "\u25b6"  # ▶
_SYM_REVIEW = "~" if _USE_ASCII else "\u25d1"  # ◑
_SYM_BOLT = "!" if _USE_ASCII else "\u26a1"  # ⚡
_SYM_FILE = "#" if _USE_ASCII else "\U0001f4c4"  # 📄
_SYM_GIT = "@" if _USE_ASCII else "\U0001f500"  # 🔀


class TerminalUI:
    """Rich terminal UI for showing agent progress — Claude Code style."""

    def __init__(self, console: Console, events: EventEmitter) -> None:
        self._console = console
        self._events = events
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Subscribe to events for live display."""
        self._events.on(EVENT_AGENT_THINKING, self._on_thinking)
        self._events.on(EVENT_AGENT_EXECUTING, self._on_executing)
        self._events.on(EVENT_AGENT_REVIEWING, self._on_reviewing)
        self._events.on(EVENT_TOOL_CALLED, self._on_tool_called)
        self._events.on(EVENT_TOOL_RESULT, self._on_tool_result)
        self._events.on(EVENT_TASK_COMPLETED, self._on_completed)
        self._events.on(EVENT_TASK_FAILED, self._on_failed)

    async def show_task_start(self, task: str) -> None:
        """Display task start banner."""
        self._console.print()
        self._console.print(
            Panel(
                f"[bold]{task}[/bold]",
                title=f"[cyan]{_SYM_BULLET} Hauba[/cyan]",
                border_style="cyan",
                padding=(1, 2),
            )
        )
        self._console.print()

    async def show_task_result(self, result: Result) -> None:
        """Display final task result."""
        self._console.print()
        if result.success:
            self._console.print(
                Panel(
                    str(result.value or "Task completed successfully."),
                    title=f"[green]{_SYM_CHECK} Task Complete[/green]",
                    border_style="green",
                    padding=(1, 2),
                )
            )
        else:
            self._console.print(
                Panel(
                    str(result.error or "Task failed."),
                    title=f"[red]{_SYM_CROSS} Task Failed[/red]",
                    border_style="red",
                    padding=(1, 2),
                )
            )
        self._console.print()

    # --- Event Handlers ---

    async def _on_thinking(self, event: Event) -> None:
        self._console.print(f"[dim]  {_SYM_THINK} Thinking...[/dim]")

    async def _on_executing(self, event: Event) -> None:
        steps = event.data.get("steps", 0)
        self._console.print(f"[cyan]  {_SYM_PLAY} Executing plan ({steps} steps)[/cyan]")

    async def _on_reviewing(self, event: Event) -> None:
        self._console.print(f"[dim]  {_SYM_REVIEW} Reviewing results...[/dim]")

    async def _on_tool_called(self, event: Event) -> None:
        tool = event.data.get("tool", "?")
        step = event.data.get("step", "")
        args = event.data.get("args", {})

        # Claude Code style: show tool name and what it's doing
        if tool == "bash":
            cmd = args.get("command", "")
            self._console.print(
                f"  [bold yellow]{_SYM_BOLT} bash[/bold yellow] [dim]{cmd[:120]}[/dim]"
            )
        elif tool == "files":
            action = args.get("action", "")
            path = args.get("path", "")
            self._console.print(f"  [bold blue]{_SYM_FILE} {action}[/bold blue] [dim]{path}[/dim]")
        elif tool == "git":
            action = args.get("action", "")
            self._console.print(f"  [bold magenta]{_SYM_GIT} git {action}[/bold magenta]")
        else:
            self._console.print(f"  [bold]{tool}[/bold] {step[:80]}")

    async def _on_tool_result(self, event: Event) -> None:
        tool = event.data.get("tool", "?")
        success = event.data.get("success", False)
        preview = event.data.get("output_preview", "")

        if success:
            if preview.strip():
                # Show truncated output like Claude Code does
                lines = preview.strip().split("\n")
                for line in lines[:5]:
                    self._console.print(f"  [dim]  {line}[/dim]")
                if len(lines) > 5:
                    self._console.print(f"  [dim]  ... ({len(lines) - 5} more lines)[/dim]")
        else:
            self._console.print(f"  [red]  {_SYM_CROSS} {tool} failed[/red]")

    async def _on_completed(self, event: Event) -> None:
        pass  # Handled by show_task_result

    async def _on_failed(self, event: Event) -> None:
        error = event.data.get("error", "Unknown error")
        self._console.print(f"\n  [red]Error: {error}[/red]")
