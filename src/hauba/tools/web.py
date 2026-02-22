"""Web search tool — DuckDuckGo HTML scraping with Brave Search API fallback."""

from __future__ import annotations

import os
import re

import httpx
import structlog

from hauba.core.types import SearchResult, ToolResult
from hauba.tools.base import BaseTool

logger = structlog.get_logger()

DUCKDUCKGO_URL = "https://html.duckduckgo.com/html/"
BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"

# User-Agent for DuckDuckGo HTML requests
DDG_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class WebSearchTool(BaseTool):
    """Web search via DuckDuckGo (default) or Brave Search API.

    Uses DuckDuckGo HTML scraping by default (no API key required).
    Falls back to Brave Search API if BRAVE_API_KEY env var is set.
    """

    name = "web_search"
    description = "Search the web and return results (title, snippet, url)"

    async def execute(self, **kwargs: object) -> ToolResult:
        """Execute web search.

        Args:
            query: Search query string
            num_results: Number of results to return (default 5)
        """
        query = str(kwargs.get("query", ""))
        if not query:
            return ToolResult(
                tool_name=self.name, success=False, error="Query required", exit_code=1
            )

        num_results = int(kwargs.get("num_results", 5))

        brave_key = os.environ.get("BRAVE_API_KEY", "")
        try:
            if brave_key:
                results = await self._search_brave(query, num_results, brave_key)
            else:
                results = await self._search_duckduckgo(query, num_results)
        except Exception as exc:
            logger.error("web_search.failed", query=query, error=str(exc))
            return ToolResult(tool_name=self.name, success=False, error=str(exc), exit_code=1)

        if not results:
            return ToolResult(tool_name=self.name, success=True, output="No results found.")

        output_lines = []
        for r in results:
            output_lines.append(f"[{r.rank}] {r.title}\n    {r.url}\n    {r.snippet}")
        output = "\n\n".join(output_lines)

        return ToolResult(tool_name=self.name, success=True, output=output)

    async def _search_duckduckgo(self, query: str, num_results: int) -> list[SearchResult]:
        """Search DuckDuckGo via HTML scraping."""
        async with httpx.AsyncClient(
            headers={"User-Agent": DDG_USER_AGENT},
            follow_redirects=True,
            timeout=15.0,
        ) as client:
            resp = await client.post(DUCKDUCKGO_URL, data={"q": query})
            resp.raise_for_status()
            html = resp.text

        return self._parse_ddg_html(html, num_results)

    def _parse_ddg_html(self, html: str, num_results: int) -> list[SearchResult]:
        """Parse DuckDuckGo HTML results page."""
        results: list[SearchResult] = []

        # Match result blocks: <a class="result__a" href="...">title</a>
        # and <a class="result__snippet" ...>snippet</a>
        link_pattern = re.compile(r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL)
        snippet_pattern = re.compile(r'class="result__snippet"[^>]*>(.*?)</(?:a|span)>', re.DOTALL)

        links = link_pattern.findall(html)
        snippets = snippet_pattern.findall(html)

        for i, (url, title) in enumerate(links[:num_results]):
            title_clean = re.sub(r"<[^>]+>", "", title).strip()
            snippet_clean = ""
            if i < len(snippets):
                snippet_clean = re.sub(r"<[^>]+>", "", snippets[i]).strip()

            # DuckDuckGo wraps URLs through a redirect — extract actual URL
            if "uddg=" in url:
                from urllib.parse import parse_qs, urlparse

                parsed = urlparse(url)
                qs = parse_qs(parsed.query)
                url = qs.get("uddg", [url])[0]

            results.append(
                SearchResult(
                    title=title_clean,
                    snippet=snippet_clean,
                    url=url,
                    rank=i + 1,
                )
            )

        return results

    async def _search_brave(self, query: str, num_results: int, api_key: str) -> list[SearchResult]:
        """Search via Brave Search API."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                BRAVE_API_URL,
                params={"q": query, "count": num_results},
                headers={
                    "X-Subscription-Token": api_key,
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        results: list[SearchResult] = []
        for i, item in enumerate(data.get("web", {}).get("results", [])[:num_results]):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    snippet=item.get("description", ""),
                    url=item.get("url", ""),
                    rank=i + 1,
                )
            )
        return results
