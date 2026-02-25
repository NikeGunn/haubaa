"""File tool — read, write, edit files and directories."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import structlog

from hauba.core.types import ToolResult
from hauba.tools.base import BaseTool

logger = structlog.get_logger()


class FileTool(BaseTool):
    """Read, write, edit, and manage files."""

    name = "files"
    description = "Read, write, edit files and create directories. Use action='write' to create new files, action='read' to read existing files, action='edit' for search-and-replace edits, action='mkdir' to create directories."

    def _parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "append", "edit", "mkdir", "list", "exists", "delete"],
                    "description": "The file operation to perform.",
                },
                "path": {
                    "type": "string",
                    "description": "File or directory path.",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (for write/append actions).",
                },
                "old_text": {
                    "type": "string",
                    "description": "Text to find (for edit action — search and replace).",
                },
                "new_text": {
                    "type": "string",
                    "description": "Replacement text (for edit action — search and replace).",
                },
            },
            "required": ["action", "path"],
        }

    async def execute(self, **kwargs: object) -> ToolResult:
        """Execute a file operation.

        Args:
            action: read | write | append | edit | mkdir | list | exists | delete
            path: File or directory path.
            content: Content to write (for write/append).
            old_text: Text to find (for edit).
            new_text: Replacement text (for edit).
        """
        action = str(kwargs.get("action", ""))
        path_str = str(kwargs.get("path", ""))

        if not action or not path_str:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="Both 'action' and 'path' are required",
            )

        path = Path(path_str)

        try:
            if action == "read":
                return await self._read(path)
            elif action == "write":
                content = str(kwargs.get("content", ""))
                return await self._write(path, content)
            elif action == "append":
                content = str(kwargs.get("content", ""))
                return await self._append(path, content)
            elif action == "edit":
                old_text = str(kwargs.get("old_text", ""))
                new_text = str(kwargs.get("new_text", ""))
                return await self._edit(path, old_text, new_text)
            elif action == "mkdir":
                return await self._mkdir(path)
            elif action == "list":
                return await self._list(path)
            elif action == "exists":
                return await self._exists(path)
            elif action == "delete":
                return await self._delete(path)
            else:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    error=f"Unknown action: {action}",
                )
        except OSError as exc:
            return ToolResult(tool_name=self.name, success=False, error=str(exc))

    async def _read(self, path: Path) -> ToolResult:
        if not path.exists():
            return ToolResult(tool_name=self.name, success=False, error=f"File not found: {path}")
        content = path.read_text(encoding="utf-8")
        return ToolResult(tool_name=self.name, success=True, output=content)

    async def _write(self, path: Path, content: str) -> ToolResult:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write
        tmp_fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(content)
            Path(tmp_path).replace(path)
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise
        return ToolResult(tool_name=self.name, success=True, output=f"Written: {path}")

    async def _append(self, path: Path, content: str) -> ToolResult:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
        return ToolResult(tool_name=self.name, success=True, output=f"Appended to: {path}")

    async def _edit(self, path: Path, old_text: str, new_text: str) -> ToolResult:
        """Search-and-replace edit on a file."""
        if not path.exists():
            return ToolResult(tool_name=self.name, success=False, error=f"File not found: {path}")
        if not old_text:
            return ToolResult(
                tool_name=self.name, success=False, error="old_text is required for edit"
            )

        content = path.read_text(encoding="utf-8")
        if old_text not in content:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Text not found in {path}. The exact text to replace was not found.",
            )

        new_content = content.replace(old_text, new_text, 1)

        # Atomic write
        tmp_fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(new_content)
            Path(tmp_path).replace(path)
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise

        return ToolResult(tool_name=self.name, success=True, output=f"Edited: {path}")

    async def _mkdir(self, path: Path) -> ToolResult:
        path.mkdir(parents=True, exist_ok=True)
        return ToolResult(tool_name=self.name, success=True, output=f"Created: {path}")

    async def _list(self, path: Path) -> ToolResult:
        if not path.exists():
            return ToolResult(tool_name=self.name, success=False, error=f"Not found: {path}")
        if path.is_file():
            return ToolResult(tool_name=self.name, success=True, output=str(path))
        entries = sorted(p.name for p in path.iterdir())
        return ToolResult(tool_name=self.name, success=True, output="\n".join(entries))

    async def _exists(self, path: Path) -> ToolResult:
        exists = path.exists()
        return ToolResult(tool_name=self.name, success=True, output=str(exists))

    async def _delete(self, path: Path) -> ToolResult:
        if not path.exists():
            return ToolResult(tool_name=self.name, success=True, output="Already deleted")
        if path.is_file():
            path.unlink()
        else:
            import shutil

            shutil.rmtree(path)
        return ToolResult(tool_name=self.name, success=True, output=f"Deleted: {path}")
