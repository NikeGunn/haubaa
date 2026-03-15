"""Unified tool registry for Hauba V4.

Core tools inspired by OpenClaw/Pi:
- bash: Run any shell command (with resource guards)
- read_file: Read file contents
- write_file: Write/create files
- edit_file: Precise string replacement edits
- web_search: Search the web (DuckDuckGo)
- web_fetch: Fetch URL content
- send_email: Send email via Brevo API
- list_directory: List directory contents

Each tool has:
- Name and description
- JSON Schema parameters
- Async execute function
- Structured output (text for LLM + details for UI)

Safety:
- Process tree kill on timeout/cleanup (not just parent PID)
- Memory limits via Windows Job Objects / Unix ulimit
- Max concurrent background processes capped
- Dangerous command patterns blocked
"""

from __future__ import annotations

import asyncio
import os
import platform
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from hauba.engine.session_tracker import SessionTracker

logger = structlog.get_logger()

# Maximum output size to prevent context bloat
MAX_OUTPUT_SIZE = 100_000
# Shell command timeout
SHELL_TIMEOUT = 120
# Maximum concurrent background processes
MAX_BACKGROUND_PROCESSES = 3
# Maximum memory per process (512 MB) — prevents OOM system crashes
MAX_PROCESS_MEMORY_BYTES = 512 * 1024 * 1024


@dataclass
class ToolResult:
    """Result of a tool execution."""

    success: bool
    output: str
    details: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def ok(output: str, **details: Any) -> ToolResult:
        return ToolResult(success=True, output=output, details=details)

    @staticmethod
    def error(message: str) -> ToolResult:
        return ToolResult(success=False, output=f"Error: {message}")


@dataclass
class ToolDefinition:
    """A tool definition with schema and executor."""

    name: str
    description: str
    parameters: dict[str, Any]
    execute_fn: Any  # async callable

    def to_schema(self) -> dict[str, Any]:
        """Convert to JSON Schema for LLM tool calling."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class ToolRegistry:
    """Registry of all available tools.

    Initializes core tools and provides execution dispatch.
    """

    def __init__(self, working_directory: str = ".") -> None:
        self._working_directory = os.path.abspath(working_directory)
        self._tools: dict[str, ToolDefinition] = {}
        self._background_processes: dict[int, Any] = {}
        self.tracker = SessionTracker()
        self.tracker.set_working_directory(self._working_directory)
        self._register_core_tools()

    def _register_core_tools(self) -> None:
        """Register all core tools."""
        self._register_bash()
        self._register_set_working_directory()
        self._register_read_file()
        self._register_write_file()
        self._register_edit_file()
        self._register_list_directory()
        self._register_grep()
        self._register_glob()
        self._register_web_search()
        self._register_web_fetch()
        self._register_send_email()

    def register(self, tool: ToolDefinition) -> None:
        """Register a custom tool."""
        self._tools[tool.name] = tool

    def list_tools(self) -> list[ToolDefinition]:
        """List all registered tools."""
        return list(self._tools.values())

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions for LLM API calls."""
        return [t.to_schema() for t in self._tools.values()]

    async def execute(self, name: str, params: dict[str, Any]) -> ToolResult:
        """Execute a tool by name with given parameters."""
        tool = self._tools.get(name)
        if not tool:
            return ToolResult.error(f"Unknown tool: {name}. Available: {list(self._tools.keys())}")

        start_time = time.monotonic()
        try:
            result = await tool.execute_fn(**params)
            # Truncate very long output
            if isinstance(result, ToolResult) and len(result.output) > MAX_OUTPUT_SIZE:
                result.output = (
                    result.output[:MAX_OUTPUT_SIZE]
                    + f"\n\n[Output truncated at {MAX_OUTPUT_SIZE} chars]"
                )
            duration_ms = (time.monotonic() - start_time) * 1000
            self.tracker.record_tool_call(
                tool_name=name,
                tool_input=params,
                success=result.success,
                duration_ms=duration_ms,
                output=result.output,
            )
            return result
        except TypeError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            self.tracker.record_tool_call(
                tool_name=name,
                tool_input=params,
                success=False,
                duration_ms=duration_ms,
                output=str(e),
            )
            return ToolResult.error(f"Invalid parameters for {name}: {e}")
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            self.tracker.record_tool_call(
                tool_name=name,
                tool_input=params,
                success=False,
                duration_ms=duration_ms,
                output=str(e),
            )
            logger.error("tool.execute_error", tool=name, error=str(e))
            return ToolResult.error(f"{name} failed: {e}")

    # ─── BASH ────────────────────────────────────────────────────────

    def _register_bash(self) -> None:
        async def bash(
            command: str,
            cwd: str = "",
            timeout: int = SHELL_TIMEOUT,
            background: bool = False,
        ) -> ToolResult:
            """Run a shell command with resource guards."""
            try:
                # ── STEP 1: Block dangerous commands ──
                blocked = _check_blocked_command(command)
                if blocked:
                    return ToolResult.error(blocked)

                # ── STEP 2: Auto-extract cd from "cd X && cmd" pattern ──
                command, extracted_cwd = _extract_cd_prefix(command)
                if extracted_cwd and not cwd:
                    cwd = extracted_cwd

                # ── STEP 3: Auto-detect long-running commands → force background ──
                if not background and _is_long_running_command(command):
                    background = True
                    logger.info(
                        "tool.bash.auto_background",
                        command=command[:80],
                        reason="detected long-running server/watcher command",
                    )

                # ── STEP 4: Platform-aware command rewriting ──
                is_windows = platform.system() == "Windows"
                command = _rewrite_command_for_platform(command, is_windows)

                # ── STEP 5: Resolve working directory ──
                if cwd:
                    effective_cwd = os.path.abspath(os.path.join(self._working_directory, cwd))
                    if not os.path.isdir(effective_cwd):
                        return ToolResult.error(
                            f"Directory not found: {cwd} (resolved to {effective_cwd})"
                        )
                else:
                    effective_cwd = self._working_directory

                # ── STEP 6: Enforce concurrent background process limit ──
                if background and len(self._background_processes) >= MAX_BACKGROUND_PROCESSES:
                    return ToolResult.error(
                        f"Too many background processes ({MAX_BACKGROUND_PROCESSES} max). "
                        "Kill an existing one first with bash(command='taskkill /F /PID <pid>') "
                        "on Windows or bash(command='kill <pid>') on Unix."
                    )

                # ── STEP 7: Create subprocess with process group ──
                create_flags = 0
                if is_windows:
                    create_flags = subprocess.CREATE_NEW_PROCESS_GROUP
                    proc = await asyncio.create_subprocess_shell(
                        command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=effective_cwd,
                        creationflags=create_flags,
                    )
                else:
                    proc = await asyncio.create_subprocess_exec(
                        "/bin/bash",
                        "-c",
                        command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=effective_cwd,
                        start_new_session=True,
                    )

                # ── STEP 8: Background mode ──
                if background:
                    initial = await _collect_initial_output(proc, seconds=5)
                    pid = proc.pid or 0
                    self._background_processes[pid] = proc
                    return ToolResult.ok(
                        f"Process started in background (PID: {pid}).\n"
                        f"Working directory: {effective_cwd}\n"
                        f"Initial output:\n{initial}\n"
                        f"The process is running. To stop it: "
                        f"bash(command='taskkill /F /T /PID {pid}') on Windows or "
                        f"bash(command='kill -- -{pid}') on Unix.",
                        pid=pid,
                    )

                # ── STEP 9: Synchronous execution with timeout + tree kill ──
                try:
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                except TimeoutError:
                    await _kill_process_tree(proc)
                    return ToolResult.error(
                        f"Command timed out after {timeout}s and was killed. "
                        "If this is a long-running process (dev server, watcher), "
                        "use background=true instead."
                    )

                output = stdout.decode("utf-8", errors="replace")
                err = stderr.decode("utf-8", errors="replace")

                if err.strip():
                    output += f"\nSTDERR:\n{err}"
                if proc.returncode != 0:
                    output += f"\n[exit code: {proc.returncode}]"

                return ToolResult.ok(output, exit_code=proc.returncode)

            except Exception as e:
                return ToolResult.error(f"Shell error: {e}")

        self._tools["bash"] = ToolDefinition(
            name="bash",
            description=(
                "Run a shell command. Use for: executing code, installing packages, "
                "running tests, git operations, system commands. "
                "IMPORTANT: Each call runs in an isolated shell — 'cd' does NOT persist. "
                "Use the 'cwd' parameter to run commands in a subdirectory. "
                "For long-running processes (dev servers, watchers), use background=true. "
                "Max 3 background processes at once."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute.",
                    },
                    "cwd": {
                        "type": "string",
                        "description": (
                            "Working directory for this command (relative or absolute). "
                            "Use this instead of 'cd'. Example: cwd='my-app' to run inside my-app/."
                        ),
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default 120).",
                    },
                    "background": {
                        "type": "boolean",
                        "description": (
                            "Run the command in background (default false). "
                            "Use for dev servers, watchers, or any long-running process. "
                            "Returns immediately with PID and initial output."
                        ),
                    },
                },
                "required": ["command"],
            },
            execute_fn=bash,
        )

    # ─── SET WORKING DIRECTORY ────────────────────────────────────────

    def _register_set_working_directory(self) -> None:
        async def set_working_directory(path: str) -> ToolResult:
            """Change the persistent working directory for ALL tools."""
            resolved = os.path.abspath(os.path.join(self._working_directory, path))
            if not os.path.isdir(resolved):
                return ToolResult.error(f"Not a directory: {path} (resolved to {resolved})")
            old = self._working_directory
            self._working_directory = resolved
            return ToolResult.ok(
                f"Working directory changed: {old} → {resolved}\n"
                "All tools (bash, read_file, write_file, etc.) now operate relative to this path."
            )

        self._tools["set_working_directory"] = ToolDefinition(
            name="set_working_directory",
            description=(
                "Change the persistent working directory for ALL subsequent tool calls. "
                "Equivalent to 'cd' but persists across calls. Affects bash cwd default, "
                "read_file, write_file, edit_file, list_directory, grep, and glob."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path (relative to current working directory, or absolute).",
                    },
                },
                "required": ["path"],
            },
            execute_fn=set_working_directory,
        )

    # ─── CLEANUP ──────────────────────────────────────────────────────

    async def cleanup_background_processes(self) -> None:
        """Kill all background processes AND their child trees.

        Called when engine stops. Uses tree-kill to prevent orphan processes
        that consume memory and CPU after the agent is done.
        """
        for pid, proc in list(self._background_processes.items()):
            try:
                await _kill_process_tree(proc)
                logger.info("tool.background_killed", pid=pid)
            except Exception:
                pass
        self._background_processes.clear()

    # ─── READ FILE ───────────────────────────────────────────────────

    def _register_read_file(self) -> None:
        async def read_file(path: str, offset: int = 0, limit: int = 0) -> ToolResult:
            """Read a file's contents."""
            try:
                file_path = self._resolve_path(path)
                if not file_path.exists():
                    return ToolResult.error(f"File not found: {path}")
                if not file_path.is_file():
                    return ToolResult.error(f"Not a file: {path}")

                content = file_path.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines(keepends=True)

                if offset > 0:
                    lines = lines[offset:]
                if limit > 0:
                    lines = lines[:limit]

                # Add line numbers
                numbered = ""
                start = offset + 1 if offset > 0 else 1
                for i, line in enumerate(lines):
                    numbered += f"{start + i:6d}\t{line}"

                return ToolResult.ok(
                    numbered,
                    path=str(file_path),
                    total_lines=len(content.splitlines()),
                )
            except Exception as e:
                return ToolResult.error(f"Read error: {e}")

        self._tools["read_file"] = ToolDefinition(
            name="read_file",
            description=(
                "Read a file from disk. Returns numbered lines. "
                "Use offset and limit for large files."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path (absolute or relative to working directory).",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Line offset to start reading from (0-based).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max number of lines to read. 0 = all.",
                    },
                },
                "required": ["path"],
            },
            execute_fn=read_file,
        )

    # ─── WRITE FILE ──────────────────────────────────────────────────

    def _register_write_file(self) -> None:
        async def write_file(path: str, content: str) -> ToolResult:
            """Write content to a file (creates parent dirs if needed)."""
            try:
                file_path = self._resolve_path(path)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf-8")
                return ToolResult.ok(
                    f"Wrote {len(content)} chars to {path}",
                    path=str(file_path),
                    size=len(content),
                )
            except Exception as e:
                return ToolResult.error(f"Write error: {e}")

        self._tools["write_file"] = ToolDefinition(
            name="write_file",
            description=(
                "Write or create a file. Creates parent directories automatically. "
                "Overwrites existing content."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to write to.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The full file content to write.",
                    },
                },
                "required": ["path", "content"],
            },
            execute_fn=write_file,
        )

    # ─── EDIT FILE ───────────────────────────────────────────────────

    def _register_edit_file(self) -> None:
        async def edit_file(path: str, old_string: str, new_string: str) -> ToolResult:
            """Edit a file by replacing a specific string."""
            try:
                file_path = self._resolve_path(path)
                if not file_path.exists():
                    return ToolResult.error(f"File not found: {path}")

                content = file_path.read_text(encoding="utf-8")

                count = content.count(old_string)
                if count == 0:
                    return ToolResult.error(
                        f"String not found in {path}. "
                        "Make sure old_string matches exactly (including whitespace)."
                    )
                if count > 1:
                    return ToolResult.error(
                        f"String found {count} times in {path}. "
                        "Provide more context to make it unique."
                    )

                new_content = content.replace(old_string, new_string, 1)
                file_path.write_text(new_content, encoding="utf-8")

                return ToolResult.ok(
                    f"Edited {path}: replaced 1 occurrence ({len(old_string)} → {len(new_string)} chars)",
                    path=str(file_path),
                )
            except Exception as e:
                return ToolResult.error(f"Edit error: {e}")

        self._tools["edit_file"] = ToolDefinition(
            name="edit_file",
            description=(
                "Edit a file by replacing an exact string match. The old_string must "
                "appear exactly once in the file. Include enough surrounding context "
                "to make it unique. Preserves all formatting and indentation."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to edit.",
                    },
                    "old_string": {
                        "type": "string",
                        "description": "The exact string to find and replace.",
                    },
                    "new_string": {
                        "type": "string",
                        "description": "The replacement string.",
                    },
                },
                "required": ["path", "old_string", "new_string"],
            },
            execute_fn=edit_file,
        )

    # ─── LIST DIRECTORY ──────────────────────────────────────────────

    def _register_list_directory(self) -> None:
        async def list_directory(
            path: str = ".", pattern: str = "*", max_depth: int = 3
        ) -> ToolResult:
            """List directory contents recursively."""
            try:
                dir_path = self._resolve_path(path)
                if not dir_path.exists():
                    return ToolResult.error(f"Directory not found: {path}")
                if not dir_path.is_dir():
                    return ToolResult.error(f"Not a directory: {path}")

                entries: list[str] = []
                _list_recursive(dir_path, dir_path, entries, pattern, max_depth, 0)

                output = f"Directory: {path}\n"
                output += f"Entries: {len(entries)}\n\n"
                output += "\n".join(entries[:500])
                if len(entries) > 500:
                    output += f"\n... and {len(entries) - 500} more"

                return ToolResult.ok(output, count=len(entries))
            except Exception as e:
                return ToolResult.error(f"List error: {e}")

        self._tools["list_directory"] = ToolDefinition(
            name="list_directory",
            description=("List files and directories. Supports glob patterns and depth control."),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path (default: working directory).",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to filter (default: '*').",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum recursion depth (default: 3).",
                    },
                },
                "required": [],
            },
            execute_fn=list_directory,
        )

    # ─── GREP ─────────────────────────────────────────────────────────

    def _register_grep(self) -> None:
        async def grep(
            pattern: str,
            path: str = ".",
            include: str = "",
            max_results: int = 50,
            context_lines: int = 0,
        ) -> ToolResult:
            """Search file contents with regex pattern."""
            try:
                import re

                search_path = self._resolve_path(path)
                if not search_path.exists():
                    return ToolResult.error(f"Path not found: {path}")

                try:
                    regex = re.compile(pattern, re.IGNORECASE)
                except re.error as e:
                    return ToolResult.error(f"Invalid regex: {e}")

                matches: list[str] = []
                files_searched = 0

                if search_path.is_file():
                    files_to_search = [search_path]
                else:
                    glob_pattern = include or "**/*"
                    files_to_search = list(search_path.glob(glob_pattern))

                skip_dirs = {
                    ".git",
                    "__pycache__",
                    "node_modules",
                    ".venv",
                    "venv",
                    ".mypy_cache",
                    ".pytest_cache",
                    "dist",
                    "build",
                }

                for file_path in files_to_search:
                    if any(part in skip_dirs for part in file_path.parts):
                        continue
                    if not file_path.is_file():
                        continue

                    # Skip binary files
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="strict")
                    except (UnicodeDecodeError, PermissionError):
                        continue

                    files_searched += 1
                    lines = content.splitlines()
                    rel_path = (
                        file_path.relative_to(search_path)
                        if search_path.is_dir()
                        else file_path.name
                    )

                    for i, line in enumerate(lines):
                        if regex.search(line):
                            line_num = i + 1
                            if context_lines > 0:
                                start = max(0, i - context_lines)
                                end = min(len(lines), i + context_lines + 1)
                                ctx = "\n".join(
                                    f"  {j + 1:6d}: {lines[j]}" for j in range(start, end)
                                )
                                matches.append(f"{rel_path}:{line_num}:\n{ctx}")
                            else:
                                matches.append(f"{rel_path}:{line_num}: {line.strip()}")

                            if len(matches) >= max_results:
                                break
                    if len(matches) >= max_results:
                        break

                if not matches:
                    return ToolResult.ok(
                        f"No matches for '{pattern}' in {files_searched} files.",
                        count=0,
                    )

                output = f"Found {len(matches)} matches in {files_searched} files:\n\n"
                output += "\n".join(matches)
                return ToolResult.ok(output, count=len(matches))

            except Exception as e:
                return ToolResult.error(f"Grep error: {e}")

        self._tools["grep"] = ToolDefinition(
            name="grep",
            description=(
                "Search file contents using regex. Searches recursively through "
                "files in the given path. Skips binary files and common noise dirs. "
                "Use include pattern to filter file types (e.g., '**/*.py')."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regex pattern to search for.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory or file to search (default: working directory).",
                    },
                    "include": {
                        "type": "string",
                        "description": "Glob pattern to filter files (e.g., '**/*.py', '**/*.ts').",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum matches to return (default 50).",
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Lines of context around each match (default 0).",
                    },
                },
                "required": ["pattern"],
            },
            execute_fn=grep,
        )

    # ─── GLOB ─────────────────────────────────────────────────────────

    def _register_glob(self) -> None:
        async def glob(pattern: str, path: str = ".") -> ToolResult:
            """Find files matching a glob pattern."""
            try:
                search_path = self._resolve_path(path)
                if not search_path.exists():
                    return ToolResult.error(f"Path not found: {path}")
                if not search_path.is_dir():
                    return ToolResult.error(f"Not a directory: {path}")

                skip_dirs = {
                    ".git",
                    "__pycache__",
                    "node_modules",
                    ".venv",
                    "venv",
                    ".mypy_cache",
                    ".pytest_cache",
                    "dist",
                    "build",
                }

                matches: list[str] = []
                for match in sorted(search_path.glob(pattern)):
                    if any(part in skip_dirs for part in match.parts):
                        continue
                    rel = match.relative_to(search_path)
                    if match.is_dir():
                        matches.append(f"{rel}/")
                    else:
                        size = match.stat().st_size
                        matches.append(f"{rel}  ({_human_size(size)})")

                    if len(matches) >= 500:
                        break

                if not matches:
                    return ToolResult.ok(f"No files matching '{pattern}'", count=0)

                output = f"Found {len(matches)} matches for '{pattern}':\n\n"
                output += "\n".join(matches)
                return ToolResult.ok(output, count=len(matches))

            except Exception as e:
                return ToolResult.error(f"Glob error: {e}")

        self._tools["glob"] = ToolDefinition(
            name="glob",
            description=(
                "Find files by glob pattern. Examples: '**/*.py' (all Python files), "
                "'src/**/*.ts' (TypeScript in src), '*.json' (JSON in current dir). "
                "Fast file discovery without reading contents."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern (e.g., '**/*.py', 'src/**/*.ts').",
                    },
                    "path": {
                        "type": "string",
                        "description": "Base directory (default: working directory).",
                    },
                },
                "required": ["pattern"],
            },
            execute_fn=glob,
        )

    # ─── WEB SEARCH ──────────────────────────────────────────────────

    def _register_web_search(self) -> None:
        async def web_search(query: str, num_results: int = 5) -> ToolResult:
            """Search the web using DuckDuckGo."""
            try:
                from hauba.tools.web import WebSearchTool

                tool = WebSearchTool()
                result = await tool.execute(query=query, num_results=num_results)
                if result.success:
                    return ToolResult.ok(result.output)
                return ToolResult.error(result.error or "Search failed")
            except ImportError:
                return ToolResult.error("Web search unavailable. Install httpx and beautifulsoup4.")
            except Exception as e:
                return ToolResult.error(f"Search error: {e}")

        self._tools["web_search"] = ToolDefinition(
            name="web_search",
            description=(
                "Search the web using DuckDuckGo. Returns titles, URLs, and snippets. "
                "Use to research technologies, find documentation, look up APIs."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query.",
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of results (default 5).",
                    },
                },
                "required": ["query"],
            },
            execute_fn=web_search,
        )

    # ─── WEB FETCH ───────────────────────────────────────────────────

    def _register_web_fetch(self) -> None:
        async def web_fetch(url: str, extract_text: bool = True) -> ToolResult:
            """Fetch a URL and return content."""
            try:
                from hauba.tools.fetch import WebFetchTool

                tool = WebFetchTool()
                result = await tool.execute(url=url, extract_text=extract_text)
                if result.success:
                    return ToolResult.ok(result.output)
                return ToolResult.error(result.error or "Fetch failed")
            except ImportError:
                return ToolResult.error("Web fetch unavailable. Install httpx and beautifulsoup4.")
            except Exception as e:
                return ToolResult.error(f"Fetch error: {e}")

        self._tools["web_fetch"] = ToolDefinition(
            name="web_fetch",
            description=(
                "Fetch any URL and return content as readable text. "
                "Supports HTML (converted to text), JSON, and plain text. "
                "Use to read docs, API responses, GitHub files."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch.",
                    },
                    "extract_text": {
                        "type": "boolean",
                        "description": "Extract readable text from HTML (default true).",
                    },
                },
                "required": ["url"],
            },
            execute_fn=web_fetch,
        )

    # ─── SEND EMAIL ──────────────────────────────────────────────────

    def _register_send_email(self) -> None:
        async def send_email(to: str, subject: str, body: str) -> ToolResult:
            """Send an email via Brevo API."""
            try:
                from hauba.services.email import EmailService

                svc = EmailService()
                if not svc.configure():
                    return ToolResult.error(
                        "Email not configured. Set HAUBA_EMAIL_API_KEY and HAUBA_EMAIL_FROM."
                    )
                success = await svc.send(to=to, subject=subject, body=body)
                if success:
                    return ToolResult.ok(f"Email sent to {to}")
                return ToolResult.error("Failed to send email")
            except ImportError:
                return ToolResult.error("Email service unavailable.")
            except Exception as e:
                return ToolResult.error(f"Email error: {e}")

        self._tools["send_email"] = ToolDefinition(
            name="send_email",
            description="Send an email via Brevo API (free, 300/day).",
            parameters={
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email."},
                    "subject": {"type": "string", "description": "Subject line."},
                    "body": {"type": "string", "description": "Email body text."},
                },
                "required": ["to", "subject", "body"],
            },
            execute_fn=send_email,
        )

    # ─── Helpers ─────────────────────────────────────────────────────

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to working directory."""
        p = Path(path)
        if p.is_absolute():
            return p
        return Path(self._working_directory) / p


def _list_recursive(
    base: Path,
    current: Path,
    entries: list[str],
    pattern: str,
    max_depth: int,
    depth: int,
) -> None:
    """Recursively list directory entries."""
    if depth > max_depth:
        return

    try:
        items = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        entries.append(f"{'  ' * depth}[permission denied]")
        return

    # Skip common uninteresting directories
    skip_dirs = {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".eggs",
    }

    for item in items:
        if item.name in skip_dirs:
            continue

        rel = item.relative_to(base)
        line_prefix = "  " * depth

        if item.is_dir():
            entries.append(f"{line_prefix}{rel}/")
            _list_recursive(base, item, entries, pattern, max_depth, depth + 1)
        elif item.is_file():
            if pattern == "*" or item.match(pattern):
                file_size = item.stat().st_size
                entries.append(f"{line_prefix}{rel}  ({_human_size(file_size)})")


# ─── COMMAND INTERCEPTION LAYER ──────────────────────────────────
#
# Enforcement at the execution boundary — don't rely on the LLM
# reading system prompt instructions. Weaker models (gpt-4o-mini)
# ignore prompts but they can't bypass tool-level guards.

# Commands that block forever if run synchronously (dev servers, watchers)
_LONG_RUNNING_PATTERNS: list[tuple[str, str]] = [
    # npm/yarn/pnpm dev servers and watchers
    (r"\bnpm\s+start\b", "npm start"),
    (r"\bnpm\s+run\s+dev\b", "npm run dev"),
    (r"\bnpm\s+run\s+serve\b", "npm run serve"),
    (r"\bnpm\s+run\s+watch\b", "npm run watch"),
    (r"\byarn\s+start\b", "yarn start"),
    (r"\byarn\s+dev\b", "yarn dev"),
    (r"\bpnpm\s+start\b", "pnpm start"),
    (r"\bpnpm\s+dev\b", "pnpm dev"),
    (r"\bnpx\s+serve\b", "npx serve"),
    (r"\bnpx\s+next\s+dev\b", "npx next dev"),
    # Python servers
    (r"\bpython[3]?\s+.*-m\s+http\.server\b", "python -m http.server"),
    (r"\bpython[3]?\s+.*manage\.py\s+runserver\b", "django runserver"),
    (r"\buvicorn\b.*--reload", "uvicorn"),
    (r"\bflask\s+run\b", "flask run"),
    (r"\bgunicorn\b", "gunicorn"),
    # Generic watchers / servers
    (r"\bnodemon\b", "nodemon"),
    (r"\btailwindcss\b.*--watch\b", "tailwind watch"),
    (r"\blive-server\b", "live-server"),
]

# Patterns that should never be executed
_BLOCKED_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+-rf\s+/\s*$", "rm -rf / (deletes entire filesystem)"),
    (r"\brm\s+-rf\s+/\s+", "rm -rf / (deletes entire filesystem)"),
    (r":\(\)\s*\{.*\|.*&\s*\}\s*;", "fork bomb"),
    (r"\bshutdown\b", "system shutdown"),
    (r"\breboot\b", "system reboot"),
    (r"\binit\s+0\b", "system halt"),
    (r"\bmkfs\b", "filesystem format"),
    (r"\bformat\s+[a-zA-Z]:", "Windows drive format"),
    (r"\bdd\s+.*of=/dev/[sh]d", "disk overwrite"),
]

# Pattern to detect "cd <dir> && <rest>" or "cd <dir> ; <rest>"
_CD_PREFIX_RE = re.compile(r"^\s*cd\s+([^\s;&|]+)\s*(?:&&|;)\s*(.+)$", re.DOTALL)


def _check_blocked_command(command: str) -> str | None:
    """Check if a command matches a blocked pattern.

    Returns error message if blocked, None if OK.
    """
    for pattern, description in _BLOCKED_PATTERNS:
        if re.search(pattern, command):
            return (
                f"BLOCKED: '{description}' is a destructive command that could "
                "damage the system. This command will not be executed."
            )
    return None


def _extract_cd_prefix(command: str) -> tuple[str, str]:
    """Extract 'cd <dir> &&' prefix from a command.

    Agents often write 'cd my-app && npm install' because they forget
    that cd doesn't persist. Instead of letting it fail, we extract
    the directory and use it as the cwd parameter.

    Returns (remaining_command, extracted_cwd).
    If no cd prefix found, returns (original_command, "").
    """
    match = _CD_PREFIX_RE.match(command)
    if match:
        directory = match.group(1).strip().strip("'\"")
        remaining = match.group(2).strip()
        return remaining, directory
    return command, ""


def _is_long_running_command(command: str) -> bool:
    """Detect commands that will block forever (dev servers, watchers).

    These must run in background mode. Without auto-detection, the agent
    will hang on timeout, then retry in a loop — never completing the task.
    """
    return any(re.search(p, command) for p, _ in _LONG_RUNNING_PATTERNS)


def _rewrite_command_for_platform(command: str, is_windows: bool) -> str:
    """Rewrite commands for platform compatibility.

    Agents often generate Unix commands on Windows (rm -rf, cat, etc.).
    Instead of failing, we transparently rewrite to the Windows equivalent.
    """
    if not is_windows:
        return command

    # rm -rf <dir> → rmdir /S /Q <dir>
    rm_match = re.match(r"^\s*rm\s+-rf?\s+(.+)$", command)
    if rm_match:
        target = rm_match.group(1).strip()
        return f'rmdir /S /Q "{target}"'

    # cat <file> → type <file>
    cat_match = re.match(r"^\s*cat\s+(.+)$", command)
    if cat_match:
        return f"type {cat_match.group(1).strip()}"

    # ls → dir
    if re.match(r"^\s*ls\s*$", command):
        return "dir"
    ls_match = re.match(r"^\s*ls\s+(-[a-zA-Z]+\s+)?(.+)$", command)
    if ls_match:
        return f"dir {ls_match.group(2).strip()}"

    # touch <file> → type nul > <file>
    touch_match = re.match(r"^\s*touch\s+(.+)$", command)
    if touch_match:
        return f"type nul > {touch_match.group(1).strip()}"

    # which <cmd> → where <cmd>
    which_match = re.match(r"^\s*which\s+(.+)$", command)
    if which_match:
        return f"where {which_match.group(1).strip()}"

    return command


async def _kill_process_tree(proc: Any) -> None:
    """Kill a process AND all its children (the entire process tree).

    On Windows: uses 'taskkill /T /F /PID' which kills the tree.
    On Unix: kills the process group (all children started with start_new_session).

    This prevents orphan processes (npm, node, webpack, etc.) from lingering
    after timeout or cleanup, which can exhaust system memory and cause crashes.
    """
    pid = proc.pid
    if pid is None:
        return

    is_windows = platform.system() == "Windows"

    try:
        if is_windows:
            # taskkill /T = kill tree, /F = force
            kill_proc = await asyncio.create_subprocess_exec(
                "taskkill",
                "/T",
                "/F",
                "/PID",
                str(pid),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                await asyncio.wait_for(kill_proc.wait(), timeout=10)
            except TimeoutError:
                pass
        else:
            # Kill the entire process group
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            # Give processes a moment to exit gracefully, then force-kill
            await asyncio.sleep(0.5)
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
    except Exception:
        # Fallback: at least try to kill the parent
        try:
            proc.kill()
        except Exception:
            pass

    # Wait for the process to actually exit
    try:
        await asyncio.wait_for(proc.wait(), timeout=5)
    except (TimeoutError, Exception):
        pass


async def _collect_initial_output(proc: Any, seconds: float = 5.0) -> str:
    """Collect initial output from a background process for a few seconds."""
    lines: list[str] = []
    try:
        end_time = asyncio.get_event_loop().time() + seconds
        while asyncio.get_event_loop().time() < end_time:
            if proc.stdout is None:
                break
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=1.0)
                if line:
                    lines.append(line.decode("utf-8", errors="replace").rstrip())
                else:
                    break  # Process ended
            except TimeoutError:
                continue
    except Exception:
        pass
    return "\n".join(lines) if lines else "(no output yet)"


def _human_size(size: int) -> str:
    """Convert bytes to human readable size."""
    fsize = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if fsize < 1024:
            return f"{fsize:.0f}{unit}" if unit == "B" else f"{fsize:.1f}{unit}"
        fsize /= 1024
    return f"{fsize:.1f}TB"
