"""Hauba V4 function tools — backward compatibility shim.

The tool system has been moved to tool_registry.py with a unified
ToolRegistry class. This module provides backward-compatible imports
for code that still references build_function_tools().
"""

from __future__ import annotations

from typing import Any


def build_function_tools() -> list[Any]:
    """Build function tools (V3 compatibility).

    In V4, tools are managed by ToolRegistry directly.
    This returns an empty list since the Agent SDK is no longer used.
    """
    return []
