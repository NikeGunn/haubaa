"""Tests for ToolRegistry — core tool system."""

from __future__ import annotations

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

    # All 10 core tools should be registered
    assert "bash" in tool_names
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

    assert len(defs) >= 10
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
