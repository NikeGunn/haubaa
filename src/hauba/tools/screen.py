"""Screen control tool using pyautogui + Pillow."""

from __future__ import annotations

from pathlib import Path

import structlog

from hauba.core.constants import EMERGENCY_STOP_FILE, SCREENSHOTS_DIR
from hauba.core.types import ScreenAction, ToolResult
from hauba.exceptions import ScreenControlError, ToolNotAvailableError
from hauba.tools.base import BaseTool

logger = structlog.get_logger()

try:
    import pyautogui

    pyautogui.FAILSAFE = True  # Move mouse to corner to abort
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

try:
    from PIL import Image  # noqa: F401

    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False


class ScreenTool(BaseTool):
    """Desktop screen control — capture, click, type, scroll, hotkey.

    Capture is always allowed.
    Click/type/scroll/hotkey require ``allow_control=True``.
    Safety: emergency stop file (~/.hauba/STOP), pyautogui FAILSAFE.
    """

    name = "screen"
    description = "Desktop screen control (capture, click, type, scroll, hotkey)"

    def __init__(self, allow_control: bool = False) -> None:
        self.allow_control = allow_control

    def _check_available(self) -> None:
        if not PYAUTOGUI_AVAILABLE:
            raise ToolNotAvailableError(
                "pyautogui not installed. Run: pip install hauba[computer-use]"
            )

    def _check_emergency_stop(self) -> None:
        """Check for emergency stop file."""
        if EMERGENCY_STOP_FILE.exists():
            raise ScreenControlError(
                f"Emergency stop active. Remove {EMERGENCY_STOP_FILE} to resume."
            )

    def _check_control_allowed(self) -> None:
        """Ensure control actions are permitted."""
        if not self.allow_control:
            raise ScreenControlError(
                "Screen control disabled. Set allow_screen_control=true in config."
            )

    def _validate_coords(self, x: int, y: int) -> None:
        """Validate screen coordinates are within bounds."""
        if not PYAUTOGUI_AVAILABLE:
            return
        screen_w, screen_h = pyautogui.size()
        if not (0 <= x < screen_w and 0 <= y < screen_h):
            raise ScreenControlError(
                f"Coordinates ({x}, {y}) out of screen bounds ({screen_w}x{screen_h})"
            )

    async def execute(self, **kwargs: object) -> ToolResult:
        """Execute a screen action.

        Args:
            action: ScreenAction or string action name
            x, y: Coordinates for click
            text: Text for type action
            keys: Keys for hotkey (comma-separated)
            dx, dy: Scroll amounts
            path: Screenshot save path
        """
        action_str = str(kwargs.get("action", ""))
        try:
            action = ScreenAction(action_str)
        except ValueError:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Unknown screen action: {action_str}",
                exit_code=1,
            )

        try:
            self._check_available()
            self._check_emergency_stop()
        except (ToolNotAvailableError, ScreenControlError) as exc:
            return ToolResult(
                tool_name=self.name, success=False, error=str(exc), exit_code=1
            )

        try:
            if action == ScreenAction.CAPTURE:
                return await self._capture(kwargs)
            elif action == ScreenAction.CLICK:
                return await self._click(kwargs)
            elif action == ScreenAction.TYPE:
                return await self._type(kwargs)
            elif action == ScreenAction.SCROLL:
                return await self._scroll(kwargs)
            elif action == ScreenAction.HOTKEY:
                return await self._hotkey(kwargs)
            else:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    error=f"Unhandled action: {action}",
                    exit_code=1,
                )
        except ScreenControlError as exc:
            return ToolResult(
                tool_name=self.name, success=False, error=str(exc), exit_code=1
            )
        except Exception as exc:
            logger.error("screen.action_failed", action=action_str, error=str(exc))
            return ToolResult(
                tool_name=self.name, success=False, error=str(exc), exit_code=1
            )

    async def _capture(self, kwargs: dict[str, object]) -> ToolResult:
        """Capture a screenshot. Always allowed."""
        path_str = str(kwargs.get("path", ""))
        if not path_str:
            SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
            import time

            path_str = str(SCREENSHOTS_DIR / f"screen_{int(time.time())}.png")

        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)

        screenshot = pyautogui.screenshot()
        screenshot.save(str(path))
        logger.info("screen.captured", path=str(path))
        return ToolResult(
            tool_name=self.name, success=True, output=f"Screenshot saved: {path}"
        )

    async def _click(self, kwargs: dict[str, object]) -> ToolResult:
        self._check_control_allowed()
        x = int(kwargs.get("x", 0))
        y = int(kwargs.get("y", 0))
        self._validate_coords(x, y)
        button = str(kwargs.get("button", "left"))
        pyautogui.click(x, y, button=button)
        logger.info("screen.clicked", x=x, y=y, button=button)
        return ToolResult(
            tool_name=self.name, success=True, output=f"Clicked ({x}, {y}) [{button}]"
        )

    async def _type(self, kwargs: dict[str, object]) -> ToolResult:
        self._check_control_allowed()
        text = str(kwargs.get("text", ""))
        if not text:
            return ToolResult(
                tool_name=self.name, success=False, error="Text required for type", exit_code=1
            )
        interval = float(kwargs.get("interval", 0.02))
        pyautogui.typewrite(text, interval=interval)
        logger.info("screen.typed", length=len(text))
        return ToolResult(
            tool_name=self.name, success=True, output=f"Typed {len(text)} characters"
        )

    async def _scroll(self, kwargs: dict[str, object]) -> ToolResult:
        self._check_control_allowed()
        clicks = int(kwargs.get("clicks", 3))
        x = kwargs.get("x")
        y = kwargs.get("y")
        if x is not None and y is not None:
            pyautogui.scroll(clicks, int(x), int(y))
        else:
            pyautogui.scroll(clicks)
        logger.info("screen.scrolled", clicks=clicks)
        return ToolResult(
            tool_name=self.name, success=True, output=f"Scrolled {clicks} clicks"
        )

    async def _hotkey(self, kwargs: dict[str, object]) -> ToolResult:
        self._check_control_allowed()
        keys_str = str(kwargs.get("keys", ""))
        if not keys_str:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="Keys required for hotkey (comma-separated)",
                exit_code=1,
            )
        keys = [k.strip() for k in keys_str.split(",")]
        pyautogui.hotkey(*keys)
        logger.info("screen.hotkey", keys=keys)
        return ToolResult(
            tool_name=self.name, success=True, output=f"Hotkey: {'+'.join(keys)}"
        )
