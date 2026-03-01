"""Tests for the interactive terminal UI module."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from hauba.ui.interactive import (
    AgentPhase,
    FileActivity,
    InteractiveUI,
    ToolActivity,
    UIState,
)


def _make_console() -> Console:
    """Create a Console that writes to a StringIO buffer for testing."""
    return Console(file=StringIO(), force_terminal=True, width=120)


def test_ui_state_defaults() -> None:
    """UIState has sensible defaults."""
    state = UIState()
    assert state.phase == AgentPhase.STARTING
    assert state.task == ""
    assert state.files == []
    assert state.tools == []
    assert state.tool_count == 0


def test_file_activity() -> None:
    """FileActivity stores file info."""
    f = FileActivity(path="main.py", action="create", lines=42, status="done")
    assert f.path == "main.py"
    assert f.action == "create"
    assert f.lines == 42


def test_tool_activity() -> None:
    """ToolActivity stores tool info."""
    t = ToolActivity(name="bash", detail="ls -la", status="running")
    assert t.name == "bash"
    assert t.detail == "ls -la"


def test_interactive_ui_show_header() -> None:
    """show_header sets state and renders without error."""
    c = _make_console()
    ui = InteractiveUI(c)
    ui.show_header(
        task="Build an API",
        provider="anthropic",
        model="claude-sonnet-4-5",
        workspace="/tmp/hauba-output",
        skills=["code-generation", "api-design"],
        interactive=True,
    )
    assert ui.state.task == "Build an API"
    assert ui.state.provider == "anthropic"
    assert ui.state.model == "claude-sonnet-4-5"
    assert len(ui.state.skills) == 2


def test_interactive_ui_show_thinking() -> None:
    """show_thinking updates phase."""
    c = _make_console()
    ui = InteractiveUI(c)
    ui.show_thinking("Analyzing dependencies...")
    assert ui.state.phase == AgentPhase.THINKING
    assert ui.state.thinking_text == "Analyzing dependencies..."


def test_interactive_ui_show_planning() -> None:
    """show_planning updates phase."""
    c = _make_console()
    ui = InteractiveUI(c)
    ui.show_planning()
    assert ui.state.phase == AgentPhase.PLANNING


def test_interactive_ui_show_executing() -> None:
    """show_executing updates phase."""
    c = _make_console()
    ui = InteractiveUI(c)
    ui.show_executing()
    assert ui.state.phase == AgentPhase.EXECUTING


def test_interactive_ui_show_tool_start() -> None:
    """show_tool_start tracks tool activity."""
    c = _make_console()
    ui = InteractiveUI(c)
    ui.show_tool_start("bash", "ls -la")
    assert ui.state.tool_count == 1
    assert len(ui.state.tools) == 1
    assert ui.state.tools[0].name == "bash"

    ui.show_tool_start("Write", "main.py")
    assert ui.state.tool_count == 2


def test_interactive_ui_show_tool_result() -> None:
    """show_tool_result updates last tool status."""
    c = _make_console()
    ui = InteractiveUI(c)
    ui.show_tool_start("bash", "ls")
    ui.show_tool_result("file1.py\nfile2.py", success=True)
    assert ui.state.tools[-1].status == "done"

    ui.show_tool_start("bash", "bad-cmd")
    ui.show_tool_result("", success=False)
    assert ui.state.tools[-1].status == "error"


def test_interactive_ui_show_file_activity() -> None:
    """show_file_activity tracks files."""
    c = _make_console()
    ui = InteractiveUI(c)
    ui.show_file_activity("main.py", "create", lines=50)
    assert len(ui.state.files) == 1
    assert ui.state.files[0].path == "main.py"
    assert ui.state.files[0].action == "create"


def test_interactive_ui_show_streaming_delta() -> None:
    """show_streaming_delta accumulates text."""
    c = _make_console()
    ui = InteractiveUI(c)
    ui.show_streaming_delta("Hello ")
    ui.show_streaming_delta("world!")
    assert ui.state.streaming_output == "Hello world!"


def test_interactive_ui_show_completion() -> None:
    """show_completion sets phase to COMPLETED."""
    c = _make_console()
    ui = InteractiveUI(c)
    ui.show_completion("Task done", tool_count=5)
    assert ui.state.phase == AgentPhase.COMPLETED


def test_interactive_ui_show_failure() -> None:
    """show_failure sets phase to FAILED."""
    c = _make_console()
    ui = InteractiveUI(c)
    ui.show_failure("Something went wrong")
    assert ui.state.phase == AgentPhase.FAILED
    assert ui.state.error == "Something went wrong"


def test_interactive_ui_show_human_escalation() -> None:
    """show_human_escalation sets phase to ASKING_USER."""
    c = _make_console()
    ui = InteractiveUI(c)
    ui.show_human_escalation("What API key should I use?")
    assert ui.state.phase == AgentPhase.ASKING_USER


def test_agent_phase_values() -> None:
    """AgentPhase enum has all expected values."""
    phases = [p.value for p in AgentPhase]
    assert "thinking" in phases
    assert "planning" in phases
    assert "executing" in phases
    assert "completed" in phases
    assert "failed" in phases
    assert "asking_user" in phases
    assert "waiting_confirm" in phases
    assert "delivering" in phases
