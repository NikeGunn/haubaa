"""Tests for GitTool."""

from __future__ import annotations

import pytest

from hauba.tools.git import GitTool


@pytest.mark.asyncio
async def test_git_status(tmp_path) -> None:
    """Test git status in a git repo."""
    tool = GitTool(cwd=str(tmp_path))
    # Init a repo first
    await tool.execute(action="init")
    result = await tool.execute(action="status")
    assert result.success


@pytest.mark.asyncio
async def test_unknown_action() -> None:
    tool = GitTool()
    result = await tool.execute(action="unknown_action")
    assert not result.success
    assert "Unknown action" in result.error


@pytest.mark.asyncio
async def test_no_action() -> None:
    tool = GitTool()
    result = await tool.execute()
    assert not result.success
