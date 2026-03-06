"""MCP server management for Hauba V3.

Manages Playwright MCP and other MCP server connections for agent tools.
Uses the OpenAI Agents SDK's MCPServerStdio for subprocess-based MCP.
"""

from __future__ import annotations

import shutil
from typing import Any

import structlog

logger = structlog.get_logger()


def _find_npx() -> str | None:
    """Find the npx command on the system."""
    return shutil.which("npx")


def create_playwright_mcp(
    *,
    headless: bool = True,
    viewport: str = "1280x720",
) -> Any | None:
    """Create a Playwright MCP server instance.

    Requires Node.js and npx to be installed. The @playwright/mcp package
    is automatically fetched via npx on first use.

    Args:
        headless: Run browser in headless mode (default True).
        viewport: Browser viewport size (default "1280x720").

    Returns:
        MCPServerStdio instance or None if npx not available.
    """
    try:
        from agents.mcp import MCPServerStdio
    except ImportError:
        logger.warning("mcp.agents_sdk_not_installed")
        return None

    npx = _find_npx()
    if not npx:
        logger.warning("mcp.npx_not_found", hint="Install Node.js to enable browser automation")
        return None

    args = ["-y", "@playwright/mcp@latest"]
    if headless:
        args.append("--headless")
    args.extend(["--viewport-size", viewport])

    return MCPServerStdio(
        name="playwright",
        params={
            "command": npx,
            "args": args,
        },
        cache_tools_list=True,
    )


def create_filesystem_mcp(workspace_dir: str) -> Any | None:
    """Create a filesystem MCP server for sandboxed file access.

    Args:
        workspace_dir: The directory to expose to the agent.

    Returns:
        MCPServerStdio instance or None if npx not available.
    """
    try:
        from agents.mcp import MCPServerStdio
    except ImportError:
        return None

    npx = _find_npx()
    if not npx:
        return None

    return MCPServerStdio(
        name="filesystem",
        params={
            "command": npx,
            "args": ["-y", "@modelcontextprotocol/server-filesystem", workspace_dir],
        },
        cache_tools_list=True,
    )
