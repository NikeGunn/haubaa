"""Phase 3 Integration Tests — Computer Use + Browser + Replay pipeline."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from rich.console import Console

from hauba.agents.computer_use import ComputerUseAgent
from hauba.core.config import ConfigManager
from hauba.core.events import EventEmitter
from hauba.core.replay import ReplayRecorder
from hauba.core.types import LLMResponse, ToolResult
from hauba.ui.replay import ReplayPlayer


@pytest.fixture
def config(tmp_path: Path) -> ConfigManager:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    return ConfigManager(settings_path)


@pytest.fixture
def events() -> EventEmitter:
    return EventEmitter()


async def test_computer_use_with_replay_recording(
    config: ConfigManager, events: EventEmitter, tmp_path: Path
) -> None:
    """Full pipeline: ComputerUseAgent executes while ReplayRecorder captures events.

    Then ReplayPlayer plays them back.
    """
    # 1. Set up recorder
    recorder = ReplayRecorder(task_id="integration-test", output_dir=tmp_path)
    recorder.subscribe(events)

    # 2. Set up agent with mocked screen + LLM
    agent = ComputerUseAgent(config=config, events=events)

    capture_result = ToolResult(
        tool_name="screen", success=True, output="Screenshot saved: /tmp/shot.png"
    )
    agent._screen.execute = AsyncMock(return_value=capture_result)
    agent._delay = 0

    done_response = LLMResponse(
        content='{"action": "done", "reasoning": "Task complete"}',
        model="test",
    )
    agent._llm.complete = AsyncMock(return_value=done_response)

    # 3. Run the agent (full lifecycle: deliberate → execute → review)
    result = await agent.run("check the screen")
    assert result.success

    # 4. Verify recorder captured events
    assert recorder.entry_count > 0
    recorder.close()

    # 5. Load and verify replay entries
    entries = ReplayRecorder.load(recorder.path)
    assert len(entries) > 0

    topics = [e.topic for e in entries]
    assert "task.started" in topics
    assert "task.completed" in topics

    # 6. Play back via ReplayPlayer
    console = Console(file=StringIO(), width=120, color_system=None)
    player = ReplayPlayer(console=console)
    played = await player.play(recorder.path, speed=100.0)
    assert played == len(entries)


async def test_browser_tool_mocked_workflow(tmp_path: Path) -> None:
    """Test browser navigate → extract → screenshot sequence (all mocked)."""
    from hauba.tools.browser import BrowserTool

    tool = BrowserTool()

    # Mock the browser page
    mock_page = AsyncMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_page.goto = AsyncMock(return_value=mock_response)
    mock_page.title = AsyncMock(return_value="Example Page")
    mock_page.content = AsyncMock(return_value="<html><body><h1>Hello World</h1></body></html>")
    mock_page.evaluate = AsyncMock(return_value="Hello World")
    mock_page.screenshot = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()

    tool._ensure_browser = AsyncMock(return_value=mock_page)

    # Navigate
    result = await tool.execute(action="navigate", url="https://example.com")
    assert result.success
    assert "200" in result.output

    # Extract full page
    result = await tool.execute(action="extract")
    assert result.success
    assert "Hello World" in result.output

    # Screenshot
    shot_path = str(tmp_path / "test_shot.png")
    result = await tool.execute(action="screenshot", path=shot_path)
    assert result.success
    assert "Screenshot saved" in result.output


async def test_web_search_integration() -> None:
    """Test web search tool with mocked HTTP response."""
    from unittest.mock import patch

    from hauba.tools.web import WebSearchTool

    tool = WebSearchTool()

    fake_html = """
    <div class="result">
        <a class="result__a" href="https://python.org">Python Official</a>
        <a class="result__snippet">The official Python website.</a>
    </div>
    """
    mock_resp = MagicMock()
    mock_resp.text = fake_html
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("hauba.tools.web.httpx.AsyncClient", return_value=mock_client):
        import os

        orig = os.environ.pop("BRAVE_API_KEY", None)
        try:
            result = await tool.execute(query="python programming")
        finally:
            if orig is not None:
                os.environ["BRAVE_API_KEY"] = orig

    assert result.success
    assert "Python Official" in result.output
