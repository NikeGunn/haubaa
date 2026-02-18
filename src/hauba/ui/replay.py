"""Replay player — reads .hauba-replay file and displays with Rich."""

from __future__ import annotations

import asyncio
from pathlib import Path

import structlog
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from hauba.core.replay import ReplayRecorder
from hauba.core.types import ReplayEntry
from hauba.exceptions import ReplayError

logger = structlog.get_logger()

# Color mapping for event topic prefixes
TOPIC_COLORS: dict[str, str] = {
    "task": "cyan",
    "agent": "green",
    "llm": "yellow",
    "tool": "blue",
    "browser": "magenta",
    "screen": "red",
    "replay": "dim",
    "ledger": "bright_cyan",
    "milestone": "bright_green",
    "worker": "bright_blue",
    "cross": "bright_yellow",
    "quality": "bright_magenta",
    "search": "bright_white",
}


class ReplayPlayer:
    """Plays back recorded events with Rich formatting and speed control.

    Usage::

        player = ReplayPlayer(console)
        await player.play(Path("~/.hauba/agents/task-xxx/.hauba-replay"), speed=2.0)
    """

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    async def play(
        self,
        path: Path,
        speed: float = 1.0,
        show_data: bool = True,
    ) -> int:
        """Play replay file. Returns number of entries played.

        Args:
            path: Path to .hauba-replay file
            speed: Playback speed multiplier (2.0 = twice as fast)
            show_data: Whether to show event data details
        """
        if not path.exists():
            raise ReplayError(f"Replay file not found: {path}")

        entries = ReplayRecorder.load(path)
        if not entries:
            self.console.print("[dim]No replay entries found.[/dim]")
            return 0

        self.console.print(
            Panel(
                f"[bold]Replay: {path.parent.name}[/bold]\n"
                f"Entries: {len(entries)} | Speed: {speed}x",
                title="Hauba Replay",
                border_style="cyan",
            )
        )

        played = 0
        prev_ts = None
        for entry in entries:
            # Calculate delay between events
            if prev_ts is not None and speed > 0:
                delta = (entry.timestamp - prev_ts).total_seconds()
                delay = max(0, delta / speed)
                # Cap delay at 2 seconds to avoid long waits
                delay = min(delay, 2.0)
                if delay > 0.01:
                    await asyncio.sleep(delay)

            self._render_entry(entry, show_data)
            prev_ts = entry.timestamp
            played += 1

        self.console.print(
            Panel(
                f"[bold green]Replay complete[/bold green] — {played} events",
                border_style="green",
            )
        )
        return played

    def _render_entry(self, entry: ReplayEntry, show_data: bool) -> None:
        """Render a single replay entry to the console."""
        prefix = entry.topic.split(".")[0] if "." in entry.topic else entry.topic
        color = TOPIC_COLORS.get(prefix, "white")

        ts = entry.timestamp.strftime("%H:%M:%S.%f")[:-3]
        topic_text = Text(entry.topic, style=f"bold {color}")

        line = Text()
        line.append(f"[{ts}] ", style="dim")
        line.append_text(topic_text)

        if entry.source:
            line.append(f" ({entry.source})", style="dim")

        self.console.print(line)

        if show_data and entry.data:
            # Show data as indented key=value pairs
            for key, value in entry.data.items():
                val_str = str(value)
                if len(val_str) > 100:
                    val_str = val_str[:100] + "..."
                self.console.print(f"    {key}: {val_str}", style="dim")
