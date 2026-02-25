"""Git tool — git operations via subprocess."""

from __future__ import annotations

from typing import Any

import structlog

from hauba.core.types import ToolResult
from hauba.tools.base import BaseTool
from hauba.tools.bash import BashTool

logger = structlog.get_logger()


class GitTool(BaseTool):
    """Git operations: status, add, commit, push, pull, diff, log."""

    name = "git"
    description = (
        "Execute git operations like status, add, commit, push, pull, diff, log, and init."
    )

    def __init__(self, cwd: str | None = None) -> None:
        self._bash = BashTool(cwd=cwd)

    def _parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["status", "add", "commit", "push", "pull", "diff", "log", "init"],
                    "description": "The git operation to perform.",
                },
                "files": {
                    "type": "string",
                    "description": "Files to add (for 'add' action). Default '.'",
                },
                "message": {
                    "type": "string",
                    "description": "Commit message (for 'commit' action).",
                },
                "args": {
                    "type": "string",
                    "description": "Additional git arguments.",
                },
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs: object) -> ToolResult:
        """Execute a git operation."""
        action = str(kwargs.get("action", ""))
        if not action:
            return ToolResult(tool_name=self.name, success=False, error="No action specified")

        cmd = self._build_command(action, kwargs)
        if cmd is None:
            return ToolResult(tool_name=self.name, success=False, error=f"Unknown action: {action}")

        result = await self._bash.execute(command=cmd)
        return ToolResult(
            tool_name=self.name,
            success=result.success,
            output=result.output,
            error=result.error,
            exit_code=result.exit_code,
        )

    def _build_command(self, action: str, kwargs: dict) -> str | None:
        """Build the git command string."""
        if action == "status":
            return "git status"
        elif action == "add":
            files = str(kwargs.get("files", "."))
            return f"git add {files}"
        elif action == "commit":
            message = str(kwargs.get("message", "Auto-commit by Hauba"))
            safe_msg = message.replace('"', '\\"')
            return f'git commit -m "{safe_msg}"'
        elif action == "push":
            return "git push"
        elif action == "pull":
            return "git pull"
        elif action == "diff":
            return "git diff"
        elif action == "log":
            return "git log --oneline -10"
        elif action == "init":
            return "git init"
        else:
            return None
