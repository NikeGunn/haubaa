"""SessionTracker — tracks tool calls, file operations, and session state.

Gives the LLM full awareness of what it has done, what files it has touched,
and the current state of the session. Injected into system prompt before each
LLM call so the agent never loses context.

Inspired by Claude Code's trace system — every action is recorded, the agent
always knows where it is and what it has done.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class ActionTrace:
    """A single recorded tool call with timing and result status."""

    turn: int
    tool_name: str
    tool_input_summary: str
    success: bool
    duration_ms: float
    output_summary: str = ""
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()

    def format(self) -> str:
        """Format for system prompt injection."""
        status = "OK" if self.success else "FAIL"
        return (
            f"  [T{self.turn}] {self.tool_name}({self.tool_input_summary}) "
            f"-> {status} ({self.duration_ms:.0f}ms)"
        )


class SessionTracker:
    """Tracks everything the agent does during a task.

    Records:
    - Files read, written, edited, deleted
    - Directories created
    - Commands executed
    - Tool call history with timing
    - Working directory changes

    Provides get_session_context() for system prompt injection.
    """

    def __init__(self) -> None:
        self._files_read: set[str] = set()
        self._files_written: set[str] = set()
        self._files_edited: set[str] = set()
        self._dirs_created: set[str] = set()
        self._actions: list[ActionTrace] = []
        self._current_turn: int = 0
        self._working_directory: str = ""
        self._errors: list[str] = []
        self._started_at: float = time.time()

    @property
    def total_actions(self) -> int:
        """Total number of tool calls recorded."""
        return len(self._actions)

    @property
    def total_errors(self) -> int:
        """Total number of failed tool calls."""
        return sum(1 for a in self._actions if not a.success)

    @property
    def files_read(self) -> set[str]:
        return self._files_read

    @property
    def files_written(self) -> set[str]:
        return self._files_written

    @property
    def files_edited(self) -> set[str]:
        return self._files_edited

    @property
    def dirs_created(self) -> set[str]:
        return self._dirs_created

    @property
    def actions(self) -> list[ActionTrace]:
        return self._actions

    @property
    def errors(self) -> list[str]:
        return self._errors

    def set_turn(self, turn: int) -> None:
        """Update the current turn number."""
        self._current_turn = turn

    def set_working_directory(self, path: str) -> None:
        """Update tracked working directory."""
        self._working_directory = path

    def record_tool_call(
        self,
        tool_name: str,
        tool_input: dict,
        success: bool,
        duration_ms: float,
        output: str = "",
    ) -> None:
        """Record a tool call with its result."""
        # Build input summary (concise)
        input_summary = self._summarize_input(tool_name, tool_input)
        output_summary = output[:200] if output else ""

        trace = ActionTrace(
            turn=self._current_turn,
            tool_name=tool_name,
            tool_input_summary=input_summary,
            success=success,
            duration_ms=duration_ms,
            output_summary=output_summary,
        )
        self._actions.append(trace)

        # Track file operations
        self._track_file_ops(tool_name, tool_input, success)

        # Track errors
        if not success:
            self._errors.append(f"T{self._current_turn}: {tool_name} failed")

    def _summarize_input(self, tool_name: str, tool_input: dict) -> str:
        """Create a concise summary of tool input."""
        if tool_name == "bash":
            cmd = tool_input.get("command", "")
            if len(cmd) > 80:
                cmd = cmd[:77] + "..."
            return f'"{cmd}"'
        elif tool_name in ("read_file", "write_file", "edit_file"):
            return f'"{tool_input.get("path", "")}"'
        elif tool_name == "grep" or tool_name == "glob":
            return f'"{tool_input.get("pattern", "")}"'
        elif tool_name == "set_working_directory":
            return f'"{tool_input.get("path", "")}"'
        elif tool_name == "list_directory":
            return f'"{tool_input.get("path", ".")}"'
        elif tool_name == "web_search":
            return f'"{tool_input.get("query", "")}"'
        elif tool_name == "web_fetch":
            return f'"{tool_input.get("url", "")}"'
        else:
            # Generic: show first key=value
            if tool_input:
                first_key = next(iter(tool_input))
                val = str(tool_input[first_key])
                if len(val) > 60:
                    val = val[:57] + "..."
                return f'{first_key}="{val}"'
            return ""

    def _track_file_ops(self, tool_name: str, tool_input: dict, success: bool) -> None:
        """Track file read/write/edit operations."""
        if not success:
            return

        path = tool_input.get("path", "")
        if not path:
            return

        if tool_name == "read_file":
            self._files_read.add(path)
        elif tool_name == "write_file":
            self._files_written.add(path)
        elif tool_name == "edit_file":
            self._files_edited.add(path)
        elif tool_name == "set_working_directory":
            self._working_directory = path

        # Track directory creation from write_file (parent dirs)
        if tool_name == "write_file" and "/" in path:
            parent = "/".join(path.split("/")[:-1])
            self._dirs_created.add(parent)

    def get_session_context(self) -> str:
        """Build session context string for system prompt injection.

        Returns a concise summary of what the agent has done so far,
        what files it has touched, and recent actions — so the LLM
        never loses track of its work.
        """
        if not self._actions:
            return ""

        elapsed = time.time() - self._started_at
        elapsed_str = f"{elapsed:.0f}s" if elapsed < 60 else f"{elapsed / 60:.1f}min"

        lines: list[str] = []
        lines.append("## Session State")
        lines.append(
            f"Turn {self._current_turn}. "
            f"{self.total_actions} tool calls in {elapsed_str}. "
            f"{self.total_errors} errors."
        )

        # Working directory
        if self._working_directory:
            lines.append(f"Working directory: {self._working_directory}")

        # Files touched
        if self._files_read:
            files = sorted(self._files_read)
            if len(files) > 10:
                shown = ", ".join(files[:10])
                lines.append(f"Files read ({len(files)}): {shown}, ...")
            else:
                lines.append(f"Files read: {', '.join(files)}")

        if self._files_written:
            files = sorted(self._files_written)
            lines.append(f"Files created: {', '.join(files)}")

        if self._files_edited:
            files = sorted(self._files_edited)
            lines.append(f"Files edited: {', '.join(files)}")

        # Recent actions (last 10)
        recent = self._actions[-10:]
        lines.append("Recent actions:")
        for action in recent:
            lines.append(action.format())

        # Persistent errors
        if self._errors:
            recent_errors = self._errors[-3:]
            lines.append("Recent errors: " + "; ".join(recent_errors))

        return "\n".join(lines)

    def reset(self) -> None:
        """Reset all tracking state for a new task."""
        self._files_read.clear()
        self._files_written.clear()
        self._files_edited.clear()
        self._dirs_created.clear()
        self._actions.clear()
        self._current_turn = 0
        self._errors.clear()
        self._started_at = time.time()
