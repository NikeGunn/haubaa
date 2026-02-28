"""Rich-based terminal UI for Hauba — Claude Code style output."""

from __future__ import annotations

import sys

import structlog
from rich.console import Console
from rich.panel import Panel

from hauba.core.constants import (
    EVENT_ENGINE_EXECUTING,
    EVENT_ENGINE_STARTED,
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

# Symbol map: Unicode -> ASCII fallback
_SYM_BULLET = "*" if _USE_ASCII else "\u25cf"  # ●
_SYM_CHECK = "+" if _USE_ASCII else "\u2713"  # ✓
_SYM_CROSS = "x" if _USE_ASCII else "\u2717"  # ✗
_SYM_THINK = "~" if _USE_ASCII else "\u25d0"  # ◐
_SYM_PLAY = ">" if _USE_ASCII else "\u25b6"  # ▶
_SYM_REVIEW = "~" if _USE_ASCII else "\u25d1"  # ◑
_SYM_BOLT = "!" if _USE_ASCII else "\u26a1"  # ⚡
_SYM_FILE = "#" if _USE_ASCII else "\U0001f4c4"  # 📄
_SYM_GIT = "@" if _USE_ASCII else "\U0001f500"  # 🔀
_SYM_EDIT = "~" if _USE_ASCII else "\u270e"  # ✎


class TerminalUI:
    """Rich terminal UI for showing agent progress — Claude Code style."""

    def __init__(self, console: Console, events: EventEmitter) -> None:
        self._console = console
        self._events = events
        self._tool_count = 0
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Subscribe to events for live display."""
        self._events.on(EVENT_ENGINE_STARTED, self._on_thinking)
        self._events.on(EVENT_ENGINE_EXECUTING, self._on_executing)
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
        self._tool_count = 0

    async def show_task_result(self, result: Result) -> None:
        """Display final task result."""
        self._console.print()
        if result.success:
            # Show the result value, truncated for readability
            value = str(result.value or "Task completed successfully.")
            # Truncate very long outputs
            if len(value) > 2000:
                value = value[:2000] + "\n\n... (output truncated)"
            self._console.print(
                Panel(
                    value,
                    title=f"[green]{_SYM_CHECK} Task Complete ({self._tool_count} tool calls)[/green]",
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
        self._console.print(f"[cyan]  {_SYM_PLAY} Executing ({steps} steps planned)[/cyan]")

    async def _on_tool_called(self, event: Event) -> None:
        tool = event.data.get("tool", "?")
        args = event.data.get("args", {})
        self._tool_count += 1

        if tool == "bash":
            cmd = args.get("command", "")
            self._console.print(
                f"  [bold yellow]{_SYM_BOLT} bash[/bold yellow] [dim]{cmd[:120]}[/dim]"
            )
        elif tool == "files":
            action = args.get("action", "")
            path = args.get("path", "")
            if action == "write":
                content = args.get("content", "")
                lines = content.count("\n") + 1 if content else 0
                self._console.print(
                    f"  [bold blue]{_SYM_FILE} write[/bold blue] [dim]{path} ({lines} lines)[/dim]"
                )
            elif action == "edit":
                self._console.print(f"  [bold blue]{_SYM_EDIT} edit[/bold blue] [dim]{path}[/dim]")
            elif action == "read":
                self._console.print(f"  [bold blue]{_SYM_FILE} read[/bold blue] [dim]{path}[/dim]")
            else:
                self._console.print(
                    f"  [bold blue]{_SYM_FILE} {action}[/bold blue] [dim]{path}[/dim]"
                )
        elif tool == "git":
            action = args.get("action", "")
            self._console.print(f"  [bold magenta]{_SYM_GIT} git {action}[/bold magenta]")
        else:
            self._console.print(f"  [bold]{tool}[/bold]")

    async def _on_tool_result(self, event: Event) -> None:
        tool = event.data.get("tool", "?")
        success = event.data.get("success", False)
        preview = event.data.get("output_preview", "")

        if success:
            if preview.strip():
                lines = preview.strip().split("\n")
                for line in lines[:3]:
                    self._console.print(f"  [dim]  {line[:120]}[/dim]")
                if len(lines) > 3:
                    self._console.print(f"  [dim]  ... ({len(lines) - 3} more lines)[/dim]")
        else:
            self._console.print(f"  [red]  {_SYM_CROSS} {tool} failed[/red]")

    async def _on_completed(self, event: Event) -> None:
        pass  # Handled by show_task_result

    async def _on_failed(self, event: Event) -> None:
        error = event.data.get("error", "Unknown error")
        self._console.print(f"\n  [red]Error: {error[:200]}[/red]")
