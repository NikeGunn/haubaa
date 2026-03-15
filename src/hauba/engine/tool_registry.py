"""Unified tool registry for Hauba V4.

Core tools inspired by OpenClaw/Pi:
- bash: Run any shell command
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
"""

from __future__ import annotations

import asyncio
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

# Maximum output size to prevent context bloat
MAX_OUTPUT_SIZE = 100_000
# Shell command timeout
SHELL_TIMEOUT = 120


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

        try:
            result = await tool.execute_fn(**params)
            # Truncate very long output
            if isinstance(result, ToolResult) and len(result.output) > MAX_OUTPUT_SIZE:
                result.output = (
                    result.output[:MAX_OUTPUT_SIZE]
                    + f"\n\n[Output truncated at {MAX_OUTPUT_SIZE} chars]"
                )
            return result
        except TypeError as e:
            return ToolResult.error(f"Invalid parameters for {name}: {e}")
        except Exception as e:
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
            """Run a shell command."""
            try:
                # Resolve working directory
                if cwd:
                    effective_cwd = os.path.abspath(
                        os.path.join(self._working_directory, cwd)
                    )
                    if not os.path.isdir(effective_cwd):
                        return ToolResult.error(
                            f"Directory not found: {cwd} (resolved to {effective_cwd})"
                        )
                else:
                    effective_cwd = self._working_directory

                # Create subprocess
                if platform.system() == "Windows":
                    proc = await asyncio.create_subprocess_shell(
                        command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=effective_cwd,
                    )
                else:
                    proc = await asyncio.create_subprocess_exec(
                        "/bin/bash",
                        "-c",
                        command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=effective_cwd,
                    )

                # Background mode: collect initial output and return immediately
                if background:
                    initial = await _collect_initial_output(proc, seconds=5)
                    pid = proc.pid or 0
                    self._background_processes[pid] = proc
                    return ToolResult.ok(
                        f"Process started in background (PID: {pid}).\n"
                        f"Working directory: {effective_cwd}\n"
                        f"Initial output:\n{initial}\n"
                        f"The process is running. To stop it: "
                        f"bash(command='kill {pid}') on Unix or "
                        f"bash(command='taskkill /F /PID {pid}') on Windows.",
                        pid=pid,
                    )

                # Normal synchronous execution
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )

                output = stdout.decode("utf-8", errors="replace")
                err = stderr.decode("utf-8", errors="replace")

                if err.strip():
                    output += f"\nSTDERR:\n{err}"
                if proc.returncode != 0:
                    output += f"\n[exit code: {proc.returncode}]"

                return ToolResult.ok(output, exit_code=proc.returncode)

            except TimeoutError:
                return ToolResult.error(
                    f"Command timed out after {timeout}s. "
                    "If this is a long-running process (dev server, watcher), "
                    "use background=true instead."
                )
            except Exception as e:
                return ToolResult.error(f"Shell error: {e}")

        self._tools["bash"] = ToolDefinition(
            name="bash",
            description=(
                "Run a shell command. Use for: executing code, installing packages, "
                "running tests, git operations, system commands. "
                "IMPORTANT: Each call runs in an isolated shell — 'cd' does NOT persist. "
                "Use the 'cwd' parameter to run commands in a subdirectory. "
                "For long-running processes (dev servers, watchers), use background=true."
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
        """Kill all background processes. Called when engine stops."""
        for pid, proc in list(self._background_processes.items()):
            try:
                proc.kill()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except TimeoutError:
                    pass  # Process didn't exit cleanly, but we killed it
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
