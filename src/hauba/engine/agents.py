"""Agent definitions for Hauba V3.

Creates the multi-agent team powered by OpenAI Agents SDK:
- DirectorAgent: Plans, delegates, coordinates
- CoderAgent: Writes code via shell + file tools
- BrowserAgent: Web automation via Playwright MCP
- ReviewerAgent: Code review and testing
"""

from __future__ import annotations

from typing import Any

import structlog

from hauba.engine.prompts import (
    BROWSER_PROMPT,
    CODER_PROMPT,
    REVIEWER_PROMPT,
    build_skill_context,
)
from hauba.engine.tools import build_function_tools

logger = structlog.get_logger()


async def _run_shell(command: str) -> str:
    """Run a shell command in a local subprocess."""
    import asyncio

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=None,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        output = stdout.decode("utf-8", errors="replace")
        if stderr:
            err = stderr.decode("utf-8", errors="replace")
            if err.strip():
                output += f"\nSTDERR:\n{err}"
        if proc.returncode != 0:
            output += f"\n[exit code: {proc.returncode}]"
        return output[:50000]
    except TimeoutError:
        return "[Command timed out after 120 seconds]"
    except Exception as exc:
        return f"[Shell error: {exc}]"


def _build_shell_tool() -> Any | None:
    """Create a shell tool as a @function_tool (works with all models)."""
    try:
        from agents import function_tool

        @function_tool
        async def shell(command: str) -> str:
            """Run a shell command on the local machine. Use this to execute code,
            install packages, run tests, read/write files, use git, and perform
            any system operations. Returns stdout, stderr, and exit code."""
            return await _run_shell(command)

        return shell
    except ImportError:
        return None


def create_agent_team(
    *,
    model: str,
    mcp_servers: list[Any] | None = None,
    skill_context: str = "",
    working_directory: str = ".",
) -> Any:
    """Create the full Hauba agent team.

    Args:
        model: The LLM model identifier (e.g. "gpt-4o", "litellm/anthropic/claude-sonnet-4-5-20250514").
        mcp_servers: List of MCP server instances (Playwright, Filesystem, etc.).
        skill_context: Matched skill text to inject into Director's prompt.
        working_directory: The working directory for file operations.

    Returns:
        The DirectorAgent (entry point for the team).
    """
    try:
        from agents import Agent
    except ImportError:
        raise RuntimeError(
            "OpenAI Agents SDK not installed. Run: pip install 'openai-agents[litellm]'"
        )

    mcp_servers = mcp_servers or []

    # Separate MCP servers by purpose
    playwright_servers = [s for s in mcp_servers if getattr(s, "name", "") == "playwright"]
    filesystem_servers = [s for s in mcp_servers if getattr(s, "name", "") == "filesystem"]

    # --- Build tools ---
    shell_tool = _build_shell_tool()
    function_tools = build_function_tools()

    # --- CoderAgent ---
    coder_tools: list[Any] = []
    if shell_tool:
        coder_tools.append(shell_tool)
    coder_mcp = filesystem_servers  # Filesystem MCP for file access

    coder_agent = Agent(
        name="coder",
        instructions=CODER_PROMPT,
        model=model,
        tools=coder_tools,
        mcp_servers=coder_mcp,
    )

    # --- BrowserAgent ---
    browser_agent = Agent(
        name="browser",
        instructions=BROWSER_PROMPT,
        model=model,
        mcp_servers=playwright_servers,
    )

    # --- ReviewerAgent ---
    reviewer_tools: list[Any] = []
    if shell_tool:
        reviewer_tools.append(shell_tool)

    reviewer_agent = Agent(
        name="reviewer",
        instructions=REVIEWER_PROMPT,
        model=model,
        tools=reviewer_tools,
    )

    # --- DirectorAgent (orchestrator) ---
    director_tools: list[Any] = list(function_tools)

    # Add specialists as handoff targets
    handoffs: list[Any] = [coder_agent, browser_agent, reviewer_agent]

    director_prompt = build_skill_context(skill_context)

    director_agent = Agent(
        name="director",
        instructions=director_prompt,
        model=model,
        tools=director_tools,
        handoffs=handoffs,
    )

    logger.info(
        "agents.team_created",
        model=model,
        mcp_count=len(mcp_servers),
        tool_count=len(director_tools),
        handoff_count=len(handoffs),
    )

    return director_agent
