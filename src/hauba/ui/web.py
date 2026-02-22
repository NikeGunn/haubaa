"""Web UI — FastAPI server with WebSocket for real-time agent dashboard."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

from hauba.core.events import EventEmitter
from hauba.core.types import Event
from hauba.exceptions import HaubaError

logger = structlog.get_logger()

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


class WebUIError(HaubaError):
    """Web UI error."""


class WebUI:
    """FastAPI-based web dashboard with WebSocket real-time updates.

    Provides:
    - GET / — Dashboard HTML page
    - GET /api/status — JSON status endpoint
    - GET /api/tasks — Recent task history
    - WS /ws — Real-time event stream
    - POST /api/task — Submit a new task
    """

    def __init__(self, events: EventEmitter, on_task: Any = None) -> None:
        if not FASTAPI_AVAILABLE:
            raise WebUIError("FastAPI not installed. Run: pip install hauba[web]")

        self.events = events
        self._on_task = on_task
        self._connections: list[WebSocket] = []
        self._task_history: list[dict[str, Any]] = []
        self._app = self._create_app()

        # Subscribe to all events for WebSocket broadcast
        self.events.on("*", self._broadcast_event)

    @property
    def app(self) -> Any:
        """The FastAPI application instance."""
        return self._app

    def _create_app(self) -> Any:
        app = FastAPI(title="Hauba AI Dashboard", version="1.0.0")

        @app.get("/", response_class=HTMLResponse)
        async def dashboard() -> str:
            return self._dashboard_html()

        @app.get("/api/status")
        async def status() -> dict[str, Any]:
            return {
                "status": "online",
                "connections": len(self._connections),
                "tasks_total": len(self._task_history),
            }

        @app.get("/api/tasks")
        async def tasks() -> list[dict[str, Any]]:
            return self._task_history[-50:]

        @app.post("/api/task")
        async def submit_task(body: dict[str, Any]) -> dict[str, Any]:
            instruction = body.get("instruction", "")
            if not instruction:
                return {"error": "instruction required"}

            self._task_history.append(
                {
                    "instruction": instruction,
                    "status": "submitted",
                }
            )

            if self._on_task:
                asyncio.create_task(self._on_task(instruction))

            return {"status": "accepted", "instruction": instruction}

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket) -> None:
            await websocket.accept()
            self._connections.append(websocket)
            logger.info("web.ws_connected", total=len(self._connections))

            try:
                while True:
                    # Keep connection alive, listen for client messages
                    data = await websocket.receive_text()
                    # Client can send task instructions via WS too
                    try:
                        msg = json.loads(data)
                        if msg.get("type") == "task" and self._on_task:
                            asyncio.create_task(self._on_task(msg.get("instruction", "")))
                    except json.JSONDecodeError:
                        pass
            except WebSocketDisconnect:
                self._connections.remove(websocket)
                logger.info("web.ws_disconnected", total=len(self._connections))

        return app

    async def _broadcast_event(self, event: Event) -> None:
        """Broadcast events to all connected WebSocket clients."""
        if not self._connections:
            return

        payload = json.dumps(
            {
                "topic": event.topic,
                "data": event.data,
                "source": event.source,
                "task_id": event.task_id,
                "timestamp": event.timestamp.isoformat(),
            }
        )

        disconnected: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self._connections.remove(ws)

    async def start(self, host: str = "0.0.0.0", port: int = 8420) -> None:
        """Start the web server."""
        try:
            import uvicorn  # type: ignore[import-untyped]
        except ImportError:
            raise WebUIError("uvicorn not installed. Run: pip install hauba[web]")

        config = uvicorn.Config(self._app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()

    def _dashboard_html(self) -> str:
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hauba AI Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1117; color: #e0e0e0; }
        .header { background: #1a1d27; padding: 1rem 2rem; border-bottom: 1px solid #2a2d37; }
        .header h1 { color: #58a6ff; font-size: 1.5rem; }
        .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
        .status { display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 0.8rem; }
        .status.online { background: #1a4731; color: #3fb950; }
        .card { background: #1a1d27; border: 1px solid #2a2d37; border-radius: 8px; padding: 1.5rem; margin: 1rem 0; }
        .events { max-height: 500px; overflow-y: auto; font-family: monospace; font-size: 0.85rem; }
        .event { padding: 4px 0; border-bottom: 1px solid #1a1d27; }
        .topic { color: #58a6ff; }
        .timestamp { color: #666; }
        #task-input { width: 100%; padding: 12px; background: #0f1117; border: 1px solid #2a2d37;
                      border-radius: 6px; color: #e0e0e0; font-size: 1rem; }
        button { padding: 10px 20px; background: #238636; color: white; border: none;
                 border-radius: 6px; cursor: pointer; margin-top: 8px; }
        button:hover { background: #2ea043; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Hauba AI Dashboard</h1>
        <span class="status online" id="status">Connecting...</span>
    </div>
    <div class="container">
        <div class="card">
            <h3>Submit Task</h3><br>
            <input id="task-input" placeholder="Describe your task..." />
            <button onclick="submitTask()">Run Task</button>
        </div>
        <div class="card">
            <h3>Live Events</h3><br>
            <div class="events" id="events"></div>
        </div>
    </div>
    <script>
        const ws = new WebSocket(`ws://${location.host}/ws`);
        const eventsDiv = document.getElementById('events');
        const statusEl = document.getElementById('status');

        ws.onopen = () => { statusEl.textContent = 'Online'; };
        ws.onclose = () => { statusEl.textContent = 'Disconnected'; statusEl.className = 'status'; };
        ws.onmessage = (e) => {
            const data = JSON.parse(e.data);
            const div = document.createElement('div');
            div.className = 'event';
            div.innerHTML = `<span class="timestamp">${new Date(data.timestamp).toLocaleTimeString()}</span> <span class="topic">${data.topic}</span> ${JSON.stringify(data.data).slice(0, 120)}`;
            eventsDiv.prepend(div);
            if (eventsDiv.children.length > 200) eventsDiv.lastChild.remove();
        };

        function submitTask() {
            const input = document.getElementById('task-input');
            if (input.value.trim()) {
                ws.send(JSON.stringify({ type: 'task', instruction: input.value }));
                input.value = '';
            }
        }
        document.getElementById('task-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') submitTask();
        });
    </script>
</body>
</html>"""
