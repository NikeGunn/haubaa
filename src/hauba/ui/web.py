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
        from hauba import __version__

        app = FastAPI(title="Hauba AI Dashboard", version=__version__)

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
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --cyan: #00d4ff; --purple: #7b2fff; --pink: #ff2d87; --green: #00ff88;
            --bg: #050508; --bg-card: #0c0c18; --bg-input: #08080f;
            --border: #1a1a2e; --border-hover: #2a2a4e;
            --text: #f0f0f5; --text-dim: #8888aa; --text-muted: #555577;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', -apple-system, system-ui, sans-serif;
            background: var(--bg); color: var(--text);
            min-height: 100vh;
        }

        /* Grid background */
        body::before {
            content: ''; position: fixed; inset: 0; z-index: 0; pointer-events: none;
            background-image:
                linear-gradient(rgba(123,47,255,0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(123,47,255,0.03) 1px, transparent 1px);
            background-size: 50px 50px;
        }

        /* Header */
        .header {
            position: sticky; top: 0; z-index: 100;
            backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
            background: rgba(5,5,8,0.85);
            border-bottom: 1px solid var(--border);
            padding: 0.8rem 1.5rem;
            display: flex; align-items: center; justify-content: space-between;
        }
        .header-left { display: flex; align-items: center; gap: 1rem; }
        .header h1 {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.1rem; font-weight: 700;
            background: linear-gradient(135deg, var(--cyan), var(--purple));
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .header-subtitle { font-size: 0.75rem; color: var(--text-muted); font-weight: 400; }
        .status-pill {
            display: flex; align-items: center; gap: 0.4rem;
            padding: 0.3rem 0.8rem; border-radius: 20px;
            font-size: 0.72rem; font-weight: 600;
            background: rgba(0,255,136,0.08); color: var(--green);
            border: 1px solid rgba(0,255,136,0.15);
            transition: all 0.3s;
        }
        .status-pill .dot {
            width: 6px; height: 6px; border-radius: 50%; background: var(--green);
            animation: pulse 2s ease-in-out infinite;
        }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
        .status-pill.offline {
            background: rgba(255,60,60,0.08); color: #ff4444;
            border-color: rgba(255,60,60,0.15);
        }
        .status-pill.offline .dot { background: #ff4444; animation: none; }

        /* Layout */
        .container {
            position: relative; z-index: 1;
            max-width: 960px; margin: 0 auto;
            padding: 1.5rem;
            display: grid; grid-template-columns: 1fr; gap: 1.2rem;
        }
        @media (min-width: 768px) {
            .container { grid-template-columns: 1fr 1fr; }
            .task-card { grid-column: 1 / -1; }
        }

        /* Cards */
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            transition: border-color 0.2s;
        }
        .card:hover { border-color: var(--border-hover); }
        .card-header {
            padding: 1rem 1.2rem 0.8rem;
            display: flex; align-items: center; justify-content: space-between;
            border-bottom: 1px solid var(--border);
        }
        .card-header h3 {
            font-size: 0.82rem; font-weight: 600; color: var(--text);
            display: flex; align-items: center; gap: 0.5rem;
        }
        .card-header .icon {
            width: 28px; height: 28px; border-radius: 8px;
            display: flex; align-items: center; justify-content: center;
            font-size: 0.85rem;
        }
        .icon-cyan { background: rgba(0,212,255,0.1); color: var(--cyan); }
        .icon-purple { background: rgba(123,47,255,0.1); color: var(--purple); }
        .icon-pink { background: rgba(255,45,135,0.1); color: var(--pink); }
        .icon-green { background: rgba(0,255,136,0.1); color: var(--green); }
        .card-body { padding: 1.2rem; }

        /* Task input */
        .task-input-wrap {
            display: flex; gap: 0.8rem; align-items: stretch;
        }
        #task-input {
            flex: 1; padding: 0.75rem 1rem;
            background: var(--bg-input); border: 1px solid var(--border);
            border-radius: 8px; color: var(--text);
            font-family: 'Inter', sans-serif; font-size: 0.9rem;
            transition: border-color 0.2s; outline: none;
        }
        #task-input:focus { border-color: var(--purple); box-shadow: 0 0 0 3px rgba(123,47,255,0.1); }
        #task-input::placeholder { color: var(--text-muted); }
        .btn-run {
            padding: 0.75rem 1.5rem;
            background: linear-gradient(135deg, var(--purple), var(--pink));
            color: white; border: none; border-radius: 8px;
            font-family: 'Inter', sans-serif; font-size: 0.85rem;
            font-weight: 600; cursor: pointer;
            transition: all 0.2s;
            white-space: nowrap;
        }
        .btn-run:hover { transform: translateY(-1px); box-shadow: 0 4px 20px rgba(123,47,255,0.3); }
        .btn-run:active { transform: translateY(0); }

        /* Stats */
        .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.8rem; }
        .stat {
            text-align: center; padding: 0.8rem 0.5rem;
            background: rgba(255,255,255,0.02); border-radius: 8px;
        }
        .stat-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.5rem; font-weight: 700;
            background: linear-gradient(135deg, var(--cyan), var(--purple));
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .stat-label { font-size: 0.68rem; color: var(--text-muted); margin-top: 0.2rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; }

        /* Events */
        .events {
            max-height: 400px; overflow-y: auto;
            scrollbar-width: thin; scrollbar-color: var(--border) transparent;
        }
        .events::-webkit-scrollbar { width: 4px; }
        .events::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
        .event {
            padding: 0.5rem 0; border-bottom: 1px solid rgba(26,26,46,0.5);
            font-size: 0.78rem; line-height: 1.5;
            display: flex; gap: 0.6rem; align-items: flex-start;
        }
        .event:last-child { border-bottom: none; }
        .event-time {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem; color: var(--text-muted);
            white-space: nowrap; padding-top: 1px;
        }
        .event-topic {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem; font-weight: 600;
            padding: 0.1rem 0.5rem; border-radius: 4px;
            white-space: nowrap;
        }
        .event-topic.thinking { background: rgba(0,212,255,0.1); color: var(--cyan); }
        .event-topic.executing { background: rgba(123,47,255,0.1); color: var(--purple); }
        .event-topic.complete { background: rgba(0,255,136,0.1); color: var(--green); }
        .event-topic.error { background: rgba(255,60,60,0.1); color: #ff4444; }
        .event-topic.default { background: rgba(255,255,255,0.04); color: var(--text-dim); }
        .event-data {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem; color: var(--text-dim);
            word-break: break-all;
        }
        .events-empty {
            text-align: center; padding: 3rem 1rem;
            color: var(--text-muted); font-size: 0.85rem;
        }
        .events-empty .empty-icon { font-size: 2rem; margin-bottom: 0.5rem; opacity: 0.3; }

        /* Agent activity */
        .agent-list { display: flex; flex-direction: column; gap: 0.6rem; }
        .agent-item {
            display: flex; align-items: center; gap: 0.8rem;
            padding: 0.6rem 0.8rem; border-radius: 8px;
            background: rgba(255,255,255,0.02);
        }
        .agent-avatar {
            width: 32px; height: 32px; border-radius: 8px;
            display: flex; align-items: center; justify-content: center;
            font-size: 0.8rem; font-weight: 700;
        }
        .agent-info { flex: 1; }
        .agent-name { font-size: 0.8rem; font-weight: 600; }
        .agent-status { font-size: 0.68rem; color: var(--text-muted); }

        /* No events placeholder */
        .placeholder-text { color: var(--text-muted); font-size: 0.82rem; text-align: center; padding: 2rem; }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-left">
            <h1>HAUBA</h1>
            <span class="header-subtitle">AI Agent Dashboard</span>
        </div>
        <div class="status-pill" id="status">
            <span class="dot"></span>
            <span id="status-text">Connecting...</span>
        </div>
    </div>

    <div class="container">
        <!-- Task Input -->
        <div class="card task-card">
            <div class="card-header">
                <h3><span class="icon icon-purple">&#x25B6;</span> New Task</h3>
            </div>
            <div class="card-body">
                <div class="task-input-wrap">
                    <input id="task-input" placeholder="Describe what you want to build..." />
                    <button class="btn-run" onclick="submitTask()">Run Task</button>
                </div>
            </div>
        </div>

        <!-- Stats -->
        <div class="card">
            <div class="card-header">
                <h3><span class="icon icon-cyan">&#x2B21;</span> Metrics</h3>
            </div>
            <div class="card-body">
                <div class="stats-grid">
                    <div class="stat">
                        <div class="stat-value" id="stat-tasks">0</div>
                        <div class="stat-label">Tasks</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value" id="stat-events">0</div>
                        <div class="stat-label">Events</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value" id="stat-conns">1</div>
                        <div class="stat-label">Clients</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Agents -->
        <div class="card">
            <div class="card-header">
                <h3><span class="icon icon-green">&#x2B22;</span> Agents</h3>
            </div>
            <div class="card-body">
                <div class="agent-list">
                    <div class="agent-item">
                        <div class="agent-avatar icon-purple" style="background:rgba(123,47,255,0.15);color:var(--purple);">D</div>
                        <div class="agent-info">
                            <div class="agent-name">Director</div>
                            <div class="agent-status">Waiting for task...</div>
                        </div>
                    </div>
                    <div class="agent-item">
                        <div class="agent-avatar" style="background:rgba(0,212,255,0.15);color:var(--cyan);">S</div>
                        <div class="agent-info">
                            <div class="agent-name">SubAgent</div>
                            <div class="agent-status">Idle</div>
                        </div>
                    </div>
                    <div class="agent-item">
                        <div class="agent-avatar" style="background:rgba(0,255,136,0.15);color:var(--green);">W</div>
                        <div class="agent-info">
                            <div class="agent-name">Worker</div>
                            <div class="agent-status">Idle</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Events -->
        <div class="card" style="grid-column: 1 / -1;">
            <div class="card-header">
                <h3><span class="icon icon-pink">&#x26A1;</span> Live Events</h3>
                <span style="font-size:0.7rem;color:var(--text-muted);" id="event-count">0 events</span>
            </div>
            <div class="card-body">
                <div class="events" id="events">
                    <div class="events-empty">
                        <div class="empty-icon">&#x2B21;</div>
                        <div>No events yet. Submit a task to get started.</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let eventCount = 0;
        const ws = new WebSocket(`ws://${location.host}/ws`);
        const eventsDiv = document.getElementById('events');
        const statusEl = document.getElementById('status');
        const statusText = document.getElementById('status-text');

        ws.onopen = () => {
            statusText.textContent = 'Online';
            statusEl.classList.remove('offline');
        };
        ws.onclose = () => {
            statusText.textContent = 'Disconnected';
            statusEl.classList.add('offline');
        };
        ws.onmessage = (e) => {
            const data = JSON.parse(e.data);
            // Clear placeholder
            const empty = eventsDiv.querySelector('.events-empty');
            if (empty) empty.remove();

            eventCount++;
            document.getElementById('stat-events').textContent = eventCount;
            document.getElementById('event-count').textContent = eventCount + ' events';

            const topicClass = data.topic.includes('think') ? 'thinking'
                : data.topic.includes('execut') ? 'executing'
                : data.topic.includes('complet') || data.topic.includes('done') ? 'complete'
                : data.topic.includes('error') || data.topic.includes('fail') ? 'error'
                : 'default';

            const div = document.createElement('div');
            div.className = 'event';
            div.innerHTML = `<span class="event-time">${new Date(data.timestamp).toLocaleTimeString()}</span>` +
                `<span class="event-topic ${topicClass}">${data.topic}</span>` +
                `<span class="event-data">${JSON.stringify(data.data).slice(0, 120)}</span>`;
            eventsDiv.prepend(div);
            if (eventsDiv.children.length > 200) eventsDiv.lastChild.remove();
        };

        function submitTask() {
            const input = document.getElementById('task-input');
            if (input.value.trim()) {
                ws.send(JSON.stringify({ type: 'task', instruction: input.value }));
                const tasks = parseInt(document.getElementById('stat-tasks').textContent) + 1;
                document.getElementById('stat-tasks').textContent = tasks;
                input.value = '';
            }
        }
        document.getElementById('task-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') submitTask();
        });
    </script>
</body>
</html>"""
