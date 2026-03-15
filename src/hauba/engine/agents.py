"""Agent definitions — backward compatibility shim for V3.

In V4, we use a single-agent architecture with a custom agent loop.
No more multi-agent handoffs — one powerful agent with all tools.
This module preserves the create_agent_team API for backward compat.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

logger = structlog.get_logger()


async def _run_shell(command: str) -> str:
    """Run a shell command in a local subprocess."""
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


def create_agent_team(
    *,
    model: str,
    mcp_servers: list[Any] | None = None,
    skill_context: str = "",
    working_directory: str = ".",
) -> Any:
    """Create agent team (V3 compatibility).

    In V4, use AgentEngine directly instead. This function is
    kept for backward compatibility with tests and other code.
    Returns None since we no longer use the Agent SDK.
    """
    logger.warning(
        "agents.v3_compat",
        msg="create_agent_team is deprecated in V4. Use AgentEngine directly.",
    )
    return None
