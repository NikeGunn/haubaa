"""Tests for BashTool."""

from __future__ import annotations

import pytest

from hauba.tools.bash import BashTool


@pytest.mark.asyncio
async def test_echo_command() -> None:
    tool = BashTool()
    result = await tool.execute(command="echo hello")
    assert result.success
    assert "hello" in result.output


@pytest.mark.asyncio
async def test_failing_command() -> None:
    tool = BashTool()
    result = await tool.execute(command="exit 1")
    assert not result.success
    assert result.exit_code == 1


@pytest.mark.asyncio
async def test_timeout() -> None:
    tool = BashTool(timeout=1)
    result = await tool.execute(command="sleep 10", timeout=1)
    assert not result.success
    assert "timed out" in result.error.lower()


@pytest.mark.asyncio
async def test_no_command() -> None:
    tool = BashTool()
    result = await tool.execute()
    assert not result.success
    assert "No command" in result.error
