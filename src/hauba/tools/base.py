"""Base tool interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from hauba.core.types import ToolResult


class BaseTool(ABC):
    """Base class for all Hauba tools."""

    name: str = ""
    description: str = ""

    @abstractmethod
    async def execute(self, **kwargs: object) -> ToolResult:
        """Execute the tool with given arguments."""
        ...
