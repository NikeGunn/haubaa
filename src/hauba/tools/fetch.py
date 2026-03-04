"""Web fetch tool — fetch URLs and convert HTML to readable text."""

from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

from hauba.core.types import ToolResult
from hauba.tools.base import BaseTool

logger = structlog.get_logger()

# Max content length (50KB — prevents memory issues with huge pages)
MAX_CONTENT_LENGTH = 50_000

# Request timeout
FETCH_TIMEOUT = 15.0

# User-Agent for requests
FETCH_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class WebFetchTool(BaseTool):
    """Fetch a web page and return its content as readable text.

    Uses httpx to fetch the URL and BeautifulSoup to extract readable text.
    Supports HTML, JSON, and plain text responses.
    """

    name = "web_fetch"
    description = (
        "Fetch a web page URL and return its content as readable text. "
        "Use this to read documentation, articles, API responses, and web content."
    )

    def _parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch.",
                },
                "extract_text": {
                    "type": "boolean",
                    "description": "Extract readable text from HTML (default true).",
                },
            },
            "required": ["url"],
        }

    async def execute(self, **kwargs: object) -> ToolResult:
        """Fetch a URL and return its content.

        Args:
            url: The URL to fetch.
            extract_text: If True, convert HTML to readable text. Default True.
        """
        url = str(kwargs.get("url", ""))
        if not url:
            return ToolResult(tool_name=self.name, success=False, error="URL required", exit_code=1)

        extract_text = bool(kwargs.get("extract_text", True))

        logger.info("tool.web_fetch.execute", url=url[:200])

        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": FETCH_USER_AGENT},
                follow_redirects=True,
                timeout=FETCH_TIMEOUT,
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            raw = resp.text

            # JSON response — return as-is
            if "json" in content_type:
                output = raw[:MAX_CONTENT_LENGTH]
                if len(raw) > MAX_CONTENT_LENGTH:
                    output += "\n\n[Content truncated — original size: {len(raw)} chars]"
                return ToolResult(tool_name=self.name, success=True, output=output)

            # Plain text — return as-is
            if "text/plain" in content_type or not extract_text:
                output = raw[:MAX_CONTENT_LENGTH]
                if len(raw) > MAX_CONTENT_LENGTH:
                    output += f"\n\n[Content truncated — original size: {len(raw)} chars]"
                return ToolResult(tool_name=self.name, success=True, output=output)

            # HTML — convert to readable text
            title, text = self._html_to_text(raw)
            output = ""
            if title:
                output = f"# {title}\n\n"
            output += text

            if len(output) > MAX_CONTENT_LENGTH:
                output = output[:MAX_CONTENT_LENGTH]
                output += "\n\n[Content truncated]"

            return ToolResult(tool_name=self.name, success=True, output=output)

        except httpx.TimeoutException:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Timeout fetching {url} (>{FETCH_TIMEOUT}s)",
                exit_code=1,
            )
        except httpx.HTTPStatusError as exc:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"HTTP {exc.response.status_code} for {url}",
                exit_code=1,
            )
        except Exception as exc:
            logger.error("tool.web_fetch.error", url=url[:200], error=str(exc))
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Failed to fetch {url}: {exc}",
                exit_code=1,
            )

    @staticmethod
    def _html_to_text(html: str) -> tuple[str, str]:
        """Convert HTML to readable text using BeautifulSoup.

        Returns (title, body_text).
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            # Fallback: strip tags with regex
            title = ""
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            return title, text

        soup = BeautifulSoup(html, "html.parser")

        # Extract title
        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)

        # Remove non-content elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()

        # Extract text with newlines for block elements
        text = soup.get_text(separator="\n", strip=True)

        # Collapse excessive newlines
        text = re.sub(r"\n{3,}", "\n\n", text)

        return title, text
