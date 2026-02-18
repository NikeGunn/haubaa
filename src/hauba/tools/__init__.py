"""Hauba tools module — bash, files, git, and optional Phase 3 tools."""

from hauba.tools.bash import BashTool
from hauba.tools.files import FileTool
from hauba.tools.git import GitTool

__all__ = ["BashTool", "FileTool", "GitTool"]

# Phase 3: Conditionally export optional tools
try:
    from hauba.tools.browser import BrowserTool

    __all__.append("BrowserTool")
except Exception:
    BrowserTool = None  # type: ignore[assignment,misc]

try:
    from hauba.tools.screen import ScreenTool

    __all__.append("ScreenTool")
except Exception:
    ScreenTool = None  # type: ignore[assignment,misc]

try:
    from hauba.tools.web import WebSearchTool

    __all__.append("WebSearchTool")
except Exception:
    WebSearchTool = None  # type: ignore[assignment,misc]
