"""Hauba API Server — FastAPI-based HTTP service for the Hauba AI Engineer.

This is the Railway-deployed service. Key design:
- BYOK: User sends their API key with every request
- Stateless: No server-side API key storage
- Streaming: SSE for real-time progress updates
- Workspace isolation: Each task gets its own temp directory

Endpoints:
    POST /api/v1/tasks           — Submit a task (returns task_id)
    GET  /api/v1/tasks/{id}      — Get task status and result
    POST /api/v1/tasks/{id}/stream — Stream task events via SSE
    GET  /api/v1/health          — Health check
    GET  /api/v1/models          — List supported models
    GET  /                       — Landing page
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from hauba.engine.types import EngineConfig, EngineEvent, ProviderType

logger = structlog.get_logger()

# ── In-memory task store (Railway is single-instance) ────────────────────────
_tasks: dict[str, dict[str, Any]] = {}


# ── Request/Response Models ──────────────────────────────────────────────────


class TaskRequest(BaseModel):
    """Request to submit a task to the Hauba AI Engineer.

    BYOK: User provides their own API key. Hauba owner pays nothing.
    """

    instruction: str = Field(
        ...,
        description="What to build (plain English)",
        examples=["Build a REST API with authentication using FastAPI"],
    )
    provider: str = Field(
        default="anthropic",
        description="LLM provider: anthropic, openai, azure, ollama",
    )
    api_key: str = Field(
        ...,
        description="Your LLM provider API key (never stored on server)",
    )
    model: str = Field(
        default="claude-sonnet-4-5-20250514",
        description="Model to use",
    )
    base_url: str | None = Field(
        default=None,
        description="Custom API endpoint (for Azure, Ollama, etc.)",
    )
    timeout: float = Field(
        default=300.0,
        description="Max execution time in seconds",
        ge=10.0,
        le=1800.0,
    )
    system_message: str | None = Field(
        default=None,
        description="Additional system prompt to append",
    )


class TaskResponse(BaseModel):
    """Response after submitting a task."""

    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    """Response for task status check."""

    task_id: str
    status: str  # pending, running, completed, failed, cancelled
    output: str | None = None
    error: str | None = None
    events_count: int = 0
    created_at: float
    completed_at: float | None = None
    session_id: str | None = None


class ModelInfo(BaseModel):
    """Information about a supported model."""

    provider: str
    model_id: str
    display_name: str
    description: str


# ── Supported Models ─────────────────────────────────────────────────────────

SUPPORTED_MODELS: list[dict[str, str]] = [
    {
        "provider": "anthropic",
        "model_id": "claude-sonnet-4-5-20250514",
        "display_name": "Claude Sonnet 4.5",
        "description": "Best balance of speed and quality. Recommended.",
    },
    {
        "provider": "anthropic",
        "model_id": "claude-opus-4-6",
        "display_name": "Claude Opus 4.6",
        "description": "Most capable model. Best for complex tasks.",
    },
    {
        "provider": "anthropic",
        "model_id": "claude-haiku-4-5-20251001",
        "display_name": "Claude Haiku 4.5",
        "description": "Fastest model. Great for simple tasks.",
    },
    {
        "provider": "openai",
        "model_id": "gpt-4o",
        "display_name": "GPT-4o",
        "description": "OpenAI's multimodal flagship model.",
    },
    {
        "provider": "openai",
        "model_id": "o3",
        "display_name": "o3",
        "description": "OpenAI's reasoning model.",
    },
    {
        "provider": "ollama",
        "model_id": "qwen2.5-coder:32b",
        "display_name": "Qwen 2.5 Coder 32B",
        "description": "Local model via Ollama. Free.",
    },
]


# ── Helper: Run task in background ───────────────────────────────────────────


async def _run_task(task_id: str, request: TaskRequest) -> None:
    """Execute a task in the background using the Copilot Engine."""
    from hauba.engine.copilot_engine import CopilotEngine

    task = _tasks[task_id]
    task["status"] = "running"

    # Create isolated workspace
    workspace = Path(tempfile.mkdtemp(prefix=f"hauba-{task_id[:8]}-"))
    task["workspace"] = str(workspace)

    # Build engine config (BYOK — user's key, not ours)
    config = EngineConfig(
        provider=ProviderType(request.provider),
        api_key=request.api_key,
        model=request.model,
        base_url=request.base_url,
        working_directory=str(workspace),
        streaming=True,
    )

    # Collect events for the task
    events: list[dict[str, Any]] = []

    def on_event(event: EngineEvent) -> None:
        event_dict = {
            "type": event.type,
            "timestamp": event.timestamp,
        }
        if event.data:
            try:
                # Try to serialize data
                if hasattr(event.data, "__dict__"):
                    event_dict["data"] = str(event.data)
                else:
                    event_dict["data"] = event.data
            except Exception:
                event_dict["data"] = str(event.data)
        events.append(event_dict)
        task["events"] = events

    engine = CopilotEngine(config)

    try:
        await engine.start()
        unsub = engine.on_event(on_event)

        result = await engine.execute(
            instruction=request.instruction,
            timeout=request.timeout,
            system_message=request.system_message,
        )

        unsub()

        task["status"] = "completed" if result.success else "failed"
        task["output"] = result.output
        task["error"] = result.error
        task["session_id"] = result.session_id
        task["completed_at"] = time.time()

    except Exception as e:
        task["status"] = "failed"
        task["error"] = str(e)
        task["completed_at"] = time.time()
        logger.error("api.task_failed", task_id=task_id, error=str(e))
    finally:
        await engine.stop()


# ── FastAPI App ──────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Hauba AI Engineer API",
        description=(
            "AI Software Engineer as a Service. BYOK — bring your own API key. "
            "The AI agent plans, codes, tests, and delivers. Zero hallucinations."
        ),
        version="0.5.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS for browser clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Health ────────────────────────────────────────────────────────────

    @app.get("/api/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "hauba-ai-engineer"}

    @app.get("/health")
    async def health_legacy() -> dict[str, str]:
        return {"status": "ok"}

    # ── Models ────────────────────────────────────────────────────────────

    @app.get("/api/v1/models")
    async def list_models() -> list[dict[str, str]]:
        """List supported models. User brings their own key for any of these."""
        return SUPPORTED_MODELS

    # ── Task Submission ───────────────────────────────────────────────────

    @app.post("/api/v1/tasks", response_model=TaskResponse)
    async def submit_task(request: TaskRequest) -> TaskResponse:
        """Submit a task to the Hauba AI Engineer.

        BYOK: Your API key is used for this request only and never stored.
        """
        # Validate API key is present (except for Ollama)
        if request.provider != "ollama" and not request.api_key:
            raise HTTPException(
                status_code=400,
                detail="API key required. Hauba uses BYOK — bring your own key.",
            )

        # Validate provider
        try:
            ProviderType(request.provider)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown provider: {request.provider}. "
                f"Supported: anthropic, openai, azure, ollama",
            )

        # Create task
        task_id = str(uuid.uuid4())
        _tasks[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "instruction": request.instruction,
            "output": None,
            "error": None,
            "events": [],
            "created_at": time.time(),
            "completed_at": None,
            "session_id": None,
            "workspace": None,
        }

        # Run in background
        asyncio.create_task(_run_task(task_id, request))

        return TaskResponse(
            task_id=task_id,
            status="pending",
            message="Task submitted. Use GET /api/v1/tasks/{task_id} to check status.",
        )

    # ── Task Status ───────────────────────────────────────────────────────

    @app.get("/api/v1/tasks/{task_id}", response_model=TaskStatusResponse)
    async def get_task(task_id: str) -> TaskStatusResponse:
        """Get the status and result of a submitted task."""
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        return TaskStatusResponse(
            task_id=task["task_id"],
            status=task["status"],
            output=task.get("output"),
            error=task.get("error"),
            events_count=len(task.get("events", [])),
            created_at=task["created_at"],
            completed_at=task.get("completed_at"),
            session_id=task.get("session_id"),
        )

    # ── Task Events Stream (SSE) ─────────────────────────────────────────

    @app.get("/api/v1/tasks/{task_id}/stream")
    async def stream_task(task_id: str) -> StreamingResponse:
        """Stream task events via Server-Sent Events (SSE).

        Connect to this endpoint to receive real-time updates as the AI
        engineer works on your task.
        """
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        async def event_generator():
            last_index = 0
            while True:
                events = task.get("events", [])
                status = task.get("status", "pending")

                # Send new events
                while last_index < len(events):
                    event = events[last_index]
                    data = json.dumps(event, default=str)
                    yield f"data: {data}\n\n"
                    last_index += 1

                # Check if task is done
                if status in ("completed", "failed", "cancelled"):
                    final = {
                        "type": f"task.{status}",
                        "output": task.get("output", ""),
                        "error": task.get("error"),
                    }
                    yield f"data: {json.dumps(final, default=str)}\n\n"
                    break

                await asyncio.sleep(0.5)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ── Landing Page ──────────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def landing_page() -> str:
        """Landing page with API documentation links."""
        return _LANDING_HTML

    # ── Version (backwards compat with old server.py) ─────────────────────

    @app.get("/api/version")
    async def api_version() -> dict[str, Any]:
        return {
            "version": "v0.2.0",
            "label": "AI Engineer API",
            "prerelease": False,
        }

    return app


# ── Landing Page HTML ────────────────────────────────────────────────────────

_LANDING_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Hauba AI Engineer API</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #0a0a0f; color: #f5f5f7; min-height: 100vh;
      display: flex; align-items: center; justify-content: center;
    }
    .container { max-width: 640px; padding: 3rem 2rem; text-align: center; }
    h1 { font-size: 2.5rem; font-weight: 900; margin-bottom: 0.5rem; }
    h1 span { color: #6C5CE7; }
    .subtitle { color: #6e6e78; font-size: 1.1rem; margin-bottom: 2rem; }
    .badge {
      display: inline-block; background: rgba(108,92,231,0.12);
      border: 1px solid rgba(108,92,231,0.25); border-radius: 20px;
      padding: 0.3rem 1rem; font-size: 0.8rem; font-weight: 600;
      color: #6C5CE7; margin-bottom: 2rem;
    }
    .card {
      background: #111118; border: 1px solid #1f1f2a; border-radius: 12px;
      padding: 1.5rem; margin-bottom: 1.5rem; text-align: left;
    }
    .card h3 { font-size: 0.9rem; margin-bottom: 0.8rem; color: #6C5CE7; }
    pre {
      background: #0d0d14; border-radius: 8px; padding: 1rem;
      font-family: 'JetBrains Mono', monospace; font-size: 0.8rem;
      overflow-x: auto; color: #b0b0b8; line-height: 1.6;
    }
    .key { color: #6C5CE7; }
    .str { color: #64b5f6; }
    .links { display: flex; gap: 1rem; justify-content: center; margin-top: 2rem; }
    .links a {
      color: #6C5CE7; text-decoration: none; font-size: 0.9rem;
      font-weight: 600; padding: 0.5rem 1.2rem; border-radius: 8px;
      border: 1px solid rgba(108,92,231,0.3); transition: all 0.2s;
    }
    .links a:hover { background: rgba(108,92,231,0.1); }
    .byok {
      color: #4caf50; font-size: 0.85rem; font-weight: 600;
      margin-top: 1rem;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>H<span>AU</span>BA</h1>
    <div class="badge">AI Engineer API v0.2.0</div>
    <p class="subtitle">
      AI Software Engineer as a Service.<br>
      Bring your own API key. We never store it.
    </p>

    <div class="card">
      <h3>Quick Start</h3>
      <pre><span class="key">POST</span> /api/v1/tasks

{
  <span class="key">"instruction"</span>: <span class="str">"Build a REST API with auth"</span>,
  <span class="key">"provider"</span>: <span class="str">"anthropic"</span>,
  <span class="key">"api_key"</span>: <span class="str">"sk-ant-your-key"</span>,
  <span class="key">"model"</span>: <span class="str">"claude-sonnet-4-5-20250514"</span>
}</pre>
      <p class="byok">BYOK — Your key, your costs, your data. We never store API keys.</p>
    </div>

    <div class="card">
      <h3>Stream Events</h3>
      <pre><span class="key">GET</span> /api/v1/tasks/{task_id}/stream

<span class="str">→ SSE: real-time agent events</span>
<span class="str">→ tool calls, file edits, progress</span>
<span class="str">→ final output on completion</span></pre>
    </div>

    <div class="links">
      <a href="/docs">API Docs</a>
      <a href="/redoc">ReDoc</a>
      <a href="https://github.com/NikeGunn/haubaa">GitHub</a>
      <a href="https://pypi.org/project/hauba/">PyPI</a>
    </div>
  </div>
</body>
</html>
"""
