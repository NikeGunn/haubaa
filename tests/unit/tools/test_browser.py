"""Tests for BrowserTool — Playwright-based browser automation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hauba.tools.browser import BrowserTool


@pytest.fixture
def browser_tool():
    return BrowserTool()


# --- Graceful degradation ---


async def test_browser_unavailable_returns_error(browser_tool):
    """When Playwright is not installed, returns ToolNotAvailableError message."""
    with patch("hauba.tools.browser.PLAYWRIGHT_AVAILABLE", False):
        result = await browser_tool.execute(action="navigate", url="https://example.com")
        assert not result.success
        assert "Playwright not installed" in result.error


# --- Action validation ---


async def test_unknown_action_returns_error(browser_tool):
    result = await browser_tool.execute(action="fly")
    assert not result.success
    assert "Unknown browser action" in result.error


# --- Navigate ---


async def test_navigate_requires_url(browser_tool):
    with patch.object(browser_tool, "_ensure_browser", new_callable=AsyncMock):
        result = await browser_tool.execute(action="navigate")
        assert not result.success
        assert "URL required" in result.error


async def test_navigate_success(browser_tool):
    mock_page = AsyncMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_page.goto = AsyncMock(return_value=mock_response)

    with patch.object(
        browser_tool, "_ensure_browser", new_callable=AsyncMock, return_value=mock_page
    ):
        result = await browser_tool.execute(action="navigate", url="https://example.com")
        assert result.success
        assert "200" in result.output
        mock_page.goto.assert_called_once()


# --- Click ---


async def test_click_requires_selector(browser_tool):
    mock_page = AsyncMock()
    with patch.object(
        browser_tool, "_ensure_browser", new_callable=AsyncMock, return_value=mock_page
    ):
        result = await browser_tool.execute(action="click")
        assert not result.success
        assert "Selector required" in result.error


async def test_click_success(browser_tool):
    mock_page = AsyncMock()
    with patch.object(
        browser_tool, "_ensure_browser", new_callable=AsyncMock, return_value=mock_page
    ):
        result = await browser_tool.execute(action="click", selector="#btn")
        assert result.success
        assert "Clicked" in result.output


# --- Type ---


async def test_type_requires_selector_and_text(browser_tool):
    mock_page = AsyncMock()
    with patch.object(
        browser_tool, "_ensure_browser", new_callable=AsyncMock, return_value=mock_page
    ):
        result = await browser_tool.execute(action="type", selector="#input")
        assert not result.success
        assert "Selector and text required" in result.error


async def test_type_success(browser_tool):
    mock_page = AsyncMock()
    with patch.object(
        browser_tool, "_ensure_browser", new_callable=AsyncMock, return_value=mock_page
    ):
        result = await browser_tool.execute(action="type", selector="#input", text="hello")
        assert result.success
        assert "Typed" in result.output
        assert mock_page.fill.call_count == 2  # clear + fill


# --- Extract ---


async def test_extract_full_page(browser_tool):
    mock_page = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value="hello world")
    with patch.object(
        browser_tool, "_ensure_browser", new_callable=AsyncMock, return_value=mock_page
    ):
        result = await browser_tool.execute(action="extract")
        assert result.success
        assert "hello world" in result.output


async def test_extract_with_selector(browser_tool):
    mock_el = AsyncMock()
    mock_el.text_content = AsyncMock(return_value="Item 1")
    mock_page = AsyncMock()
    mock_page.query_selector_all = AsyncMock(return_value=[mock_el])
    with patch.object(
        browser_tool, "_ensure_browser", new_callable=AsyncMock, return_value=mock_page
    ):
        result = await browser_tool.execute(action="extract", selector=".item")
        assert result.success
        assert "Item 1" in result.output


# --- Screenshot ---


async def test_screenshot_success(browser_tool, tmp_path):
    mock_page = AsyncMock()
    out_path = str(tmp_path / "shot.png")
    with patch.object(
        browser_tool, "_ensure_browser", new_callable=AsyncMock, return_value=mock_page
    ):
        result = await browser_tool.execute(action="screenshot", path=out_path)
        assert result.success
        assert "Screenshot saved" in result.output
        mock_page.screenshot.assert_called_once()


# --- Wait ---


async def test_wait_with_selector(browser_tool):
    mock_page = AsyncMock()
    with patch.object(
        browser_tool, "_ensure_browser", new_callable=AsyncMock, return_value=mock_page
    ):
        result = await browser_tool.execute(action="wait", selector="#loading", timeout=100)
        assert result.success
        mock_page.wait_for_selector.assert_called_once()


async def test_wait_without_selector(browser_tool):
    mock_page = AsyncMock()
    with patch.object(
        browser_tool, "_ensure_browser", new_callable=AsyncMock, return_value=mock_page
    ):
        result = await browser_tool.execute(action="wait", timeout=10)
        assert result.success
        assert "Waited" in result.output
