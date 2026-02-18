"""Tests for WebSearchTool — DuckDuckGo + Brave Search."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hauba.tools.web import WebSearchTool


@pytest.fixture
def search_tool():
    return WebSearchTool()


# --- Validation ---

async def test_search_requires_query(search_tool):
    result = await search_tool.execute()
    assert not result.success
    assert "Query required" in result.error


# --- DuckDuckGo ---

async def test_ddg_search_returns_results(search_tool):
    """Mock DuckDuckGo HTML response and verify parsing."""
    fake_html = """
    <div class="result">
        <a class="result__a" href="https://example.com">Example Title</a>
        <a class="result__snippet">This is a snippet about the topic.</a>
    </div>
    <div class="result">
        <a class="result__a" href="https://other.com">Other Title</a>
        <a class="result__snippet">Another snippet here.</a>
    </div>
    """
    mock_resp = MagicMock()
    mock_resp.text = fake_html
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("hauba.tools.web.httpx.AsyncClient", return_value=mock_client), \
         patch.dict("os.environ", {}, clear=False):
        # Ensure no BRAVE_API_KEY
        import os
        orig = os.environ.pop("BRAVE_API_KEY", None)
        try:
            result = await search_tool.execute(query="test query")
        finally:
            if orig is not None:
                os.environ["BRAVE_API_KEY"] = orig

    assert result.success
    assert "Example Title" in result.output


async def test_ddg_no_results(search_tool):
    mock_resp = MagicMock()
    mock_resp.text = "<html><body>No results</body></html>"
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("hauba.tools.web.httpx.AsyncClient", return_value=mock_client):
        import os
        orig = os.environ.pop("BRAVE_API_KEY", None)
        try:
            result = await search_tool.execute(query="noresults12345")
        finally:
            if orig is not None:
                os.environ["BRAVE_API_KEY"] = orig

    assert result.success
    assert "No results" in result.output


# --- Brave Search ---

async def test_brave_search_used_when_key_set(search_tool):
    """Brave Search API is used when BRAVE_API_KEY is set."""
    brave_response = {
        "web": {
            "results": [
                {"title": "Brave Result", "description": "From Brave", "url": "https://brave.com/r"}
            ]
        }
    }
    mock_resp = MagicMock()
    mock_resp.json = MagicMock(return_value=brave_response)
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("hauba.tools.web.httpx.AsyncClient", return_value=mock_client), \
         patch.dict("os.environ", {"BRAVE_API_KEY": "test-key"}):
        result = await search_tool.execute(query="brave test")

    assert result.success
    assert "Brave Result" in result.output


# --- Error handling ---

async def test_search_network_error(search_tool):
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=Exception("Connection failed"))

    with patch("hauba.tools.web.httpx.AsyncClient", return_value=mock_client):
        import os
        orig = os.environ.pop("BRAVE_API_KEY", None)
        try:
            result = await search_tool.execute(query="test")
        finally:
            if orig is not None:
                os.environ["BRAVE_API_KEY"] = orig

    assert not result.success
    assert "Connection failed" in result.error


# --- DDG URL parsing ---

def test_ddg_html_parsing_with_uddg_redirect(search_tool):
    """DuckDuckGo wraps URLs — test extraction of real URL."""
    html = '''
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Freal.com&rut=abc">Real Title</a>
    <a class="result__snippet">A real snippet.</a>
    '''
    results = search_tool._parse_ddg_html(html, 5)
    assert len(results) == 1
    assert results[0].url == "https://real.com"
    assert results[0].title == "Real Title"


def test_ddg_html_parsing_limits_results(search_tool):
    html = ""
    for i in range(10):
        html += f'<a class="result__a" href="https://ex{i}.com">Title {i}</a>'
        html += f'<a class="result__snippet">Snippet {i}</a>'
    results = search_tool._parse_ddg_html(html, 3)
    assert len(results) == 3
    assert results[2].rank == 3
