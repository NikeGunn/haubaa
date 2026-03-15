"""Tests for ToolRegistry — core tool system."""

from __future__ import annotations

import platform
from pathlib import Path

import pytest

from hauba.engine.tool_registry import ToolDefinition, ToolRegistry, ToolResult

# --- ToolResult tests ---


def test_tool_result_ok() -> None:
    """ToolResult.ok() creates success result."""
    r = ToolResult.ok("output text", extra="value")
    assert r.success
    assert r.output == "output text"
    assert r.details["extra"] == "value"


def test_tool_result_error() -> None:
    """ToolResult.error() creates failure result."""
    r = ToolResult.error("something broke")
    assert not r.success
    assert "Error:" in r.output


# --- ToolDefinition tests ---


def test_tool_definition_schema() -> None:
    """ToolDefinition converts to JSON schema."""

    async def dummy(**kwargs):
        return ToolResult.ok("ok")

    tool = ToolDefinition(
        name="test_tool",
        description="A test tool",
        parameters={"type": "object", "properties": {"x": {"type": "string"}}},
        execute_fn=dummy,
    )

    schema = tool.to_schema()
    assert schema["name"] == "test_tool"
    assert schema["description"] == "A test tool"
    assert "properties" in schema["parameters"]


# --- ToolRegistry initialization ---


def test_registry_init_registers_core_tools() -> None:
    """Registry registers all core tools on init."""
    registry = ToolRegistry()
    tools = registry.list_tools()
    tool_names = {t.name for t in tools}

    # All 11 core tools should be registered
    assert "bash" in tool_names
    assert "set_working_directory" in tool_names
    assert "read_file" in tool_names
    assert "write_file" in tool_names
    assert "edit_file" in tool_names
    assert "list_directory" in tool_names
    assert "grep" in tool_names
    assert "glob" in tool_names
    assert "web_search" in tool_names
    assert "web_fetch" in tool_names
    assert "send_email" in tool_names


def test_registry_get_tool_definitions() -> None:
    """Registry returns tool schemas for LLM API."""
    registry = ToolRegistry()
    defs = registry.get_tool_definitions()

    assert len(defs) >= 11
    for d in defs:
        assert "name" in d
        assert "description" in d
        assert "parameters" in d


def test_registry_custom_tool() -> None:
    """Can register custom tools."""
    registry = ToolRegistry()

    async def my_tool(x: str) -> ToolResult:
        return ToolResult.ok(f"got {x}")

    registry.register(
        ToolDefinition(
            name="custom",
            description="Custom tool",
            parameters={"type": "object", "properties": {"x": {"type": "string"}}},
            execute_fn=my_tool,
        )
    )

    assert any(t.name == "custom" for t in registry.list_tools())


# --- Tool execution tests ---


@pytest.mark.asyncio
async def test_execute_unknown_tool() -> None:
    """Executing unknown tool returns error."""
    registry = ToolRegistry()
    result = await registry.execute("nonexistent", {})
    assert not result.success
    assert "Unknown tool" in result.output


@pytest.mark.asyncio
async def test_execute_bash_echo() -> None:
    """Bash tool runs shell commands."""
    registry = ToolRegistry()
    result = await registry.execute("bash", {"command": "echo hello"})
    assert result.success
    assert "hello" in result.output


@pytest.mark.asyncio
async def test_execute_bash_timeout() -> None:
    """Bash tool respects timeout."""
    registry = ToolRegistry()
    result = await registry.execute(
        "bash",
        {
            "command": "sleep 10",
            "timeout": 1,
        },
    )
    assert not result.success
    assert "timed out" in result.output.lower()


@pytest.mark.asyncio
async def test_execute_read_file(tmp_path: Path) -> None:
    """read_file reads file contents with line numbers."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line 1\nline 2\nline 3\n")

    registry = ToolRegistry(working_directory=str(tmp_path))
    result = await registry.execute("read_file", {"path": "test.txt"})

    assert result.success
    assert "line 1" in result.output
    assert "line 2" in result.output
    assert "line 3" in result.output
    # Should have line numbers
    assert "\t" in result.output


@pytest.mark.asyncio
async def test_execute_read_file_not_found() -> None:
    """read_file returns error for missing files."""
    registry = ToolRegistry()
    result = await registry.execute("read_file", {"path": "/nonexistent/file.txt"})
    assert not result.success
    assert "not found" in result.output.lower()


@pytest.mark.asyncio
async def test_execute_read_file_with_offset_limit(tmp_path: Path) -> None:
    """read_file supports offset and limit."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("\n".join(f"line {i}" for i in range(1, 11)))

    registry = ToolRegistry(working_directory=str(tmp_path))
    result = await registry.execute(
        "read_file",
        {
            "path": "test.txt",
            "offset": 3,
            "limit": 2,
        },
    )

    assert result.success
    assert "line 4" in result.output
    assert "line 5" in result.output
    assert "line 1" not in result.output


@pytest.mark.asyncio
async def test_execute_write_file(tmp_path: Path) -> None:
    """write_file creates files."""
    registry = ToolRegistry(working_directory=str(tmp_path))
    result = await registry.execute(
        "write_file",
        {
            "path": "new_file.txt",
            "content": "hello world",
        },
    )

    assert result.success
    assert (tmp_path / "new_file.txt").read_text() == "hello world"


@pytest.mark.asyncio
async def test_execute_write_file_creates_dirs(tmp_path: Path) -> None:
    """write_file creates parent directories."""
    registry = ToolRegistry(working_directory=str(tmp_path))
    result = await registry.execute(
        "write_file",
        {
            "path": "subdir/deep/file.txt",
            "content": "nested",
        },
    )

    assert result.success
    assert (tmp_path / "subdir" / "deep" / "file.txt").read_text() == "nested"


@pytest.mark.asyncio
async def test_execute_edit_file(tmp_path: Path) -> None:
    """edit_file replaces exact string match."""
    test_file = tmp_path / "code.py"
    test_file.write_text("def hello():\n    print('hello')\n")

    registry = ToolRegistry(working_directory=str(tmp_path))
    result = await registry.execute(
        "edit_file",
        {
            "path": "code.py",
            "old_string": "print('hello')",
            "new_string": "print('world')",
        },
    )

    assert result.success
    assert "print('world')" in test_file.read_text()


@pytest.mark.asyncio
async def test_execute_edit_file_not_found(tmp_path: Path) -> None:
    """edit_file returns error for missing file."""
    registry = ToolRegistry(working_directory=str(tmp_path))
    result = await registry.execute(
        "edit_file",
        {
            "path": "missing.py",
            "old_string": "x",
            "new_string": "y",
        },
    )
    assert not result.success
    assert "not found" in result.output.lower()


@pytest.mark.asyncio
async def test_execute_edit_file_string_not_found(tmp_path: Path) -> None:
    """edit_file returns error when string not found."""
    test_file = tmp_path / "code.py"
    test_file.write_text("def hello(): pass\n")

    registry = ToolRegistry(working_directory=str(tmp_path))
    result = await registry.execute(
        "edit_file",
        {
            "path": "code.py",
            "old_string": "nonexistent string",
            "new_string": "replacement",
        },
    )
    assert not result.success
    assert "not found" in result.output.lower()


@pytest.mark.asyncio
async def test_execute_edit_file_ambiguous(tmp_path: Path) -> None:
    """edit_file returns error when string appears multiple times."""
    test_file = tmp_path / "code.py"
    test_file.write_text("x = 1\ny = x\nz = x\n")

    registry = ToolRegistry(working_directory=str(tmp_path))
    result = await registry.execute(
        "edit_file",
        {
            "path": "code.py",
            "old_string": "x",
            "new_string": "w",
        },
    )
    assert not result.success
    assert "times" in result.output.lower()


@pytest.mark.asyncio
async def test_execute_list_directory(tmp_path: Path) -> None:
    """list_directory shows directory contents."""
    (tmp_path / "file1.py").write_text("pass")
    (tmp_path / "file2.txt").write_text("hello")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested.py").write_text("pass")

    registry = ToolRegistry(working_directory=str(tmp_path))
    result = await registry.execute("list_directory", {"path": "."})

    assert result.success
    assert "file1.py" in result.output
    assert "file2.txt" in result.output
    assert "subdir" in result.output


@pytest.mark.asyncio
async def test_execute_grep(tmp_path: Path) -> None:
    """grep searches file contents."""
    (tmp_path / "a.py").write_text("def hello():\n    return 'world'\n")
    (tmp_path / "b.py").write_text("class Foo:\n    pass\n")

    registry = ToolRegistry(working_directory=str(tmp_path))
    result = await registry.execute(
        "grep",
        {
            "pattern": "def hello",
            "path": ".",
        },
    )

    assert result.success
    assert "hello" in result.output
    assert "a.py" in result.output


@pytest.mark.asyncio
async def test_execute_grep_with_include(tmp_path: Path) -> None:
    """grep filters by file pattern."""
    (tmp_path / "a.py").write_text("target line\n")
    (tmp_path / "b.txt").write_text("target line\n")

    registry = ToolRegistry(working_directory=str(tmp_path))
    result = await registry.execute(
        "grep",
        {
            "pattern": "target",
            "path": ".",
            "include": "**/*.py",
        },
    )

    assert result.success
    assert "a.py" in result.output
    # b.txt should NOT be included
    assert "b.txt" not in result.output


@pytest.mark.asyncio
async def test_execute_grep_no_match(tmp_path: Path) -> None:
    """grep returns empty result when no matches."""
    (tmp_path / "a.py").write_text("hello world\n")

    registry = ToolRegistry(working_directory=str(tmp_path))
    result = await registry.execute(
        "grep",
        {
            "pattern": "nonexistent_pattern",
            "path": ".",
        },
    )

    assert result.success
    assert "No matches" in result.output


@pytest.mark.asyncio
async def test_execute_glob(tmp_path: Path) -> None:
    """glob finds files by pattern."""
    (tmp_path / "a.py").write_text("pass")
    (tmp_path / "b.py").write_text("pass")
    (tmp_path / "c.txt").write_text("hello")

    registry = ToolRegistry(working_directory=str(tmp_path))
    result = await registry.execute(
        "glob",
        {
            "pattern": "*.py",
            "path": ".",
        },
    )

    assert result.success
    assert "a.py" in result.output
    assert "b.py" in result.output
    assert "c.txt" not in result.output


@pytest.mark.asyncio
async def test_execute_glob_recursive(tmp_path: Path) -> None:
    """glob searches recursively with **."""
    sub = tmp_path / "src"
    sub.mkdir()
    (sub / "main.py").write_text("pass")
    (tmp_path / "test.py").write_text("pass")

    registry = ToolRegistry(working_directory=str(tmp_path))
    result = await registry.execute(
        "glob",
        {
            "pattern": "**/*.py",
            "path": ".",
        },
    )

    assert result.success
    assert "main.py" in result.output
    assert "test.py" in result.output


# --- Invalid parameters ---


@pytest.mark.asyncio
async def test_execute_with_missing_params() -> None:
    """Tools handle missing required parameters."""
    registry = ToolRegistry()
    result = await registry.execute("bash", {})
    assert not result.success
    assert "parameter" in result.output.lower() or "missing" in result.output.lower()


# --- Bash cwd parameter ---


@pytest.mark.asyncio
async def test_bash_cwd_parameter(tmp_path: Path) -> None:
    """Bash cwd runs command in specified directory."""
    subdir = tmp_path / "myapp"
    subdir.mkdir()
    (subdir / "hello.txt").write_text("found")

    registry = ToolRegistry(working_directory=str(tmp_path))
    result = await registry.execute(
        "bash",
        {
            "command": "cat hello.txt" if platform.system() != "Windows" else "type hello.txt",
            "cwd": "myapp",
        },
    )

    assert result.success
    assert "found" in result.output


@pytest.mark.asyncio
async def test_bash_cwd_nonexistent(tmp_path: Path) -> None:
    """Bash cwd returns error for nonexistent directory."""
    registry = ToolRegistry(working_directory=str(tmp_path))
    result = await registry.execute(
        "bash",
        {
            "command": "echo hello",
            "cwd": "nonexistent_dir",
        },
    )

    assert not result.success
    assert "not found" in result.output.lower() or "directory" in result.output.lower()


@pytest.mark.asyncio
async def test_bash_timeout_suggests_background() -> None:
    """Bash timeout message suggests using background=true."""
    registry = ToolRegistry()
    result = await registry.execute(
        "bash",
        {
            "command": "sleep 10",
            "timeout": 1,
        },
    )
    assert not result.success
    assert "background" in result.output.lower()


@pytest.mark.asyncio
async def test_bash_background_mode(tmp_path: Path) -> None:
    """Bash background mode returns immediately with PID."""
    registry = ToolRegistry(working_directory=str(tmp_path))
    result = await registry.execute(
        "bash",
        {
            "command": "sleep 60",
            "background": True,
        },
    )

    assert result.success
    assert "PID" in result.output
    assert "background" in result.output.lower()
    assert len(registry._background_processes) > 0

    # Cleanup
    await registry.cleanup_background_processes()
    assert len(registry._background_processes) == 0


# --- set_working_directory ---


@pytest.mark.asyncio
async def test_set_working_directory(tmp_path: Path) -> None:
    """set_working_directory changes the persistent working directory."""
    subdir = tmp_path / "myproject"
    subdir.mkdir()
    (subdir / "test.txt").write_text("project file")

    registry = ToolRegistry(working_directory=str(tmp_path))
    result = await registry.execute("set_working_directory", {"path": "myproject"})

    assert result.success
    assert "myproject" in result.output

    # Now read_file should work relative to new directory
    result2 = await registry.execute("read_file", {"path": "test.txt"})
    assert result2.success
    assert "project file" in result2.output


@pytest.mark.asyncio
async def test_set_working_directory_nonexistent(tmp_path: Path) -> None:
    """set_working_directory returns error for nonexistent directory."""
    registry = ToolRegistry(working_directory=str(tmp_path))
    result = await registry.execute("set_working_directory", {"path": "nonexistent"})

    assert not result.success
    assert "not a directory" in result.output.lower()


@pytest.mark.asyncio
async def test_set_working_directory_affects_bash(tmp_path: Path) -> None:
    """set_working_directory affects bash default cwd."""
    subdir = tmp_path / "myapp"
    subdir.mkdir()
    (subdir / "hello.txt").write_text("hello from myapp")

    registry = ToolRegistry(working_directory=str(tmp_path))
    await registry.execute("set_working_directory", {"path": "myapp"})

    result = await registry.execute(
        "bash",
        {
            "command": "cat hello.txt" if platform.system() != "Windows" else "type hello.txt",
        },
    )

    assert result.success
    assert "hello from myapp" in result.output


# --- Cleanup ---


@pytest.mark.asyncio
async def test_cleanup_background_processes(tmp_path: Path) -> None:
    """cleanup_background_processes kills all background processes."""
    registry = ToolRegistry(working_directory=str(tmp_path))

    # Start a background process
    await registry.execute("bash", {"command": "sleep 600", "background": True})

    assert len(registry._background_processes) == 1

    await registry.cleanup_background_processes()
    assert len(registry._background_processes) == 0


@pytest.mark.asyncio
async def test_background_process_cap(tmp_path: Path) -> None:
    """Cannot exceed MAX_BACKGROUND_PROCESSES concurrent background processes."""
    from hauba.engine.tool_registry import MAX_BACKGROUND_PROCESSES

    registry = ToolRegistry(working_directory=str(tmp_path))

    # Fill up to the limit
    for i in range(MAX_BACKGROUND_PROCESSES):
        result = await registry.execute("bash", {"command": f"sleep {600 + i}", "background": True})
        assert result.success, f"Process {i} should start: {result.output}"

    # Next one should be rejected
    result = await registry.execute("bash", {"command": "sleep 999", "background": True})
    assert not result.success
    assert "too many" in result.output.lower()

    # Cleanup
    await registry.cleanup_background_processes()


@pytest.mark.asyncio
async def test_bash_timeout_kills_process() -> None:
    """Bash timeout kills the process (not just returns error)."""
    registry = ToolRegistry()
    result = await registry.execute(
        "bash",
        {
            "command": "sleep 60",
            "timeout": 2,
        },
    )
    assert not result.success
    assert "killed" in result.output.lower()


# --- Tracker integration ---


def test_registry_has_tracker() -> None:
    """ToolRegistry has a SessionTracker."""
    registry = ToolRegistry()
    assert registry.tracker is not None
    assert registry.tracker.total_actions == 0


@pytest.mark.asyncio
async def test_tracker_records_tool_calls() -> None:
    """execute() records tool calls in the tracker."""
    registry = ToolRegistry()
    await registry.execute("bash", {"command": "echo tracked"})
    assert registry.tracker.total_actions == 1
    assert registry.tracker.actions[0].tool_name == "bash"
    assert registry.tracker.actions[0].success is True
    assert registry.tracker.actions[0].duration_ms >= 0


@pytest.mark.asyncio
async def test_tracker_records_failures() -> None:
    """Failed tool calls are tracked with success=False."""
    registry = ToolRegistry()
    await registry.execute("read_file", {"path": "/nonexistent/file.txt"})
    assert registry.tracker.total_actions == 1
    assert registry.tracker.total_errors == 1
    assert registry.tracker.actions[0].success is False


@pytest.mark.asyncio
async def test_tracker_records_file_ops(tmp_path: Path) -> None:
    """File operations are tracked in file sets."""
    registry = ToolRegistry(working_directory=str(tmp_path))

    # Write a file
    await registry.execute("write_file", {"path": "test.py", "content": "pass"})
    assert "test.py" in registry.tracker.files_written

    # Read it
    await registry.execute("read_file", {"path": "test.py"})
    assert "test.py" in registry.tracker.files_read

    # Edit it
    await registry.execute(
        "edit_file",
        {"path": "test.py", "old_string": "pass", "new_string": "x = 1"},
    )
    assert "test.py" in registry.tracker.files_edited


@pytest.mark.asyncio
async def test_tracker_session_context(tmp_path: Path) -> None:
    """Tracker produces session context after tool calls."""
    registry = ToolRegistry(working_directory=str(tmp_path))
    registry.tracker.set_turn(1)

    await registry.execute("write_file", {"path": "app.py", "content": "hello"})
    await registry.execute("bash", {"command": "echo done"})

    ctx = registry.tracker.get_session_context()
    assert "Session State" in ctx
    assert "2 tool calls" in ctx
    assert "app.py" in ctx


# --- Command interception layer ---


def test_check_blocked_command_rm_rf_root() -> None:
    """rm -rf / is blocked."""
    from hauba.engine.tool_registry import _check_blocked_command

    assert _check_blocked_command("rm -rf /") is not None
    assert _check_blocked_command("rm -rf / --no-preserve-root") is not None


def test_check_blocked_command_shutdown() -> None:
    """shutdown is blocked."""
    from hauba.engine.tool_registry import _check_blocked_command

    assert _check_blocked_command("shutdown -h now") is not None
    assert _check_blocked_command("reboot") is not None


def test_check_blocked_command_safe_commands() -> None:
    """Normal commands are not blocked."""
    from hauba.engine.tool_registry import _check_blocked_command

    assert _check_blocked_command("npm install") is None
    assert _check_blocked_command("rm -rf node_modules") is None
    assert _check_blocked_command("echo hello") is None


def test_extract_cd_prefix() -> None:
    """cd <dir> && <cmd> is split into (cmd, dir)."""
    from hauba.engine.tool_registry import _extract_cd_prefix

    cmd, cwd = _extract_cd_prefix("cd my-app && npm install")
    assert cmd == "npm install"
    assert cwd == "my-app"


def test_extract_cd_prefix_semicolon() -> None:
    """cd <dir> ; <cmd> is also handled."""
    from hauba.engine.tool_registry import _extract_cd_prefix

    cmd, cwd = _extract_cd_prefix("cd src ; python main.py")
    assert cmd == "python main.py"
    assert cwd == "src"


def test_extract_cd_prefix_no_cd() -> None:
    """Commands without cd prefix are returned unchanged."""
    from hauba.engine.tool_registry import _extract_cd_prefix

    cmd, cwd = _extract_cd_prefix("npm install")
    assert cmd == "npm install"
    assert cwd == ""


def test_is_long_running_npm_start() -> None:
    """npm start is detected as long-running."""
    from hauba.engine.tool_registry import _is_long_running_command

    assert _is_long_running_command("npm start")
    assert _is_long_running_command("npm run dev")
    assert _is_long_running_command("yarn start")
    assert _is_long_running_command("npx serve")
    assert _is_long_running_command("python -m http.server 8080")
    assert _is_long_running_command("flask run --port 5000")
    assert _is_long_running_command("uvicorn main:app --reload")


def test_is_long_running_safe_commands() -> None:
    """Normal commands are NOT detected as long-running."""
    from hauba.engine.tool_registry import _is_long_running_command

    assert not _is_long_running_command("npm install")
    assert not _is_long_running_command("npm run build")
    assert not _is_long_running_command("npm test")
    assert not _is_long_running_command("python setup.py install")
    assert not _is_long_running_command("echo hello")


def test_rewrite_command_for_platform_unix() -> None:
    """On Unix, commands are not rewritten."""
    from hauba.engine.tool_registry import _rewrite_command_for_platform

    assert _rewrite_command_for_platform("rm -rf dist", is_windows=False) == "rm -rf dist"
    assert _rewrite_command_for_platform("cat file.txt", is_windows=False) == "cat file.txt"


def test_rewrite_command_for_platform_windows() -> None:
    """On Windows, Unix commands are rewritten."""
    from hauba.engine.tool_registry import _rewrite_command_for_platform

    assert "rmdir" in _rewrite_command_for_platform("rm -rf dist", is_windows=True)
    assert "type" in _rewrite_command_for_platform("cat file.txt", is_windows=True)
    assert "dir" in _rewrite_command_for_platform("ls", is_windows=True)
    assert "where" in _rewrite_command_for_platform("which python", is_windows=True)


@pytest.mark.asyncio
async def test_bash_auto_background_npm_start(tmp_path: Path) -> None:
    """npm start is automatically switched to background mode."""
    registry = ToolRegistry(working_directory=str(tmp_path))
    # Create a fake package.json so npm start would try to run
    (tmp_path / "package.json").write_text('{"scripts":{"start":"echo ok"}}')

    result = await registry.execute("bash", {"command": "npm start"})

    # Should have been auto-switched to background mode
    assert result.success
    assert "background" in result.output.lower() or "PID" in result.output

    await registry.cleanup_background_processes()


@pytest.mark.asyncio
async def test_bash_cd_extraction(tmp_path: Path) -> None:
    """'cd <dir> && <cmd>' extracts dir as cwd."""
    subdir = tmp_path / "myapp"
    subdir.mkdir()
    (subdir / "hello.txt").write_text("found-it")

    registry = ToolRegistry(working_directory=str(tmp_path))
    result = await registry.execute(
        "bash",
        {
            "command": "cd myapp && type hello.txt"
            if platform.system() == "Windows"
            else "cd myapp && cat hello.txt",
        },
    )
    assert result.success
    assert "found-it" in result.output


@pytest.mark.asyncio
async def test_bash_blocked_command() -> None:
    """Blocked commands return error without executing."""
    registry = ToolRegistry()
    result = await registry.execute("bash", {"command": "shutdown -h now"})
    assert not result.success
    assert "blocked" in result.output.lower()
