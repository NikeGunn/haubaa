"""Tests for WebUI — FastAPI dashboard with WebSocket."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hauba.core.events import EventEmitter

# --- Graceful degradation ---


def test_web_ui_unavailable_raises() -> None:
    with patch("hauba.ui.web.FASTAPI_AVAILABLE", False):
        from hauba.ui.web import WebUI, WebUIError

        events = EventEmitter()
        with pytest.raises(WebUIError, match="FastAPI not installed"):
            WebUI(events=events)


# --- Construction (with FastAPI mocked as available) ---


def test_web_ui_creates_app() -> None:
    mock_fastapi = MagicMock()
    mock_app = MagicMock()
    mock_fastapi.return_value = mock_app
    mock_app.get = MagicMock(return_value=lambda f: f)
    mock_app.post = MagicMock(return_value=lambda f: f)
    mock_app.websocket = MagicMock(return_value=lambda f: f)

    with patch("hauba.ui.web.FASTAPI_AVAILABLE", True), \
         patch("hauba.ui.web.FastAPI", mock_fastapi, create=True), \
         patch("hauba.ui.web.HTMLResponse", MagicMock(), create=True), \
         patch("hauba.ui.web.WebSocket", MagicMock(), create=True), \
         patch("hauba.ui.web.WebSocketDisconnect", Exception, create=True):
        from hauba.ui.web import WebUI

        events = EventEmitter()
        web = WebUI(events=events)
        assert web.app is not None


# --- Event broadcasting ---


async def test_broadcast_event_to_connections() -> None:
    mock_fastapi = MagicMock()
    mock_app = MagicMock()
    mock_fastapi.return_value = mock_app
    mock_app.get = MagicMock(return_value=lambda f: f)
    mock_app.post = MagicMock(return_value=lambda f: f)
    mock_app.websocket = MagicMock(return_value=lambda f: f)

    with patch("hauba.ui.web.FASTAPI_AVAILABLE", True), \
         patch("hauba.ui.web.FastAPI", mock_fastapi, create=True), \
         patch("hauba.ui.web.HTMLResponse", MagicMock(), create=True), \
         patch("hauba.ui.web.WebSocket", MagicMock(), create=True), \
         patch("hauba.ui.web.WebSocketDisconnect", Exception, create=True):
        from hauba.ui.web import WebUI

        events = EventEmitter()
        web = WebUI(events=events)

        # Simulate WebSocket connection
        mock_ws = AsyncMock()
        web._connections.append(mock_ws)

        # Emit an event — should broadcast to the mock WS
        await events.emit("task.started", {"msg": "hello"})

        mock_ws.send_text.assert_called_once()
        sent_text = mock_ws.send_text.call_args[0][0]
        assert "task.started" in sent_text


async def test_broadcast_removes_disconnected() -> None:
    mock_fastapi = MagicMock()
    mock_app = MagicMock()
    mock_fastapi.return_value = mock_app
    mock_app.get = MagicMock(return_value=lambda f: f)
    mock_app.post = MagicMock(return_value=lambda f: f)
    mock_app.websocket = MagicMock(return_value=lambda f: f)

    with patch("hauba.ui.web.FASTAPI_AVAILABLE", True), \
         patch("hauba.ui.web.FastAPI", mock_fastapi, create=True), \
         patch("hauba.ui.web.HTMLResponse", MagicMock(), create=True), \
         patch("hauba.ui.web.WebSocket", MagicMock(), create=True), \
         patch("hauba.ui.web.WebSocketDisconnect", Exception, create=True):
        from hauba.ui.web import WebUI

        events = EventEmitter()
        web = WebUI(events=events)

        bad_ws = AsyncMock()
        bad_ws.send_text = AsyncMock(side_effect=Exception("disconnected"))
        web._connections.append(bad_ws)

        await events.emit("test.event", {})

        # Bad connection should be removed
        assert bad_ws not in web._connections


# --- Dashboard HTML ---


def test_dashboard_html_returns_valid_html() -> None:
    mock_fastapi = MagicMock()
    mock_app = MagicMock()
    mock_fastapi.return_value = mock_app
    mock_app.get = MagicMock(return_value=lambda f: f)
    mock_app.post = MagicMock(return_value=lambda f: f)
    mock_app.websocket = MagicMock(return_value=lambda f: f)

    with patch("hauba.ui.web.FASTAPI_AVAILABLE", True), \
         patch("hauba.ui.web.FastAPI", mock_fastapi, create=True), \
         patch("hauba.ui.web.HTMLResponse", MagicMock(), create=True), \
         patch("hauba.ui.web.WebSocket", MagicMock(), create=True), \
         patch("hauba.ui.web.WebSocketDisconnect", Exception, create=True):
        from hauba.ui.web import WebUI

        events = EventEmitter()
        web = WebUI(events=events)
        html = web._dashboard_html()
        assert "<!DOCTYPE html>" in html
        assert "Hauba AI Dashboard" in html
        assert "WebSocket" in html
