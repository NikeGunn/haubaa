"""Tests for SessionTracker — action tracing and session awareness."""

from __future__ import annotations

import time

from hauba.engine.session_tracker import ActionTrace, SessionTracker

# --- ActionTrace tests ---


def test_action_trace_format_success() -> None:
    """ActionTrace formats success correctly."""
    trace = ActionTrace(
        turn=3,
        tool_name="bash",
        tool_input_summary='"echo hello"',
        success=True,
        duration_ms=42.5,
    )
    formatted = trace.format()
    assert "[T3]" in formatted
    assert "bash" in formatted
    assert "OK" in formatted
    assert "42ms" in formatted or "43ms" in formatted


def test_action_trace_format_failure() -> None:
    """ActionTrace formats failure correctly."""
    trace = ActionTrace(
        turn=5,
        tool_name="read_file",
        tool_input_summary='"missing.py"',
        success=False,
        duration_ms=3.2,
    )
    formatted = trace.format()
    assert "FAIL" in formatted
    assert "read_file" in formatted


def test_action_trace_auto_timestamp() -> None:
    """ActionTrace auto-populates timestamp."""
    before = time.time()
    trace = ActionTrace(
        turn=0, tool_name="test", tool_input_summary="", success=True, duration_ms=0
    )
    after = time.time()
    assert before <= trace.timestamp <= after


# --- SessionTracker basic tests ---


def test_tracker_init_empty() -> None:
    """New tracker starts empty."""
    tracker = SessionTracker()
    assert tracker.total_actions == 0
    assert tracker.total_errors == 0
    assert len(tracker.files_read) == 0
    assert len(tracker.files_written) == 0
    assert len(tracker.files_edited) == 0


def test_tracker_record_tool_call() -> None:
    """record_tool_call stores action trace."""
    tracker = SessionTracker()
    tracker.set_turn(1)
    tracker.record_tool_call(
        tool_name="bash",
        tool_input={"command": "echo hello"},
        success=True,
        duration_ms=50,
        output="hello",
    )
    assert tracker.total_actions == 1
    assert tracker.total_errors == 0
    assert tracker.actions[0].tool_name == "bash"


def test_tracker_record_failure() -> None:
    """Failed tool calls are counted as errors."""
    tracker = SessionTracker()
    tracker.set_turn(2)
    tracker.record_tool_call(
        tool_name="read_file",
        tool_input={"path": "nope.txt"},
        success=False,
        duration_ms=5,
        output="Error: File not found",
    )
    assert tracker.total_actions == 1
    assert tracker.total_errors == 1
    assert len(tracker.errors) == 1


# --- File tracking tests ---


def test_tracker_tracks_read_file() -> None:
    """Successful read_file tracked in files_read."""
    tracker = SessionTracker()
    tracker.record_tool_call(
        tool_name="read_file",
        tool_input={"path": "src/main.py"},
        success=True,
        duration_ms=10,
    )
    assert "src/main.py" in tracker.files_read
    assert len(tracker.files_written) == 0


def test_tracker_tracks_write_file() -> None:
    """Successful write_file tracked in files_written."""
    tracker = SessionTracker()
    tracker.record_tool_call(
        tool_name="write_file",
        tool_input={"path": "src/new.py", "content": "pass"},
        success=True,
        duration_ms=10,
    )
    assert "src/new.py" in tracker.files_written


def test_tracker_tracks_edit_file() -> None:
    """Successful edit_file tracked in files_edited."""
    tracker = SessionTracker()
    tracker.record_tool_call(
        tool_name="edit_file",
        tool_input={"path": "app.py", "old_string": "x", "new_string": "y"},
        success=True,
        duration_ms=10,
    )
    assert "app.py" in tracker.files_edited


def test_tracker_tracks_dir_creation() -> None:
    """write_file with subdirectory tracks parent dir creation."""
    tracker = SessionTracker()
    tracker.record_tool_call(
        tool_name="write_file",
        tool_input={"path": "src/deep/file.py", "content": "pass"},
        success=True,
        duration_ms=10,
    )
    assert "src/deep" in tracker.dirs_created


def test_tracker_no_track_on_failure() -> None:
    """Failed file operations are NOT tracked in file sets."""
    tracker = SessionTracker()
    tracker.record_tool_call(
        tool_name="read_file",
        tool_input={"path": "missing.py"},
        success=False,
        duration_ms=5,
    )
    assert len(tracker.files_read) == 0


# --- Input summarization tests ---


def test_summarize_bash_command() -> None:
    """Bash commands are quoted in summary."""
    tracker = SessionTracker()
    tracker.record_tool_call(
        tool_name="bash",
        tool_input={"command": "npm install"},
        success=True,
        duration_ms=1000,
    )
    assert '"npm install"' in tracker.actions[0].tool_input_summary


def test_summarize_long_bash_truncated() -> None:
    """Long bash commands are truncated."""
    tracker = SessionTracker()
    long_cmd = "echo " + "x" * 200
    tracker.record_tool_call(
        tool_name="bash",
        tool_input={"command": long_cmd},
        success=True,
        duration_ms=50,
    )
    assert "..." in tracker.actions[0].tool_input_summary
    assert len(tracker.actions[0].tool_input_summary) < 100


def test_summarize_file_path() -> None:
    """File tools show path in summary."""
    tracker = SessionTracker()
    tracker.record_tool_call(
        tool_name="read_file",
        tool_input={"path": "src/app.py"},
        success=True,
        duration_ms=10,
    )
    assert '"src/app.py"' in tracker.actions[0].tool_input_summary


def test_summarize_grep_pattern() -> None:
    """Grep shows pattern in summary."""
    tracker = SessionTracker()
    tracker.record_tool_call(
        tool_name="grep",
        tool_input={"pattern": "def main", "path": "."},
        success=True,
        duration_ms=100,
    )
    assert '"def main"' in tracker.actions[0].tool_input_summary


# --- Session context tests ---


def test_get_session_context_empty() -> None:
    """Empty tracker returns empty context."""
    tracker = SessionTracker()
    assert tracker.get_session_context() == ""


def test_get_session_context_basic() -> None:
    """Session context includes turn count and action count."""
    tracker = SessionTracker()
    tracker.set_turn(3)
    tracker.record_tool_call(
        tool_name="bash",
        tool_input={"command": "echo hello"},
        success=True,
        duration_ms=50,
    )
    ctx = tracker.get_session_context()
    assert "Session State" in ctx
    assert "Turn 3" in ctx
    assert "1 tool calls" in ctx


def test_get_session_context_includes_files() -> None:
    """Session context lists files touched."""
    tracker = SessionTracker()
    tracker.record_tool_call(
        tool_name="read_file",
        tool_input={"path": "src/app.py"},
        success=True,
        duration_ms=10,
    )
    tracker.record_tool_call(
        tool_name="write_file",
        tool_input={"path": "src/new.py", "content": "pass"},
        success=True,
        duration_ms=15,
    )
    ctx = tracker.get_session_context()
    assert "Files read:" in ctx
    assert "src/app.py" in ctx
    assert "Files created:" in ctx
    assert "src/new.py" in ctx


def test_get_session_context_includes_recent_actions() -> None:
    """Session context shows recent action traces."""
    tracker = SessionTracker()
    tracker.set_turn(1)
    tracker.record_tool_call(
        tool_name="bash",
        tool_input={"command": "pytest tests/"},
        success=False,
        duration_ms=1200,
    )
    tracker.set_turn(2)
    tracker.record_tool_call(
        tool_name="read_file",
        tool_input={"path": "src/app.py"},
        success=True,
        duration_ms=12,
    )
    ctx = tracker.get_session_context()
    assert "Recent actions:" in ctx
    assert "[T1]" in ctx
    assert "[T2]" in ctx
    assert "FAIL" in ctx
    assert "OK" in ctx


def test_get_session_context_includes_errors() -> None:
    """Session context shows recent errors."""
    tracker = SessionTracker()
    tracker.set_turn(1)
    tracker.record_tool_call(
        tool_name="bash",
        tool_input={"command": "broken"},
        success=False,
        duration_ms=50,
    )
    ctx = tracker.get_session_context()
    assert "Recent errors:" in ctx


def test_get_session_context_includes_working_dir() -> None:
    """Session context shows working directory."""
    tracker = SessionTracker()
    tracker.set_working_directory("/home/user/project")
    tracker.record_tool_call(
        tool_name="bash",
        tool_input={"command": "ls"},
        success=True,
        duration_ms=10,
    )
    ctx = tracker.get_session_context()
    assert "/home/user/project" in ctx


def test_get_session_context_limits_recent_actions() -> None:
    """Session context shows at most 10 recent actions."""
    tracker = SessionTracker()
    for i in range(15):
        tracker.set_turn(i)
        tracker.record_tool_call(
            tool_name="bash",
            tool_input={"command": f"cmd{i}"},
            success=True,
            duration_ms=10,
        )
    ctx = tracker.get_session_context()
    # Should have last 10 actions, not first 5
    assert "[T14]" in ctx
    assert "[T5]" in ctx
    assert "[T4]" not in ctx


# --- Reset tests ---


def test_tracker_reset() -> None:
    """Reset clears all tracking state."""
    tracker = SessionTracker()
    tracker.set_turn(5)
    tracker.record_tool_call(
        tool_name="read_file",
        tool_input={"path": "file.py"},
        success=True,
        duration_ms=10,
    )
    tracker.record_tool_call(
        tool_name="bash",
        tool_input={"command": "fail"},
        success=False,
        duration_ms=10,
    )

    tracker.reset()

    assert tracker.total_actions == 0
    assert tracker.total_errors == 0
    assert len(tracker.files_read) == 0
    assert len(tracker.errors) == 0
    assert tracker.get_session_context() == ""


# --- Working directory tracking ---


def test_tracker_set_working_directory_via_tool() -> None:
    """set_working_directory tool updates tracked working directory."""
    tracker = SessionTracker()
    tracker.record_tool_call(
        tool_name="set_working_directory",
        tool_input={"path": "/new/dir"},
        success=True,
        duration_ms=5,
    )
    ctx = tracker.get_session_context()
    assert "/new/dir" in ctx


# --- Multiple actions ---


def test_tracker_multiple_file_ops() -> None:
    """Tracker handles many file operations without duplicates."""
    tracker = SessionTracker()
    # Read same file twice
    for _ in range(3):
        tracker.record_tool_call(
            tool_name="read_file",
            tool_input={"path": "app.py"},
            success=True,
            duration_ms=10,
        )
    # Sets deduplicate
    assert len(tracker.files_read) == 1
    assert tracker.total_actions == 3


def test_get_session_context_large_file_list() -> None:
    """Large file lists are truncated with '...'."""
    tracker = SessionTracker()
    for i in range(15):
        tracker.record_tool_call(
            tool_name="read_file",
            tool_input={"path": f"file{i}.py"},
            success=True,
            duration_ms=10,
        )
    ctx = tracker.get_session_context()
    assert "..." in ctx
    assert f"Files read ({15})" in ctx
