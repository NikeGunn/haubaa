"""Tests for WebFetchTool."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hauba.tools.fetch import WebFetchTool


@pytest.fixture
def fetch_tool() -> WebFetchTool:
    return WebFetchTool()


class TestWebFetchTool:
    """Test WebFetchTool.execute()."""

    def test_name_and_description(self, fetch_tool: WebFetchTool) -> None:
        assert fetch_tool.name == "web_fetch"
        assert "fetch" in fetch_tool.description.lower()

    @pytest.mark.asyncio
    async def test_missing_url(self, fetch_tool: WebFetchTool) -> None:
        result = await fetch_tool.execute()
        assert not result.success
        assert "URL required" in result.error

    @pytest.mark.asyncio
    async def test_successful_html_fetch(self, fetch_tool: WebFetchTool) -> None:
        fake_html = (
            "<html><head><title>Test Page</title></head><body><p>Hello world</p></body></html>"
        )
        mock_resp = MagicMock()
        mock_resp.text = fake_html
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("hauba.tools.fetch.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_tool.execute(url="https://example.com")

        assert result.success
        assert "Hello world" in result.output

    @pytest.mark.asyncio
    async def test_json_response(self, fetch_tool: WebFetchTool) -> None:
        mock_resp = MagicMock()
        mock_resp.text = '{"key": "value"}'
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("hauba.tools.fetch.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_tool.execute(url="https://api.example.com/data")

        assert result.success
        assert '"key"' in result.output

    @pytest.mark.asyncio
    async def test_timeout_error(self, fetch_tool: WebFetchTool) -> None:
        import httpx

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with patch("hauba.tools.fetch.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_tool.execute(url="https://slow.example.com")

        assert not result.success
        assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_http_error(self, fetch_tool: WebFetchTool) -> None:
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("Not Found", request=MagicMock(), response=mock_resp)
        )

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("hauba.tools.fetch.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_tool.execute(url="https://example.com/404")

        assert not result.success
        assert "404" in result.error


class TestHtmlToText:
    """Test WebFetchTool._html_to_text()."""

    def test_extract_title(self) -> None:
        html = "<html><head><title>My Title</title></head><body>Content</body></html>"
        title, _text = WebFetchTool._html_to_text(html)
        assert title == "My Title"

    def test_strip_scripts_and_styles(self) -> None:
        html = (
            "<html><body>"
            "<script>alert('bad')</script>"
            "<style>body{color:red}</style>"
            "<p>Visible content</p>"
            "</body></html>"
        )
        _title, text = WebFetchTool._html_to_text(html)
        assert "alert" not in text
        assert "color:red" not in text
        assert "Visible content" in text

    def test_empty_html(self) -> None:
        title, _text = WebFetchTool._html_to_text("")
        assert title == ""


class TestParametersSchema:
    """Test tool schema."""

    def test_schema_has_url(self) -> None:
        tool = WebFetchTool()
        schema = tool._parameters_schema()
        assert "url" in schema["properties"]
        assert "url" in schema["required"]
