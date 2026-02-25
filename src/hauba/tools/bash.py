"""Bash tool — execute shell commands in a subprocess."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import structlog

from hauba.core.types import ToolResult
from hauba.tools.base import BaseTool

logger = structlog.get_logger()

DEFAULT_TIMEOUT = 120  # seconds
MAX_OUTPUT_LENGTH = 50000  # chars


class BashTool(BaseTool):
    """Execute shell commands safely with timeout."""

    name = "bash"
    description = "Execute a shell command and return stdout/stderr. Use this for running programs, installing packages, building projects, and any system operations."

    def __init__(self, cwd: str | None = None, timeout: int = DEFAULT_TIMEOUT) -> None:
        self._cwd = cwd
        self._timeout = timeout

    def _parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute.",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory for the command (optional).",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 120).",
                },
            },
            "required": ["command"],
        }

    async def execute(self, **kwargs: object) -> ToolResult:
        """Execute a bash command.

        Args:
            command: The shell command to run.
            cwd: Working directory (optional override).
            timeout: Timeout in seconds (optional override).
        """
        command = str(kwargs.get("command", ""))
        if not command:
            return ToolResult(tool_name=self.name, success=False, error="No command provided")

        cwd = str(kwargs.get("cwd", "")) or self._cwd
        timeout = int(kwargs.get("timeout", self._timeout))

        logger.info("tool.bash.execute", command=command[:200], cwd=cwd)

        try:
            # Platform-aware shell execution
            if sys.platform == "win32":
                # On Windows, prefer Git Bash if available, else cmd.exe
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd or None,
                    # Use cmd.exe on Windows — Git Bash commands still work via shell
                )
            else:
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd or None,
                )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            stdout_str = stdout.decode("utf-8", errors="replace")[:MAX_OUTPUT_LENGTH]
            stderr_str = stderr.decode("utf-8", errors="replace")[:MAX_OUTPUT_LENGTH]

            exit_code = proc.returncode or 0
            success = exit_code == 0

            output = stdout_str
            if stderr_str:
                if success:
                    # Some tools write to stderr even on success (e.g., npm, pip)
                    output = f"{stdout_str}\n{stderr_str}" if stdout_str else stderr_str
                else:
                    output = (
                        f"{stdout_str}\n--- STDERR ---\n{stderr_str}" if stdout_str else stderr_str
                    )

            logger.info("tool.bash.result", exit_code=exit_code, output_len=len(output))

            return ToolResult(
                tool_name=self.name,
                success=success,
                output=output,
                error=stderr_str if not success else "",
                exit_code=exit_code,
            )

        except TimeoutError:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Command timed out after {timeout}s",
                exit_code=-1,
            )
        except OSError as exc:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Failed to execute: {exc}",
                exit_code=-1,
            )
