"""Tests for ScreenTool — pyautogui desktop control."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hauba.tools.screen import ScreenTool


@pytest.fixture
def screen_tool():
    return ScreenTool(allow_control=True)


@pytest.fixture
def screen_tool_no_control():
    return ScreenTool(allow_control=False)


def _screen_patches(mock_pyautogui=None, stop_file=None):
    """Helper to create the standard set of patches for screen tests."""
    patches = [patch("hauba.tools.screen.PYAUTOGUI_AVAILABLE", True)]
    if stop_file is not None:
        patches.append(patch("hauba.tools.screen.EMERGENCY_STOP_FILE", stop_file))
    else:
        patches.append(patch("hauba.tools.screen.EMERGENCY_STOP_FILE", Path("/nonexistent/STOP")))
    if mock_pyautogui is not None:
        patches.append(patch("hauba.tools.screen.pyautogui", mock_pyautogui, create=True))
    return patches


# --- Graceful degradation ---

async def test_screen_unavailable(screen_tool):
    with patch("hauba.tools.screen.PYAUTOGUI_AVAILABLE", False):
        result = await screen_tool.execute(action="capture")
        assert not result.success
        assert "pyautogui not installed" in result.error


# --- Action validation ---

async def test_unknown_action(screen_tool):
    with patch("hauba.tools.screen.PYAUTOGUI_AVAILABLE", True):
        result = await screen_tool.execute(action="teleport")
        assert not result.success
        assert "Unknown screen action" in result.error


# --- Emergency stop ---

async def test_emergency_stop_blocks_actions(screen_tool, tmp_path):
    stop_file = tmp_path / "STOP"
    stop_file.write_text("stop")
    with patch("hauba.tools.screen.PYAUTOGUI_AVAILABLE", True), \
         patch("hauba.tools.screen.EMERGENCY_STOP_FILE", stop_file):
        result = await screen_tool.execute(action="capture")
        assert not result.success
        assert "Emergency stop" in result.error


# --- Capture (always allowed) ---

async def test_capture_success(screen_tool_no_control, tmp_path):
    """Capture is allowed even when control is disabled."""
    mock_screenshot = MagicMock()
    mock_pyautogui = MagicMock()
    mock_pyautogui.screenshot = MagicMock(return_value=mock_screenshot)

    out_path = str(tmp_path / "test.png")
    with patch("hauba.tools.screen.PYAUTOGUI_AVAILABLE", True), \
         patch("hauba.tools.screen.EMERGENCY_STOP_FILE", tmp_path / "NO_STOP"), \
         patch("hauba.tools.screen.pyautogui", mock_pyautogui, create=True):
        result = await screen_tool_no_control.execute(action="capture", path=out_path)
        assert result.success
        assert "Screenshot saved" in result.output
        mock_pyautogui.screenshot.assert_called_once()


# --- Control actions require allow_control ---

async def test_click_blocked_without_control(screen_tool_no_control):
    with patch("hauba.tools.screen.PYAUTOGUI_AVAILABLE", True), \
         patch("hauba.tools.screen.EMERGENCY_STOP_FILE", Path("/nonexistent/STOP")):
        result = await screen_tool_no_control.execute(action="click", x=100, y=200)
        assert not result.success
        assert "Screen control disabled" in result.error


async def test_type_blocked_without_control(screen_tool_no_control):
    with patch("hauba.tools.screen.PYAUTOGUI_AVAILABLE", True), \
         patch("hauba.tools.screen.EMERGENCY_STOP_FILE", Path("/nonexistent/STOP")):
        result = await screen_tool_no_control.execute(action="type", text="hello")
        assert not result.success
        assert "Screen control disabled" in result.error


# --- Click ---

async def test_click_success(screen_tool):
    mock_pyautogui = MagicMock()
    mock_pyautogui.size = MagicMock(return_value=(1920, 1080))
    mock_pyautogui.click = MagicMock()

    with patch("hauba.tools.screen.PYAUTOGUI_AVAILABLE", True), \
         patch("hauba.tools.screen.EMERGENCY_STOP_FILE", Path("/nonexistent/STOP")), \
         patch("hauba.tools.screen.pyautogui", mock_pyautogui, create=True):
        result = await screen_tool.execute(action="click", x=100, y=200)
        assert result.success
        assert "Clicked" in result.output
        mock_pyautogui.click.assert_called_once_with(100, 200, button="left")


async def test_click_out_of_bounds(screen_tool):
    mock_pyautogui = MagicMock()
    mock_pyautogui.size = MagicMock(return_value=(1920, 1080))

    with patch("hauba.tools.screen.PYAUTOGUI_AVAILABLE", True), \
         patch("hauba.tools.screen.EMERGENCY_STOP_FILE", Path("/nonexistent/STOP")), \
         patch("hauba.tools.screen.pyautogui", mock_pyautogui, create=True):
        result = await screen_tool.execute(action="click", x=5000, y=200)
        assert not result.success
        assert "out of screen bounds" in result.error


# --- Type ---

async def test_type_success(screen_tool):
    mock_pyautogui = MagicMock()
    with patch("hauba.tools.screen.PYAUTOGUI_AVAILABLE", True), \
         patch("hauba.tools.screen.EMERGENCY_STOP_FILE", Path("/nonexistent/STOP")), \
         patch("hauba.tools.screen.pyautogui", mock_pyautogui, create=True):
        result = await screen_tool.execute(action="type", text="hello world")
        assert result.success
        assert "11 characters" in result.output


async def test_type_requires_text(screen_tool):
    mock_pyautogui = MagicMock()
    with patch("hauba.tools.screen.PYAUTOGUI_AVAILABLE", True), \
         patch("hauba.tools.screen.EMERGENCY_STOP_FILE", Path("/nonexistent/STOP")), \
         patch("hauba.tools.screen.pyautogui", mock_pyautogui, create=True):
        result = await screen_tool.execute(action="type")
        assert not result.success
        assert "Text required" in result.error


# --- Scroll ---

async def test_scroll_success(screen_tool):
    mock_pyautogui = MagicMock()
    with patch("hauba.tools.screen.PYAUTOGUI_AVAILABLE", True), \
         patch("hauba.tools.screen.EMERGENCY_STOP_FILE", Path("/nonexistent/STOP")), \
         patch("hauba.tools.screen.pyautogui", mock_pyautogui, create=True):
        result = await screen_tool.execute(action="scroll", clicks=5)
        assert result.success
        assert "5 clicks" in result.output


# --- Hotkey ---

async def test_hotkey_success(screen_tool):
    mock_pyautogui = MagicMock()
    with patch("hauba.tools.screen.PYAUTOGUI_AVAILABLE", True), \
         patch("hauba.tools.screen.EMERGENCY_STOP_FILE", Path("/nonexistent/STOP")), \
         patch("hauba.tools.screen.pyautogui", mock_pyautogui, create=True):
        result = await screen_tool.execute(action="hotkey", keys="ctrl,c")
        assert result.success
        assert "ctrl+c" in result.output
        mock_pyautogui.hotkey.assert_called_once_with("ctrl", "c")


async def test_hotkey_requires_keys(screen_tool):
    mock_pyautogui = MagicMock()
    with patch("hauba.tools.screen.PYAUTOGUI_AVAILABLE", True), \
         patch("hauba.tools.screen.EMERGENCY_STOP_FILE", Path("/nonexistent/STOP")), \
         patch("hauba.tools.screen.pyautogui", mock_pyautogui, create=True):
        result = await screen_tool.execute(action="hotkey")
        assert not result.success
        assert "Keys required" in result.error


# --- Coordinate validation ---

async def test_validate_coords_negative(screen_tool):
    mock_pyautogui = MagicMock()
    mock_pyautogui.size = MagicMock(return_value=(1920, 1080))

    with patch("hauba.tools.screen.PYAUTOGUI_AVAILABLE", True), \
         patch("hauba.tools.screen.EMERGENCY_STOP_FILE", Path("/nonexistent/STOP")), \
         patch("hauba.tools.screen.pyautogui", mock_pyautogui, create=True):
        result = await screen_tool.execute(action="click", x=-10, y=100)
        assert not result.success
        assert "out of screen bounds" in result.error
