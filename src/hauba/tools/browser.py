"""Browser automation tool using Playwright with persistent session relay.

The "relay" concept: browser sessions are persisted to disk (cookies, local storage,
session storage) so that sessions survive crashes and restarts. The browser context
is stored at ~/.hauba/browser_sessions/ and can be resumed.

Features:
- Persistent browser context (cookies/storage saved to disk)
- Stealth mode (anti-bot detection evasion)
- Auto-retry on page crashes with session recovery
- Configurable timeouts per action
- Smart waiting (networkidle + DOM settle)
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import structlog

from hauba.core.constants import HAUBA_HOME, SCREENSHOTS_DIR
from hauba.core.types import BrowserAction, ToolResult
from hauba.exceptions import ToolNotAvailableError
from hauba.tools.base import BaseTool

logger = structlog.get_logger()

try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# Session storage directory
BROWSER_SESSIONS_DIR = HAUBA_HOME / "browser_sessions"

# Stealth scripts to inject into pages to avoid bot detection
_STEALTH_JS = """
// Override navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

// Override chrome runtime
window.chrome = {runtime: {}};

// Override permissions query
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) =>
    parameters.name === 'notifications'
        ? Promise.resolve({state: Notification.permission})
        : originalQuery(parameters);

// Override plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
});

// Override languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en'],
});
"""

# Default timeouts (ms)
DEFAULT_NAVIGATION_TIMEOUT = 60000
DEFAULT_ACTION_TIMEOUT = 10000
MAX_RETRIES = 3
RETRY_DELAY = 2.0


class BrowserTool(BaseTool):
    """Playwright-based browser with persistent session relay.

    Sessions are stored on disk and survive crashes. Pages auto-recover
    from navigation failures with retry logic.
    """

    name = "browser"
    description = (
        "Browser automation with persistent sessions "
        "(navigate, click, type, extract, screenshot, wait, scroll, evaluate)"
    )

    def __init__(
        self,
        session_name: str = "default",
        headless: bool = True,
        stealth: bool = True,
    ) -> None:
        self._session_name = session_name
        self._headless = headless
        self._stealth = stealth
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self._playwright: Any = None
        self._session_dir = BROWSER_SESSIONS_DIR / session_name

    async def _ensure_browser(self) -> Any:
        """Launch browser with persistent context if not running. Returns the active page."""
        if not PLAYWRIGHT_AVAILABLE:
            raise ToolNotAvailableError(
                "Playwright not installed. Run: pip install hauba[computer-use] && playwright install chromium"
            )

        if self._page is not None:
            # Check if page is still alive
            try:
                await self._page.title()
                return self._page
            except Exception:
                logger.warning("browser.page_crashed", session=self._session_name)
                self._page = None

        # Ensure session directory exists for persistent context
        self._session_dir.mkdir(parents=True, exist_ok=True)

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        if self._context is None:
            # Launch browser with persistent context — this is the relay mechanism
            # All cookies, localStorage, sessionStorage are saved to disk automatically
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self._session_dir),
                headless=self._headless,
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                timezone_id="America/New_York",
                java_script_enabled=True,
                bypass_csp=True,
                ignore_https_errors=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            logger.info(
                "browser.context_created", session=self._session_name, headless=self._headless
            )

        # Get or create page
        pages = self._context.pages
        if pages:
            self._page = pages[0]
        else:
            self._page = await self._context.new_page()

        # Inject stealth scripts
        if self._stealth:
            await self._page.add_init_script(_STEALTH_JS)

        # Set default timeouts
        self._page.set_default_timeout(DEFAULT_ACTION_TIMEOUT)
        self._page.set_default_navigation_timeout(DEFAULT_NAVIGATION_TIMEOUT)

        return self._page

    async def close(self) -> None:
        """Close browser and cleanup resources. Session data persists on disk."""
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None
            self._page = None
            self._browser = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    async def execute(self, **kwargs: object) -> ToolResult:
        """Execute a browser action with auto-retry on failure.

        Args:
            action: BrowserAction or string action name
            url: URL for navigate action
            selector: CSS selector for click/type/extract/wait
            text: Text for type action
            path: Screenshot save path (optional)
            timeout: Timeout in ms (overrides default)
            wait_for: Additional wait condition after action ("networkidle", "domcontentloaded")
            script: JavaScript to evaluate (for "evaluate" action)
        """
        action_str = str(kwargs.get("action", ""))
        try:
            BrowserAction(action_str)  # validate known action
        except ValueError:
            # Support extended actions beyond BrowserAction enum
            if action_str not in ("scroll", "evaluate"):
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    error=f"Unknown browser action: {action_str}. Valid: navigate, click, type, extract, screenshot, wait, scroll, evaluate",
                    exit_code=1,
                )

        # Auto-retry wrapper
        last_error = ""
        for attempt in range(MAX_RETRIES):
            try:
                page = await self._ensure_browser()
                result = await self._dispatch_action(action_str, page, kwargs)

                # Optional wait_for after action
                wait_for = str(kwargs.get("wait_for", ""))
                if wait_for and result.success:
                    await self._smart_wait(page, wait_for)

                return result
            except ToolNotAvailableError as exc:
                return ToolResult(tool_name=self.name, success=False, error=str(exc), exit_code=1)
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "browser.retry",
                    action=action_str,
                    attempt=attempt + 1,
                    error=last_error[:200],
                )
                # Reset page on crash to force reconnection
                self._page = None
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)

        return ToolResult(
            tool_name=self.name,
            success=False,
            error=f"Failed after {MAX_RETRIES} attempts: {last_error}",
            exit_code=1,
        )

    async def _dispatch_action(
        self, action_str: str, page: Any, kwargs: dict[str, object]
    ) -> ToolResult:
        """Route to the correct action handler."""
        if action_str == "navigate":
            return await self._navigate(page, kwargs)
        elif action_str == "click":
            return await self._click(page, kwargs)
        elif action_str == "type":
            return await self._type(page, kwargs)
        elif action_str == "extract":
            return await self._extract(page, kwargs)
        elif action_str == "screenshot":
            return await self._screenshot(page, kwargs)
        elif action_str == "wait":
            return await self._wait(page, kwargs)
        elif action_str == "scroll":
            return await self._scroll(page, kwargs)
        elif action_str == "evaluate":
            return await self._evaluate(page, kwargs)
        else:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Unhandled action: {action_str}",
                exit_code=1,
            )

    async def _navigate(self, page: Any, kwargs: dict[str, object]) -> ToolResult:
        url = str(kwargs.get("url", ""))
        if not url:
            return ToolResult(
                tool_name=self.name, success=False, error="URL required for navigate", exit_code=1
            )
        timeout = int(kwargs.get("timeout", DEFAULT_NAVIGATION_TIMEOUT))
        response = await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        status = response.status if response else 0

        # Wait for page to settle (dynamic content)
        await self._wait_for_settle(page)

        title = await page.title()
        return ToolResult(
            tool_name=self.name,
            success=True,
            output=f"Navigated to {url} (status={status}, title='{title}')",
        )

    async def _click(self, page: Any, kwargs: dict[str, object]) -> ToolResult:
        selector = str(kwargs.get("selector", ""))
        if not selector:
            return ToolResult(
                tool_name=self.name, success=False, error="Selector required for click", exit_code=1
            )
        timeout = int(kwargs.get("timeout", DEFAULT_ACTION_TIMEOUT))

        # Try to scroll element into view first
        try:
            await page.locator(selector).scroll_into_view_if_needed(timeout=timeout)
        except Exception:
            pass

        await page.click(selector, timeout=timeout)
        await self._wait_for_settle(page)

        return ToolResult(tool_name=self.name, success=True, output=f"Clicked: {selector}")

    async def _type(self, page: Any, kwargs: dict[str, object]) -> ToolResult:
        selector = str(kwargs.get("selector", ""))
        text = str(kwargs.get("text", ""))
        if not selector or not text:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="Selector and text required for type",
                exit_code=1,
            )
        timeout = int(kwargs.get("timeout", DEFAULT_ACTION_TIMEOUT))

        # Clear existing content first, then type
        await page.fill(selector, "", timeout=timeout)
        await page.fill(selector, text, timeout=timeout)

        return ToolResult(
            tool_name=self.name, success=True, output=f"Typed into {selector}: {text[:50]}"
        )

    async def _extract(self, page: Any, kwargs: dict[str, object]) -> ToolResult:
        selector = str(kwargs.get("selector", ""))
        if not selector:
            # Extract full page text content (cleaned)
            content = await page.evaluate(
                "() => document.body ? document.body.innerText : document.documentElement.textContent"
            )
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=str(content)[:10000],
            )

        elements = await page.query_selector_all(selector)
        texts = []
        for el in elements:
            text = await el.text_content()
            if text:
                texts.append(text.strip())

        if not texts:
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=f"No elements found for selector: {selector}",
            )

        return ToolResult(tool_name=self.name, success=True, output="\n".join(texts))

    async def _screenshot(self, page: Any, kwargs: dict[str, object]) -> ToolResult:
        path_str = str(kwargs.get("path", ""))
        if not path_str:
            SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
            path_str = str(SCREENSHOTS_DIR / f"screenshot_{int(time.time())}.png")

        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(path), full_page=True)

        return ToolResult(tool_name=self.name, success=True, output=f"Screenshot saved: {path}")

    async def _wait(self, page: Any, kwargs: dict[str, object]) -> ToolResult:
        selector = str(kwargs.get("selector", ""))
        timeout = int(kwargs.get("timeout", DEFAULT_ACTION_TIMEOUT))

        if selector:
            await page.wait_for_selector(selector, timeout=timeout, state="visible")
            return ToolResult(
                tool_name=self.name, success=True, output=f"Element visible: {selector}"
            )
        else:
            await asyncio.sleep(timeout / 1000.0)
            return ToolResult(tool_name=self.name, success=True, output=f"Waited {timeout}ms")

    async def _scroll(self, page: Any, kwargs: dict[str, object]) -> ToolResult:
        direction = str(kwargs.get("direction", "down"))
        amount = int(kwargs.get("amount", 500))

        if direction == "down":
            await page.evaluate(f"window.scrollBy(0, {amount})")
        elif direction == "up":
            await page.evaluate(f"window.scrollBy(0, -{amount})")
        elif direction == "bottom":
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        elif direction == "top":
            await page.evaluate("window.scrollTo(0, 0)")

        return ToolResult(
            tool_name=self.name, success=True, output=f"Scrolled {direction} {amount}px"
        )

    async def _evaluate(self, page: Any, kwargs: dict[str, object]) -> ToolResult:
        script = str(kwargs.get("script", ""))
        if not script:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="Script required for evaluate",
                exit_code=1,
            )

        result = await page.evaluate(script)
        return ToolResult(tool_name=self.name, success=True, output=str(result)[:5000])

    async def _wait_for_settle(self, page: Any, timeout_ms: int = 3000) -> None:
        """Wait for the page to settle — no new network requests or DOM mutations.

        Uses a short networkidle wait with fallback to a brief sleep.
        """
        try:
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:
            # networkidle can timeout on long-polling pages — that's OK
            await asyncio.sleep(0.5)

    async def _smart_wait(self, page: Any, condition: str) -> None:
        """Wait for a specific condition after an action."""
        try:
            if condition == "networkidle":
                await page.wait_for_load_state("networkidle", timeout=10000)
            elif condition == "domcontentloaded":
                await page.wait_for_load_state("domcontentloaded", timeout=10000)
            elif condition.startswith("selector:"):
                sel = condition.split(":", 1)[1]
                await page.wait_for_selector(sel, timeout=10000, state="visible")
        except Exception:
            pass  # Don't fail the action for wait timeouts

    async def get_page_info(self) -> dict[str, str]:
        """Get current page info (url, title) — useful for agent decision-making."""
        try:
            page = await self._ensure_browser()
            return {
                "url": page.url,
                "title": await page.title(),
            }
        except Exception:
            return {"url": "", "title": ""}
