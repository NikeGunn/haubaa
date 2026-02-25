"""Base tool interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from hauba.core.types import ToolResult


class BaseTool(ABC):
    """Base class for all Hauba tools."""

    name: str = ""
    description: str = ""

    @abstractmethod
    async def execute(self, **kwargs: object) -> ToolResult:
        """Execute the tool with given arguments."""
        ...

    @property
    def tool_schema(self) -> dict[str, Any]:
        """Return OpenAI-compatible tool schema for LLM native function calling.

        Subclasses should override this to provide parameter definitions.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self._parameters_schema(),
            },
        }

    def _parameters_schema(self) -> dict[str, Any]:
        """Return JSON Schema for tool parameters. Override in subclasses."""
        return {"type": "object", "properties": {}, "required": []}
