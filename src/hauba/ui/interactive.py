"""Interactive terminal UI for Hauba — Claude Code style experience.

Features:
- Live spinner showing thinking/planning/executing state
- Real-time file tracking panel (which files being created/modified)
- Arrow-key driven selection menus (plan review, delivery channel, etc.)
- Progress indicators for multi-step tasks
- Streaming output with syntax highlighting
- Beautiful panels with status indicators
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# ASCII-safe symbols for Windows legacy console
_USE_ASCII = sys.platform == "win32" and not sys.stdout.encoding.lower().startswith("utf")

# Symbol constants
SYM_THINK = "~" if _USE_ASCII else "\u25cf"
SYM_CHECK = "+" if _USE_ASCII else "\u2713"
SYM_CROSS = "x" if _USE_ASCII else "\u2717"
SYM_ARROW = ">" if _USE_ASCII else "\u25b6"
SYM_FILE = "#" if _USE_ASCII else "\u25a0"
SYM_TOOL = "!" if _USE_ASCII else "\u26a1"
SYM_PLAN = "=" if _USE_ASCII else "\u2261"
SYM_DELIVER = "@" if _USE_ASCII else "\u2709"
SYM_USER = "*" if _USE_ASCII else "\u25c6"
SYM_DOT = "." if _USE_ASCII else "\u2022"
SYM_UP = "^" if _USE_ASCII else "\u25b2"
SYM_DOWN = "v" if _USE_ASCII else "\u25bc"
SYM_SELECT = ">" if _USE_ASCII else "\u25b8"


class AgentPhase(str, Enum):
    """Current phase of the agent's work."""

    STARTING = "starting"
    THINKING = "thinking"
    PLANNING = "planning"
    WAITING_CONFIRM = "waiting_confirm"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    DELIVERING = "delivering"
    COMPLETED = "completed"
    FAILED = "failed"
    ASKING_USER = "asking_user"


@dataclass
class FileActivity:
    """Track a file being worked on."""

    path: str
    action: str  # "create", "edit", "read", "delete"
    lines: int = 0
    status: str = "active"  # "active", "done", "error"


@dataclass
class ToolActivity:
    """Track a tool invocation."""

    name: str
    detail: str = ""
    status: str = "running"  # "running", "done", "error"


@dataclass
class UIState:
    """Mutable state for the interactive UI."""

    phase: AgentPhase = AgentPhase.STARTING
    task: str = ""
    plan_text: str = ""
    streaming_output: str = ""
    files: list[FileActivity] = field(default_factory=list)
    tools: list[ToolActivity] = field(default_factory=list)
    current_tool: str = ""
    tool_count: int = 0
    thinking_text: str = ""
    error: str = ""
    model: str = ""
    provider: str = ""
    workspace: str = ""
    skills: list[str] = field(default_factory=list)


class InteractiveUI:
    """Claude Code style interactive terminal UI.

    Shows real-time progress with spinners, file tracking, tool invocations,
    and streaming output. Uses Rich Live for flicker-free updates.
    """

    def __init__(self, console: Console) -> None:
        self._console = console
        self.state = UIState()

    def show_header(
        self,
        task: str,
        provider: str,
        model: str,
        workspace: str,
        skills: list[str] | None = None,
        interactive: bool = True,
    ) -> None:
        """Display the task start header with config info."""
        self.state.task = task
        self.state.provider = provider
        self.state.model = model
        self.state.workspace = workspace
        self.state.skills = skills or []

        mode = "[bold green]interactive[/bold green]" if interactive else "[dim]auto[/dim]"

        # Build info lines
        info = Text()
        info.append("Provider: ", style="dim")
        info.append(provider, style="bold")
        info.append(" | Model: ", style="dim")
        info.append(model, style="bold cyan")
        info.append(" | Mode: ", style="dim")
        info.append_text(Text.from_markup(mode))

        workspace_line = Text()
        workspace_line.append("Workspace: ", style="dim")
        workspace_line.append(workspace, style="dim italic")

        skill_line = None
        if skills:
            skill_line = Text()
            skill_line.append("Skills: ", style="dim")
            skill_line.append(", ".join(skills), style="dim cyan")

        content_parts: list[Any] = [
            Text("Hauba AI Workstation", style="bold cyan"),
            Text(),
            info,
            workspace_line,
        ]
        if skill_line:
            content_parts.append(skill_line)

        self._console.print()
        self._console.print(
            Panel(
                Group(*content_parts),
                border_style="cyan",
                padding=(1, 2),
            )
        )
        self._console.print()

    def show_thinking(self, text: str = "Analyzing task...") -> None:
        """Show a thinking indicator."""
        self.state.phase = AgentPhase.THINKING
        self.state.thinking_text = text
        self._console.print(f"  [bold cyan]{SYM_THINK}[/bold cyan] [dim italic]{text}[/dim italic]")

    def show_planning(self) -> None:
        """Show that the agent is in planning phase."""
        self.state.phase = AgentPhase.PLANNING
        self._console.print(f"\n  [bold blue]{SYM_PLAN}[/bold blue] [bold]Planning...[/bold]")

    def show_plan(self, plan_text: str) -> None:
        """Display the agent's plan for review."""
        self.state.plan_text = plan_text
        self.state.phase = AgentPhase.WAITING_CONFIRM

        self._console.print()
        self._console.print(
            Panel(
                Markdown(plan_text) if plan_text else Text("[dim]No plan details available[/dim]"),
                title="[bold blue]Plan[/bold blue]",
                border_style="blue",
                padding=(1, 2),
            )
        )

    def show_executing(self) -> None:
        """Show that execution has started."""
        self.state.phase = AgentPhase.EXECUTING
        self._console.print(f"\n  [bold green]{SYM_ARROW}[/bold green] [bold]Executing...[/bold]")

    def show_tool_start(self, name: str, detail: str = "") -> None:
        """Show a tool invocation starting."""
        self.state.current_tool = name
        self.state.tool_count += 1
        activity = ToolActivity(name=name, detail=detail)
        self.state.tools.append(activity)

        # Format tool display based on type
        detail_short = detail[:120] if detail else ""

        if name in ("bash", "Bash"):
            self._console.print(
                f"  [bold yellow]{SYM_TOOL} bash[/bold yellow] [dim]{detail_short}[/dim]"
            )
        elif name in ("Read", "read"):
            self._console.print(
                f"  [bold blue]{SYM_FILE} read[/bold blue] [dim]{detail_short}[/dim]"
            )
        elif name in ("Write", "write"):
            self._console.print(
                f"  [bold green]{SYM_FILE} write[/bold green] [dim]{detail_short}[/dim]"
            )
        elif name in ("Edit", "edit"):
            self._console.print(
                f"  [bold magenta]{SYM_FILE} edit[/bold magenta] [dim]{detail_short}[/dim]"
            )
        elif name in ("Glob", "Grep", "glob", "grep"):
            self._console.print(
                f"  [bold cyan]{SYM_FILE} {name.lower()}[/bold cyan] [dim]{detail_short}[/dim]"
            )
        else:
            self._console.print(f"  [bold]{SYM_TOOL} {name}[/bold] [dim]{detail_short}[/dim]")

    def show_tool_result(self, output: str = "", success: bool = True) -> None:
        """Show tool result."""
        if self.state.tools:
            self.state.tools[-1].status = "done" if success else "error"

        if not success:
            self._console.print(f"    [red]{SYM_CROSS} failed[/red]")
        elif output.strip():
            lines = output.strip().split("\n")
            for line in lines[:3]:
                if line.strip():
                    self._console.print(f"    [dim]{line[:140]}[/dim]")
            if len(lines) > 3:
                self._console.print(f"    [dim]... ({len(lines) - 3} more lines)[/dim]")

    def show_file_activity(self, path: str, action: str, lines: int = 0) -> None:
        """Track and display file activity."""
        activity = FileActivity(path=path, action=action, lines=lines, status="done")
        self.state.files.append(activity)

    def show_streaming_delta(self, text: str) -> None:
        """Append streaming text from the agent."""
        self.state.streaming_output += text
        self._console.print(text, end="")

    def show_human_escalation(self, question: str) -> None:
        """Show that the agent is asking for human input."""
        self.state.phase = AgentPhase.ASKING_USER
        self._console.print()
        self._console.print(
            Panel(
                f"[bold yellow]{SYM_USER} Agent needs your input[/bold yellow]\n\n{question}",
                border_style="yellow",
                padding=(1, 2),
            )
        )

    def show_completion(self, output: str, tool_count: int = 0) -> None:
        """Show task completion with summary."""
        self.state.phase = AgentPhase.COMPLETED

        self._console.print()

        # File summary table
        if self.state.files:
            file_table = Table(
                title="Files",
                border_style="dim",
                show_header=True,
                header_style="bold dim",
                padding=(0, 1),
            )
            file_table.add_column("Action", style="dim", width=8)
            file_table.add_column("File", style="cyan")
            file_table.add_column("Lines", style="dim", justify="right", width=6)

            for f in self.state.files[-20:]:
                action_style = {
                    "create": "green",
                    "write": "green",
                    "edit": "yellow",
                    "read": "dim",
                    "delete": "red",
                }.get(f.action, "dim")
                file_table.add_row(
                    f"[{action_style}]{f.action}[/{action_style}]",
                    f.path,
                    str(f.lines) if f.lines else "",
                )

            self._console.print(file_table)
            self._console.print()

        # Result panel
        tc = tool_count or self.state.tool_count
        title = f"[bold green]{SYM_CHECK} Task Complete[/bold green]"
        if tc:
            title += f" [dim]({tc} tool calls)[/dim]"

        self._console.print(
            Panel(
                output[:2000] if output else "[dim]No output[/dim]",
                title=title,
                border_style="green",
                padding=(1, 2),
            )
        )

    def show_failure(self, error: str) -> None:
        """Show task failure."""
        self.state.phase = AgentPhase.FAILED
        self.state.error = error

        self._console.print()
        self._console.print(
            Panel(
                error[:2000],
                title=f"[bold red]{SYM_CROSS} Task Failed[/bold red]",
                border_style="red",
                padding=(1, 2),
            )
        )

    def show_workspace(self, path: str) -> None:
        """Show workspace path."""
        self._console.print(f"  [dim]Workspace: {path}[/dim]")

    def show_session_active(self) -> None:
        """Show that the session is active for follow-ups."""
        self._console.print()
        self._console.print(
            Rule(
                "[dim]Session active — type a follow-up or 'exit' to finish[/dim]",
                style="dim",
            )
        )

    def show_plan_updated(self) -> None:
        """Show that the plan was updated."""
        self._console.print(f"  [bold cyan]{SYM_PLAN}[/bold cyan] [dim]Plan updated[/dim]")


def select_menu(
    console: Console,
    title: str,
    options: list[str],
    descriptions: list[str] | None = None,
) -> int:
    """Display a keyboard-navigable selection menu with arrow keys.

    Uses arrow keys (up/down) + Enter to select. Falls back to numbered
    input if keyboard reading fails (e.g., piped input, CI).

    Also supports: j/k for vim-style navigation, q/Escape to cancel.

    Args:
        console: Rich Console instance.
        title: Menu title.
        options: List of option labels.
        descriptions: Optional descriptions for each option.

    Returns:
        Selected index (0-based), or -1 if cancelled.
    """
    try:
        return _arrow_key_menu(console, title, options, descriptions)
    except Exception:
        return _fallback_numbered_menu(console, title, options, descriptions)


def _arrow_key_menu(
    console: Console,
    title: str,
    options: list[str],
    descriptions: list[str] | None,
) -> int:
    """Arrow-key driven menu with live highlighting."""
    from hauba.ui.keyboard import read_key

    selected = 0
    n = len(options)

    def _render() -> str:
        """Render the menu at current selection."""
        lines: list[str] = []
        lines.append(f"  [bold]{title}[/bold]")
        lines.append(f"  [dim]{SYM_UP}/{SYM_DOWN} navigate  Enter select  q cancel[/dim]")
        lines.append("")
        for i, opt in enumerate(options):
            desc = ""
            if descriptions and i < len(descriptions):
                desc = f" [dim]— {descriptions[i]}[/dim]"
            if i == selected:
                lines.append(f"    [bold cyan]{SYM_SELECT} {opt}[/bold cyan]{desc}")
            else:
                lines.append(f"      [dim]{opt}[/dim]{desc}")
        return "\n".join(lines)

    # Initial render
    console.print()
    output = _render()
    console.print(output)

    while True:
        key = read_key()

        if key == "up":
            selected = (selected - 1) % n
        elif key == "down":
            selected = (selected + 1) % n
        elif key == "enter" or key == "space":
            # Clear and show final selection
            console.print(f"\n  [green]{SYM_CHECK}[/green] [bold]{options[selected]}[/bold]")
            return selected
        elif key in ("escape", "quit"):
            console.print("\n  [dim]Cancelled[/dim]")
            return -1
        else:
            continue

        # Re-render: move cursor up to overwrite previous menu
        # Use ANSI escape to move up N+3 lines (title + hint + blank + options)
        move_up = n + 3
        console.file.write(f"\033[{move_up}A\033[J")
        console.file.flush()
        output = _render()
        console.print(output)


def _fallback_numbered_menu(
    console: Console,
    title: str,
    options: list[str],
    descriptions: list[str] | None,
) -> int:
    """Fallback numbered menu when keyboard input isn't available."""
    console.print()
    console.print(f"  [bold]{title}[/bold]")
    console.print()

    for i, opt in enumerate(options):
        num = f"[bold cyan]{i + 1}[/bold cyan]"
        desc = ""
        if descriptions and i < len(descriptions):
            desc = f" [dim]— {descriptions[i]}[/dim]"
        console.print(f"    {num}. {opt}{desc}")

    console.print()

    from rich.prompt import Prompt

    answer = Prompt.ask(f"  [bold]Select[/bold] [dim](1-{len(options)}, or 'q' to cancel)[/dim]")

    if answer.lower() in ("q", "quit", "cancel", "skip"):
        return -1

    try:
        idx = int(answer) - 1
        if 0 <= idx < len(options):
            return idx
    except ValueError:
        pass

    console.print("  [red]Invalid selection[/red]")
    return -1


def confirm_prompt(
    console: Console,
    question: str,
    default: bool = True,
) -> bool:
    """Display a styled confirmation prompt.

    Accepts: yes/y/ok/proceed/start/go/sure (True)
             no/n/cancel/stop/abort (False)
    """
    default_hint = "[green]Y[/green]/n" if default else "y/[red]N[/red]"

    console.print()
    from rich.prompt import Prompt

    answer = Prompt.ask(
        f"  [bold]{question}[/bold] [{default_hint}]",
        default="y" if default else "n",
    )

    positive = {"y", "yes", "ok", "proceed", "start", "go", "sure", "yep", "yeah", "do it"}
    negative = {"n", "no", "cancel", "stop", "abort", "nah", "nope"}

    lower = answer.strip().lower()
    if lower in positive:
        return True
    if lower in negative:
        return False
    return default


def show_delivery_menu(console: Console) -> str | None:
    """Show delivery channel selection menu.

    Returns:
        Channel name ("whatsapp", "telegram", "discord") or None to skip.
    """
    idx = select_menu(
        console,
        f"{SYM_DELIVER} Deliver results via:",
        ["WhatsApp", "Telegram", "Discord", "Skip"],
        [
            "Send via Twilio WhatsApp API",
            "Send via Telegram Bot",
            "Send to Discord channel",
            "Don't deliver, just show here",
        ],
    )

    channel_map = {0: "whatsapp", 1: "telegram", 2: "discord"}
    return channel_map.get(idx)
