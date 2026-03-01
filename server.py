"""Hauba.tech — Landing page + AI Engineer API server.

Serves:
  GET /              → Beautiful landing page (same as before)
  GET /install.sh    → Bash installer
  GET /install.ps1   → PowerShell installer
  GET /health        → Health check
  GET /favicon.png   → Favicon
  GET /api/version   → Latest GitHub release info
  POST /api/v1/tasks → Submit AI engineering task (BYOK)
  GET /api/v1/tasks/{id} → Task status
  GET /api/v1/tasks/{id}/stream → SSE event stream
  GET /api/v1/models → Supported models
  GET /docs          → Swagger API docs
  GET /redoc         → ReDoc API docs

Architecture:
  Core Engine: GitHub Copilot SDK (production-tested agent runtime)
  BYOK: Users bring their own API key. Hauba owner pays ZERO.
"""

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

# ── Pre-flight: ensure copilot CLI is available ─────────────────────────────


def _ensure_copilot_sdk() -> None:
    """Verify the Copilot SDK is available (installed via pip)."""
    try:
        import copilot  # noqa: F401

        print("[hauba] Copilot SDK available.")
    except ImportError:
        print("[hauba] Copilot SDK not found. Installing via pip...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "github-copilot-sdk"],
                check=True,
                timeout=120,
                capture_output=True,
                text=True,
            )
            print("[hauba] Copilot SDK installed successfully.")
        except Exception as e:
            print(f"[hauba] Warning: Could not install Copilot SDK: {e}")
            print("[hauba] API will serve but task execution may fail.")


# ── GitHub release cache ─────────────────────────────────────────────────────

GITHUB_REPO = "NikeGunn/haubaa"
_release_cache: dict = {}
_release_cache_lock = threading.Lock()
_CACHE_TTL = 300  # seconds (5 min)


def _fetch_latest_release() -> dict:
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "hauba.tech/2.0"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())


def get_release_info() -> dict:
    with _release_cache_lock:
        now = time.monotonic()
        if _release_cache.get("expires", 0) > now:
            return _release_cache["data"]
        try:
            data = _fetch_latest_release()
            tag = data.get("tag_name", "v0.2.0")
            prerelease = data.get("prerelease", False)
            parts = tag.lstrip("v").split(".")
            is_beta = prerelease or (parts[0] == "0")
            label = "Public Beta" if is_beta else "Stable"
            result = {"version": tag, "label": label, "prerelease": prerelease}
        except Exception as exc:
            print(f"[hauba] GitHub release fetch failed: {exc}")
            result = {"version": "v0.2.0", "label": "Public Beta", "prerelease": False}
        _release_cache["data"] = result
        _release_cache["expires"] = now + _CACHE_TTL
        return result


# ── FastAPI App ──────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent

# Load install scripts
_install_sh_path = BASE_DIR / "install.sh"
_install_ps1_path = BASE_DIR / "install.ps1"
INSTALL_SH = (
    _install_sh_path.read_text(encoding="utf-8")
    if _install_sh_path.exists()
    else "echo 'pip install hauba'"
)
INSTALL_PS1 = (
    _install_ps1_path.read_text(encoding="utf-8")
    if _install_ps1_path.exists()
    else "pip install hauba"
)

# Load favicon
_favicon_path = BASE_DIR / "static" / "favicon.png"
FAVICON_BYTES: bytes | None = _favicon_path.read_bytes() if _favicon_path.exists() else None

# Load landing page HTML
_landing_html_path = BASE_DIR / "static" / "landing.html"


def _get_landing_html() -> str:
    """Get the landing page HTML (from file or inline fallback)."""
    if _landing_html_path.exists():
        return _landing_html_path.read_text(encoding="utf-8")
    return LANDING_PAGE


def create_server_app():
    """Create the combined landing page + AI Engineer API."""
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, Response

    app = FastAPI(
        title="Hauba AI Engineer",
        description=(
            "AI Software Engineer as a Service. BYOK — bring your own API key. "
            "Powered by GitHub Copilot SDK."
        ),
        version="0.2.1",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Landing page ──────────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def landing():
        return _get_landing_html()

    # ── Install scripts ───────────────────────────────────────────────────

    @app.get("/install.sh")
    async def install_sh():
        return Response(content=INSTALL_SH, media_type="text/plain")

    @app.get("/install.ps1")
    async def install_ps1():
        return Response(content=INSTALL_PS1, media_type="text/plain")

    # ── Static assets ─────────────────────────────────────────────────────

    @app.get("/favicon.png")
    async def favicon():
        if FAVICON_BYTES:
            return Response(
                content=FAVICON_BYTES,
                media_type="image/png",
                headers={"Cache-Control": "public, max-age=86400"},
            )
        return Response(status_code=404)

    # ── Health check ──────────────────────────────────────────────────────

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/health")
    async def health_v1():
        return {"status": "ok", "service": "hauba-ai-engineer", "engine": "copilot-sdk"}

    # ── Version ───────────────────────────────────────────────────────────

    @app.get("/api/version")
    async def api_version():
        return get_release_info()

    # ── AI Engineer API ───────────────────────────────────────────────────

    try:
        from hauba.api.server import (
            SUPPORTED_MODELS,
            TaskRequest,
            TaskResponse,
            TaskStatusResponse,
            _run_task,
            _tasks,
        )

        @app.get("/api/v1/models")
        async def list_models():
            return SUPPORTED_MODELS

        @app.post("/api/v1/tasks", response_model=TaskResponse)
        async def submit_task(request: TaskRequest):
            import uuid

            from hauba.engine.types import ProviderType

            if request.provider != "ollama" and not request.api_key:
                from fastapi import HTTPException

                raise HTTPException(400, "API key required (BYOK).")

            try:
                ProviderType(request.provider)
            except ValueError:
                from fastapi import HTTPException

                raise HTTPException(400, f"Unknown provider: {request.provider}")

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

            asyncio.create_task(_run_task(task_id, request))

            return TaskResponse(
                task_id=task_id,
                status="pending",
                message="Task submitted. GET /api/v1/tasks/{task_id} to check status.",
            )

        @app.get("/api/v1/tasks/{task_id}", response_model=TaskStatusResponse)
        async def get_task(task_id: str):
            from fastapi import HTTPException

            task = _tasks.get(task_id)
            if not task:
                raise HTTPException(404, "Task not found")

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

        @app.get("/api/v1/tasks/{task_id}/stream")
        async def stream_task(task_id: str):
            from fastapi import HTTPException
            from fastapi.responses import StreamingResponse

            task = _tasks.get(task_id)
            if not task:
                raise HTTPException(404, "Task not found")

            async def event_generator():
                last_index = 0
                while True:
                    events = task.get("events", [])
                    status = task.get("status", "pending")

                    while last_index < len(events):
                        event = events[last_index]
                        data = json.dumps(event, default=str)
                        yield f"data: {data}\n\n"
                        last_index += 1

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

        print("[hauba] AI Engineer API endpoints loaded.")
    except ImportError as e:
        print(f"[hauba] Warning: API module not available: {e}")
        print("[hauba] Landing page and install scripts will still work.")

    # ── WhatsApp Webhook (hidden from docs) ───────────────────────────────
    try:
        from hauba.channels.whatsapp_webhook import WhatsAppBot

        _wa_bot = WhatsAppBot()
        _wa_enabled = _wa_bot.configure()

        if _wa_enabled:

            @app.post("/whatsapp/webhook", include_in_schema=False)
            async def whatsapp_webhook(request: Request):
                """Receive incoming WhatsApp messages from Twilio."""
                form = await request.form()
                params = {k: str(v) for k, v in form.items()}

                body = params.get("Body", "")
                from_number = params.get("From", "")
                message_sid = params.get("MessageSid", "")

                if not body or not from_number:
                    return Response(content="", status_code=200)

                # Validate Twilio signature
                # Use X-Forwarded-* headers to reconstruct the public URL
                # (Railway/proxies rewrite the URL to internal host:port)
                signature = request.headers.get("X-Twilio-Signature", "")
                if signature:
                    forwarded_proto = request.headers.get("X-Forwarded-Proto", request.url.scheme)
                    forwarded_host = request.headers.get(
                        "X-Forwarded-Host",
                        request.headers.get("Host", request.url.hostname or ""),
                    )
                    webhook_url = f"{forwarded_proto}://{forwarded_host}{request.url.path}"
                    if not _wa_bot.validate_signature(webhook_url, params, signature):
                        return Response(content="Invalid signature", status_code=403)

                # ACK immediately, process in background
                asyncio.create_task(_wa_bot.handle_message(body, from_number, message_sid))
                return Response(content="", status_code=200)

            @app.get("/whatsapp/status", include_in_schema=False)
            async def whatsapp_status():
                """Check WhatsApp bot status (hidden from docs)."""
                return {
                    "enabled": True,
                    "active_sessions": _wa_bot.session_count,
                }

            # Start session cleanup loop on first request
            _wa_cleanup_started = False

            @app.middleware("http")
            async def _wa_cleanup_middleware(request: Request, call_next):
                nonlocal _wa_cleanup_started
                if not _wa_cleanup_started:
                    _wa_cleanup_started = True
                    await _wa_bot.start_cleanup_loop()
                return await call_next(request)

            print("[hauba] WhatsApp webhook enabled at /whatsapp/webhook")
        else:
            print("[hauba] WhatsApp webhook not configured (missing env vars).")
    except ImportError:
        print("[hauba] WhatsApp webhook not available (twilio not installed).")
    except Exception as e:
        print(f"[hauba] WhatsApp webhook error: {e}")

    # ── Hide Swagger/ReDoc from public access ─────────────────────────────
    # Disable OpenAPI docs for security (FAANG-style private API)
    app.openapi_url = None  # type: ignore[assignment]

    return app


# ── Original Landing Page (inline fallback) ──────────────────────────────────
# This is the same beautiful landing page from before.

LANDING_PAGE = """\
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Hauba — Your AI Engineering Company</title>
  <meta name="description" content="Stop hiring. Start shipping. Hauba is an AI engineering team that builds real software, not chatbot responses. One command. Production code. Open-source.">
  <link rel="icon" type="image/png" href="/favicon.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --accent: #6C5CE7;
      --accent-soft: rgba(108,92,231,0.12);
      --accent-glow: rgba(108,92,231,0.25);
      --accent-text: #fff;
    }
    [data-theme="dark"] {
      --white: #f5f5f7;
      --gray-1: #b0b0b8;
      --gray-2: #6e6e78;
      --gray-3: #3a3a44;
      --gray-4: #1c1c24;
      --bg: #0a0a0f;
      --bg-card: #111118;
      --bg-elevated: #16161f;
      --border: #1f1f2a;
      --border-hover: #2e2e3c;
      --code-bg: #0d0d14;
      --shadow-panel: rgba(0,0,0,0.5);
      --glow-bg: rgba(108,92,231,0.06);
      --noise-opacity: 0.025;
      --mascot-eye: #0a0a0f;
      --mascot-mouth: #1a0505;
      --mascot-mouth-inner: #0a0000;
      --success: #4caf50;
      --fn-color: #64b5f6;
    }
    [data-theme="light"] {
      --white: #111118;
      --gray-1: #3a3a44;
      --gray-2: #6e6e78;
      --gray-3: #a0a0b0;
      --gray-4: #d0d0da;
      --bg: #f5f5f8;
      --bg-card: #ffffff;
      --bg-elevated: #f0f0f5;
      --border: #e0e0ea;
      --border-hover: #c8c8d8;
      --code-bg: #eeeef4;
      --shadow-panel: rgba(0,0,0,0.1);
      --glow-bg: rgba(108,92,231,0.04);
      --noise-opacity: 0.015;
      --mascot-eye: #1a1a2e;
      --mascot-mouth: #2a1525;
      --mascot-mouth-inner: #1a0a15;
      --success: #2e7d32;
      --fn-color: #1565c0;
      --accent-text: #fff;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg); color: var(--white);
      min-height: 100vh; overflow-x: hidden;
      -webkit-font-smoothing: antialiased;
      transition: background 0.3s ease, color 0.3s ease;
    }
    .bg-noise {
      position: fixed; inset: 0; z-index: 0; pointer-events: none; opacity: var(--noise-opacity);
      background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
      background-repeat: repeat; background-size: 256px;
    }
    .bg-glow {
      position: fixed; top: -300px; left: 50%; transform: translateX(-50%);
      width: 800px; height: 600px; z-index: 0; pointer-events: none;
      background: radial-gradient(ellipse, var(--glow-bg) 0%, transparent 70%);
    }
    .hero {
      position: relative; z-index: 1;
      min-height: 100vh;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      padding: 4rem 2rem 4rem;
      text-align: center;
    }
    .mascot-wrapper {
      margin-bottom: 2rem;
      position: relative; cursor: pointer;
      width: 120px; height: 148px;
    }
    .mascot-svg {
      width: 120px; height: 148px;
      filter: drop-shadow(0 0 30px var(--accent-glow));
      transition: filter 0.3s;
    }
    .mascot-wrapper:hover .mascot-svg {
      filter: drop-shadow(0 0 50px rgba(108,92,231,0.5));
    }
    .mascot-hover-panel {
      position: absolute;
      top: 50%; left: calc(100% + 16px);
      transform: translateY(-50%) scale(0.9);
      width: 240px; opacity: 0; pointer-events: none;
      transition: all 0.3s cubic-bezier(.34,1.56,.64,1);
      transform-origin: left center;
      z-index: 10;
    }
    .mascot-wrapper:hover .mascot-hover-panel {
      opacity: 1; transform: translateY(-50%) scale(1);
    }
    .mhp-inner {
      background: var(--bg-card); border: 1px solid var(--border);
      border-radius: 10px; padding: 0.75rem 1rem;
      font-family: 'JetBrains Mono', monospace; font-size: 0.65rem;
      text-align: left; position: relative;
      box-shadow: 0 8px 40px var(--shadow-panel);
    }
    .mhp-inner::after {
      content: ''; position: absolute; top: 50%; left: -7px; transform: translateY(-50%);
      width: 0; height: 0;
      border-top: 7px solid transparent; border-bottom: 7px solid transparent;
      border-right: 7px solid var(--border);
    }
    .mhp-inner::before {
      content: ''; position: absolute; top: 50%; left: -6px; transform: translateY(-50%);
      width: 0; height: 0;
      border-top: 6px solid transparent; border-bottom: 6px solid transparent;
      border-right: 6px solid var(--bg-card); z-index: 1;
    }
    .mhp-bar { display: flex; gap: 4px; margin-bottom: 6px; }
    .mhp-dot { width: 7px; height: 7px; border-radius: 50%; }
    .mhp-dot.r { background: #ff5f57; }
    .mhp-dot.y { background: #ffbd2e; }
    .mhp-dot.g { background: #28c840; }
    .mhp-file { font-size: 0.58rem; color: var(--gray-2); margin-bottom: 5px; }
    .mhp-line { margin: 1px 0; color: var(--gray-1); }
    .mhp-line .c-kw { color: var(--accent); }
    .mhp-line .c-fn { color: var(--fn-color); }
    .mhp-line .c-cm { color: var(--gray-3); }
    .mhp-status {
      margin-top: 6px; padding-top: 5px; border-top: 1px solid var(--border);
      font-size: 0.58rem; color: var(--success);
      display: flex; align-items: center; gap: 4px;
    }
    .mhp-cursor {
      display: inline-block; width: 5px; height: 0.8em;
      background: var(--accent); vertical-align: text-bottom;
      animation: cursorBlink 0.7s step-end infinite;
    }
    @keyframes cursorBlink { 0%,100% { opacity: 1; } 50% { opacity: 0; } }
    @keyframes bodyBounce {
      0%,100% { transform: translateY(0); }
      50% { transform: translateY(-5px); }
    }
    .mascot-body-group { animation: bodyBounce 2.2s ease-in-out infinite; }
    @keyframes eyeLook {
      0%,18% { transform: translate(0,0); }
      22%,34% { transform: translate(3px,-1px); }
      38%,52% { transform: translate(-3px,1px); }
      56%,68% { transform: translate(2px,2px); }
      72%,84% { transform: translate(-2px,-1px); }
      88%,100% { transform: translate(0,0); }
    }
    .eye-pupil { animation: eyeLook 4.5s ease-in-out infinite; }
    @keyframes blink {
      0%,40%,42%,100% { transform: scaleY(1); }
      41% { transform: scaleY(0.05); }
    }
    .eye-blink { animation: blink 4s infinite; transform-origin: center; }
    .eye-blink-r { animation: blink 4s infinite 0.6s; transform-origin: center; }
    @keyframes bellyJiggle {
      0%,100% { transform: scaleX(1) scaleY(1); }
      30% { transform: scaleX(1.015) scaleY(0.985); }
      65% { transform: scaleX(0.985) scaleY(1.015); }
    }
    .belly { animation: bellyJiggle 2.1s ease-in-out infinite; transform-origin: center 60%; }
    @keyframes armWaveL {
      0%,100% { transform: rotate(0deg); } 30% { transform: rotate(-18deg); } 65% { transform: rotate(6deg); }
    }
    @keyframes armWaveR {
      0%,100% { transform: rotate(0deg); } 30% { transform: rotate(18deg); } 65% { transform: rotate(-6deg); }
    }
    .arm-left { animation: armWaveL 2.6s ease-in-out infinite; transform-origin: 36px 70px; }
    .arm-right { animation: armWaveR 2.6s ease-in-out infinite 0.4s; transform-origin: 95px 70px; }
    .logo {
      font-family: 'Inter', sans-serif;
      font-size: 5.5rem; font-weight: 900; letter-spacing: -0.03em;
      color: var(--white);
      margin-bottom: 0.2rem; position: relative;
      line-height: 1;
    }
    .logo span {
      background: linear-gradient(135deg, var(--accent) 0%, #a29bfe 100%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .version-tag {
      display: inline-block; background: var(--accent-soft);
      border: 1px solid rgba(108,92,231,0.25); border-radius: 20px;
      padding: 0.2rem 0.8rem; font-size: 0.7rem; font-weight: 600;
      color: var(--accent); margin-bottom: 1.5rem; letter-spacing: 0.04em;
    }
    .hero-tagline {
      font-size: 1.4rem; font-weight: 300; color: var(--gray-1);
      max-width: 580px; line-height: 1.6; margin-bottom: 0.6rem;
    }
    .hero-tagline strong { color: var(--white); font-weight: 600; }
    .hero-sub {
      font-size: 1rem; color: var(--gray-2); max-width: 480px;
      line-height: 1.6; margin-bottom: 2.5rem;
    }
    .terminal {
      width: 100%; max-width: 540px;
      background: var(--code-bg); border: 1px solid var(--border);
      border-radius: 12px; overflow: hidden; margin-bottom: 2.5rem;
      text-align: left;
    }
    .terminal-bar {
      display: flex; align-items: center; gap: 6px;
      padding: 0.7rem 1rem; border-bottom: 1px solid var(--border);
      background: var(--bg-card);
    }
    .terminal-dot { width: 10px; height: 10px; border-radius: 50%; }
    .terminal-dot.r { background: #ff5f57; }
    .terminal-dot.y { background: #ffbd2e; }
    .terminal-dot.g { background: #28c840; }
    .terminal-title {
      flex: 1; text-align: center;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.68rem; color: var(--gray-3);
    }
    .terminal-body {
      padding: 1.2rem 1.4rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.82rem; line-height: 1.8;
    }
    .t-prompt { color: var(--accent); }
    .t-cmd { color: var(--white); }
    .t-output { color: var(--gray-2); }
    .t-success { color: var(--success); }
    .t-cursor {
      display: inline-block; width: 8px; height: 1.1em;
      background: var(--accent); vertical-align: text-bottom;
      animation: cursorBlink 0.8s step-end infinite;
    }
    .download-section { width: 100%; max-width: 540px; margin-bottom: 2.5rem; }
    .download-auto {
      display: flex; align-items: center; justify-content: center; gap: 0.6rem;
      padding: 0.85rem 2rem;
      background: var(--accent); color: var(--accent-text);
      border: none; border-radius: 10px; cursor: pointer;
      font-family: 'Inter', sans-serif; font-size: 0.95rem; font-weight: 700;
      transition: all 0.2s; width: 100%;
      box-shadow: 0 4px 24px var(--accent-glow);
    }
    .download-auto:hover { transform: translateY(-2px); box-shadow: 0 8px 36px rgba(108,92,231,0.35); }
    .download-auto svg { flex-shrink: 0; }
    .download-other {
      text-align: center; margin-top: 0.7rem;
      font-size: 0.75rem; color: var(--gray-3);
    }
    .download-other a { color: var(--gray-2); text-decoration: none; transition: color 0.2s; }
    .download-other a:hover { color: var(--accent); }
    .install-options {
      display: none; margin-top: 1rem;
      background: var(--code-bg); border: 1px solid var(--border);
      border-radius: 10px; overflow: hidden;
    }
    .install-options.open { display: block; }
    .install-opt {
      display: flex; align-items: center; justify-content: space-between;
      padding: 0.75rem 1.2rem;
      border-bottom: 1px solid var(--border);
      font-family: 'JetBrains Mono', monospace; font-size: 0.78rem;
    }
    .install-opt:last-child { border-bottom: none; }
    .install-opt-label { color: var(--gray-2); font-size: 0.7rem; font-weight: 600; min-width: 90px; font-family: 'Inter', sans-serif; }
    .install-opt-cmd { color: var(--accent); flex: 1; margin: 0 1rem; word-break: break-all; }
    .install-opt .copy-btn {
      background: rgba(108,92,231,0.1); border: 1px solid rgba(108,92,231,0.2);
      color: var(--accent); border-radius: 5px; padding: 0.25rem 0.55rem;
      font-size: 0.65rem; cursor: pointer; font-family: inherit; font-weight: 600;
      transition: all 0.2s; white-space: nowrap;
    }
    .install-opt .copy-btn:hover { background: rgba(108,92,231,0.2); }
    .install-opt .copy-btn.copied { background: rgba(76,175,80,0.15); border-color: #4caf50; color: #4caf50; }
    .cta-row { display: flex; gap: 0.8rem; justify-content: center; margin-bottom: 3rem; }
    .cta-gh {
      display: inline-flex; align-items: center; gap: 0.5rem;
      background: var(--bg-card); border: 1px solid var(--border);
      color: var(--white); padding: 0.65rem 1.4rem; border-radius: 8px;
      text-decoration: none; font-weight: 600; font-size: 0.85rem;
      transition: all 0.2s;
    }
    .cta-gh:hover { border-color: var(--border-hover); background: var(--bg-elevated); transform: translateY(-1px); }
    .cta-docs {
      display: inline-flex; align-items: center; gap: 0.5rem;
      background: transparent; border: 1px solid var(--border);
      color: var(--gray-2); padding: 0.65rem 1.4rem; border-radius: 8px;
      text-decoration: none; font-weight: 500; font-size: 0.85rem;
      transition: all 0.2s;
    }
    .cta-docs:hover { border-color: var(--border-hover); color: var(--white); }
    .section {
      position: relative; z-index: 1;
      padding: 5rem 2rem; max-width: 1000px; margin: 0 auto;
    }
    .section-label {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.72rem; font-weight: 600; color: var(--accent);
      letter-spacing: 0.1em; text-transform: uppercase;
      margin-bottom: 0.5rem; text-align: center;
    }
    .section-title {
      text-align: center; font-size: 2.2rem; font-weight: 800;
      letter-spacing: -0.02em; margin-bottom: 0.5rem;
    }
    .section-subtitle {
      text-align: center; color: var(--gray-2); font-size: 0.95rem;
      margin-bottom: 3rem; max-width: 520px; margin-left: auto; margin-right: auto;
    }
    .features {
      display: grid; grid-template-columns: repeat(3,1fr);
      gap: 1px; background: var(--border); border-radius: 14px; overflow: hidden;
      border: 1px solid var(--border);
    }
    .feature {
      background: var(--bg-card); padding: 2rem 1.6rem;
      transition: background 0.3s;
    }
    .feature:hover { background: var(--bg-elevated); }
    .feature-icon {
      width: 40px; height: 40px; border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      font-size: 1.1rem; margin-bottom: 1rem;
      background: var(--accent-soft); color: var(--accent);
    }
    .feature h3 { font-size: 0.92rem; font-weight: 700; margin-bottom: 0.4rem; }
    .feature p { font-size: 0.82rem; color: var(--gray-2); line-height: 1.6; }
    .steps {
      display: grid; grid-template-columns: repeat(3, 1fr);
      gap: 2rem; max-width: 800px; margin: 0 auto;
    }
    .step { text-align: center; }
    .step-num {
      width: 44px; height: 44px; border-radius: 50%;
      background: var(--accent-soft); color: var(--accent);
      display: inline-flex; align-items: center; justify-content: center;
      font-family: 'JetBrains Mono', monospace;
      font-size: 1rem; font-weight: 700; margin-bottom: 1rem;
    }
    .step h3 { font-size: 0.9rem; font-weight: 700; margin-bottom: 0.4rem; }
    .step p { font-size: 0.8rem; color: var(--gray-2); line-height: 1.55; }
    .arch-card {
      max-width: 680px; margin: 0 auto;
      background: var(--code-bg); border: 1px solid var(--border);
      border-radius: 12px; padding: 1.8rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.78rem; line-height: 1.8; color: var(--gray-1);
    }
    .a-cm { color: var(--gray-3); }
    .a-k { color: var(--accent); }
    .a-v { color: var(--fn-color); }
    .a-t { color: var(--gray-2); }
    .footer {
      position: relative; z-index: 1;
      text-align: center; padding: 3rem 2rem;
      border-top: 1px solid var(--border);
    }
    .footer-links {
      display: flex; gap: 2rem; justify-content: center; margin-bottom: 1rem;
    }
    .footer-links a {
      color: var(--gray-2); text-decoration: none; font-size: 0.82rem;
      font-weight: 500; transition: color 0.2s;
    }
    .footer-links a:hover { color: var(--accent); }
    .footer-credit {
      color: var(--gray-3); font-size: 0.78rem; line-height: 1.6;
    }
    .footer-credit strong { color: var(--gray-2); font-weight: 600; }
    .theme-toggle {
      position: fixed; top: 1.2rem; right: 1.4rem; z-index: 200;
      width: 48px; height: 26px; border-radius: 13px;
      background: var(--bg-card); border: 1px solid var(--border);
      cursor: pointer; padding: 3px;
      transition: border-color 0.3s, background 0.3s;
      display: flex; align-items: center;
    }
    .theme-toggle:hover { border-color: var(--accent); }
    .toggle-knob {
      width: 20px; height: 20px; border-radius: 50%;
      background: var(--accent);
      transition: transform 0.3s cubic-bezier(.34,1.56,.64,1);
      display: flex; align-items: center; justify-content: center;
      font-size: 11px; line-height: 1;
    }
    [data-theme="dark"] .toggle-knob { transform: translateX(0); }
    [data-theme="light"] .toggle-knob { transform: translateX(22px); }
    [data-theme="dark"] .toggle-knob::after { content: '\\263E'; color: #fff; }
    [data-theme="light"] .toggle-knob::after { content: '\\2600'; color: #fff; }
    .terminal, .mhp-inner, .feature, .arch-card, .install-options, .install-opt,
    .cta-gh, .cta-docs, .download-auto, .version-tag, .footer {
      transition: background 0.3s ease, border-color 0.3s ease, color 0.3s ease, box-shadow 0.3s ease;
    }
    .reveal { opacity: 0; transform: translateY(20px); transition: all 0.6s ease; }
    .reveal.visible { opacity: 1; transform: translateY(0); }
    @media (max-width: 768px) {
      .logo { font-size: 3.5rem; }
      .hero-tagline { font-size: 1.1rem; }
      .features { grid-template-columns: 1fr; }
      .steps { grid-template-columns: 1fr; gap: 1.5rem; }
      .cta-row { flex-direction: column; align-items: center; }
      .mascot-hover-panel { left: auto; right: calc(100% + 12px); transform-origin: right center; }
      .mascot-wrapper:hover .mascot-hover-panel { transform: translateY(-50%) scale(1); }
      .mhp-inner::after { left: auto; right: -7px; border-right: none; border-left: 7px solid var(--border); }
      .mhp-inner::before { left: auto; right: -6px; border-right: none; border-left: 6px solid var(--bg-card); }
    }
    @media (max-width: 480px) {
      .logo { font-size: 2.8rem; }
      .mascot-hover-panel { display: none; }
    }
  </style>
</head>
<body>
  <div class="bg-noise"></div>
  <div class="bg-glow"></div>
  <button class="theme-toggle" id="themeBtn" aria-label="Toggle dark/light mode">
    <div class="toggle-knob"></div>
  </button>

  <section class="hero">
    <div class="mascot-wrapper" id="mascot">
      <div class="mascot-hover-panel">
        <div class="mhp-inner">
          <div class="mhp-bar"><div class="mhp-dot r"></div><div class="mhp-dot y"></div><div class="mhp-dot g"></div></div>
          <div class="mhp-file">hauba/engine/copilot_engine.py</div>
          <div class="mhp-line"><span class="c-kw">async def</span> <span class="c-fn">execute</span>(self, task):</div>
          <div class="mhp-line">&nbsp;&nbsp;session = <span class="c-kw">await</span> self.<span class="c-fn">create_session</span>()</div>
          <div class="mhp-line">&nbsp;&nbsp;<span class="c-cm"># BYOK: user's key, not ours</span></div>
          <div class="mhp-line">&nbsp;&nbsp;<span class="c-kw">return await</span> session.<span class="c-fn">send_and_wait</span>(task)<span class="mhp-cursor"></span></div>
          <div class="mhp-status">&#x2713; Powered by Copilot SDK</div>
        </div>
      </div>
      <svg class="mascot-svg" viewBox="0 0 130 158" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="bG" x1="30" y1="10" x2="100" y2="148" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stop-color="#a29bfe"/><stop offset="50%" stop-color="#6C5CE7"/><stop offset="100%" stop-color="#5541d6"/>
          </linearGradient>
          <linearGradient id="blG" x1="45" y1="65" x2="85" y2="120" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stop-color="rgba(255,255,255,0.18)"/><stop offset="100%" stop-color="rgba(255,255,255,0.02)"/>
          </linearGradient>
          <radialGradient id="aura" cx="65" cy="82" r="58" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stop-color="rgba(108,92,231,0.18)"/><stop offset="100%" stop-color="transparent"/>
          </radialGradient>
          <filter id="gF"><feGaussianBlur stdDeviation="2.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
        </defs>
        <ellipse cx="65" cy="86" rx="56" ry="62" fill="url(#aura)" opacity="0.5"/>
        <g class="mascot-body-group">
          <g class="arm-left"><path d="M36 72 Q18 62 15 76 Q12 90 26 86 Q32 84 38 78" fill="url(#bG)" opacity="0.9"/><ellipse cx="15" cy="78" rx="6" ry="5" fill="url(#bG)" opacity="0.85"/></g>
          <g class="arm-right"><path d="M94 72 Q112 62 115 76 Q118 90 104 86 Q98 84 92 78" fill="url(#bG)" opacity="0.9"/><ellipse cx="115" cy="78" rx="6" ry="5" fill="url(#bG)" opacity="0.85"/></g>
          <g class="belly"><ellipse cx="65" cy="87" rx="38" ry="48" fill="url(#bG)"/><ellipse cx="65" cy="92" rx="28" ry="34" fill="url(#blG)"/><ellipse cx="65" cy="104" rx="3" ry="3.5" fill="rgba(0,0,0,0.18)"/></g>
          <ellipse cx="65" cy="41" rx="25" ry="24" fill="url(#bG)"/>
          <ellipse cx="60" cy="34" rx="12" ry="9" fill="rgba(255,255,255,0.07)"/>
          <g><path d="M65 18 Q62 6 68 2" stroke="url(#bG)" stroke-width="2.2" fill="none" stroke-linecap="round"><animateTransform attributeName="transform" type="rotate" values="0 65 18;7 65 18;-7 65 18;0 65 18" dur="2.1s" repeatCount="indefinite"/></path><circle cx="68" cy="2" r="3.5" fill="#a29bfe" filter="url(#gF)"><animate attributeName="r" values="3.5;5;3.5" dur="1.6s" repeatCount="indefinite"/><animate attributeName="opacity" values="0.75;1;0.75" dur="1.6s" repeatCount="indefinite"/></circle></g>
          <g class="eye-blink"><ellipse cx="55" cy="40" rx="8" ry="9" fill="white"/><g class="eye-pupil"><circle cx="56.5" cy="41" r="4" fill="var(--mascot-eye)"/><circle cx="57.5" cy="39" r="1.8" fill="white" opacity="0.9"/></g></g>
          <g class="eye-blink-r"><ellipse cx="75" cy="40" rx="8" ry="9" fill="white"/><g class="eye-pupil"><circle cx="76.5" cy="41" r="4" fill="var(--mascot-eye)"/><circle cx="77.5" cy="39" r="1.8" fill="white" opacity="0.9"/></g></g>
          <ellipse cx="65" cy="53" rx="5.5" ry="2.8" fill="var(--mascot-mouth)"><animate attributeName="ry" values="2.8;8;3.5;9;2.8;8.5;2.8" dur="3.2s" repeatCount="indefinite"/><animate attributeName="rx" values="5.5;7;5;7.5;5.5;7;5.5" dur="3.2s" repeatCount="indefinite"/></ellipse>
          <ellipse cx="65" cy="55" rx="3.5" ry="1.5" fill="var(--mascot-mouth-inner)" opacity="0.55"><animate attributeName="ry" values="1.5;5.5;2;6;1.5;5.5;1.5" dur="3.2s" repeatCount="indefinite"/></ellipse>
          <ellipse cx="52" cy="132" rx="11" ry="5.5" fill="url(#bG)" opacity="0.88"/>
          <ellipse cx="78" cy="132" rx="11" ry="5.5" fill="url(#bG)" opacity="0.88"/>
        </g>
      </svg>
    </div>

    <h1 class="logo">H<span>AU</span>BA</h1>
    <div class="version-tag" id="versionTag" style="visibility:hidden"></div>

    <p class="hero-tagline">
      <strong>Stop hiring engineers. Start shipping products.</strong><br>
      An AI engineering company in your terminal. Not a chatbot.
    </p>
    <p class="hero-sub">
      One command gives you an AI team that plans architecture, writes production code,
      runs tests, fixes bugs, and delivers &mdash; while you sleep. Powered by Copilot SDK.
      Your API key. Your code. Your infrastructure. Zero vendor lock-in.
    </p>

    <div class="terminal reveal">
      <div class="terminal-bar">
        <div class="terminal-dot r"></div><div class="terminal-dot y"></div><div class="terminal-dot g"></div>
        <div class="terminal-title">Terminal</div>
      </div>
      <div class="terminal-body">
        <span class="t-prompt">$</span> <span class="t-cmd">pip install hauba</span><br>
        <span class="t-prompt">$</span> <span class="t-cmd">hauba init</span><br>
        <span class="t-output">Initialized hauba workspace at ./hauba.yaml</span><br>
        <span class="t-prompt">$</span> <span class="t-cmd">hauba run <span style="color:var(--gray-1)">"build a SaaS dashboard with auth"</span></span><br>
        <span class="t-output">Engine &rarr; Copilot SDK connected</span><br>
        <span class="t-output">Agent &rarr; Planning architecture...</span><br>
        <span class="t-output">Agent &rarr; Implementing auth + Stripe billing</span><br>
        <span class="t-success">&#x2713; All tasks verified. 0 hallucinations.</span><span class="t-cursor"></span>
      </div>
    </div>

    <div class="download-section reveal">
      <button class="download-auto" id="downloadBtn" onclick="copyInstallCmd()">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        <span id="downloadText">Install for your platform</span>
      </button>
      <div class="download-other">
        <a href="#" id="togglePlatforms" onclick="toggleInstallOpts(event)">All platforms</a>
        &middot; <a href="https://pypi.org/project/hauba/">PyPI</a>
        &middot; <a href="https://github.com/NikeGunn/haubaa/releases">Releases</a>
        &middot; <a href="/docs">API Docs</a>
      </div>
      <div class="install-options" id="installOpts">
        <div class="install-opt">
          <span class="install-opt-label">pip</span>
          <code class="install-opt-cmd">pip install hauba</code>
          <button class="copy-btn" onclick="copyCmd(this,'pip install hauba')">Copy</button>
        </div>
        <div class="install-opt">
          <span class="install-opt-label">macOS / Linux</span>
          <code class="install-opt-cmd">curl -fsSL https://hauba.tech/install.sh | sh</code>
          <button class="copy-btn" onclick="copyCmd(this,'curl -fsSL https://hauba.tech/install.sh | sh')">Copy</button>
        </div>
        <div class="install-opt">
          <span class="install-opt-label">Windows</span>
          <code class="install-opt-cmd">irm hauba.tech/install.ps1 | iex</code>
          <button class="copy-btn" onclick="copyCmd(this,'irm hauba.tech/install.ps1 | iex')">Copy</button>
        </div>
      </div>
    </div>

    <div class="cta-row reveal">
      <a href="https://github.com/NikeGunn/haubaa" class="cta-gh">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
        Star on GitHub
      </a>
      <a href="https://github.com/NikeGunn/haubaa#readme" class="cta-docs">Documentation</a>
    </div>
  </section>

  <section class="section" id="features">
    <div class="section-label reveal">Capabilities</div>
    <h2 class="section-title reveal">Why 10,000+ developers chose Hauba.</h2>
    <p class="section-subtitle reveal">The same AI backbone used by GitHub. Now open-source and in your hands.</p>
    <div class="features reveal">
      <div class="feature">
        <div class="feature-icon">&#x2B21;</div>
        <h3>Enterprise-Grade Engine</h3>
        <p>Powered by GitHub Copilot SDK &mdash; the same production-tested runtime behind Copilot. Not a wrapper. The real thing.</p>
      </div>
      <div class="feature">
        <div class="feature-icon">&#x2B22;</div>
        <h3>BYOK &mdash; $0 Platform Cost</h3>
        <p>Bring Claude, GPT-4, or run fully offline with Ollama. Your key, your models. Hauba charges nothing. Ever.</p>
      </div>
      <div class="feature">
        <div class="feature-icon">&#x25C6;</div>
        <h3>Air-Gap Ready</h3>
        <p>Runs 100% offline with Ollama. No telemetry. No cloud dependency. Deploy in classified environments.</p>
      </div>
      <div class="feature">
        <div class="feature-icon">&#x25A0;</div>
        <h3>17 Built-in Skills</h3>
        <p>Full-stack, ML, video editing, data pipelines, DevOps, security &mdash; domain expertise as composable .md files.</p>
      </div>
      <div class="feature">
        <div class="feature-icon">&#x25B2;</div>
        <h3>Ship via WhatsApp</h3>
        <p>Message your AI team on WhatsApp. Get results delivered to your phone. Works with Telegram and Discord too.</p>
      </div>
      <div class="feature">
        <div class="feature-icon">&#x25CB;</div>
        <h3>Interactive CLI</h3>
        <p>Claude Code-style terminal with arrow-key menus, live progress, file tracking. Zero typing for setup.</p>
      </div>
    </div>
  </section>

  <section class="section" id="how">
    <div class="section-label reveal">Workflow</div>
    <h2 class="section-title reveal">From idea to production in 3 steps.</h2>
    <p class="section-subtitle reveal">Your competitors are hiring for 6 months. You ship today.</p>
    <div class="steps reveal">
      <div class="step">
        <div class="step-num">1</div>
        <h3>Install</h3>
        <p>One command. No Docker, Redis, or Kubernetes. Just pip install and go.</p>
      </div>
      <div class="step">
        <div class="step-num">2</div>
        <h3>Describe</h3>
        <p>"Build me a SaaS dashboard with auth and Stripe billing." That's it. Plain English.</p>
      </div>
      <div class="step">
        <div class="step-num">3</div>
        <h3>Ship</h3>
        <p>Hauba plans the architecture, writes code, runs tests, fixes bugs, and delivers. You review and deploy.</p>
      </div>
    </div>
  </section>

  <section class="section" id="architecture">
    <div class="section-label reveal">Under the hood</div>
    <h2 class="section-title reveal">Architecture</h2>
    <p class="section-subtitle reveal">Copilot SDK engine. BYOK. Event-driven. Infinite sessions.</p>
    <div class="arch-card reveal">
      <span class="a-cm"># Hauba AI Engineer Architecture</span><br>
      <span class="a-k">User</span> <span class="a-t">(brings own API key)</span><br>
      &nbsp;&nbsp;<span class="a-v">&#x2514;&#x2500;&#x2500;</span> <span class="a-k">Hauba CLI / API</span><br>
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="a-v">&#x2514;&#x2500;&#x2500;</span> <span class="a-k">Copilot SDK</span> <span class="a-t">(engine)</span><br>
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="a-v">&#x2514;&#x2500;&#x2500;</span> <span class="a-k">Copilot CLI Server</span> <span class="a-t">(agent runtime)</span><br>
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="a-v">&#x251C;&#x2500;&#x2500;</span> bash, files, git <span class="a-cm">&mdash; built-in tools</span><br>
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="a-v">&#x251C;&#x2500;&#x2500;</span> web, browser <span class="a-cm">&mdash; optional tools</span><br>
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="a-v">&#x2514;&#x2500;&#x2500;</span> infinite sessions <span class="a-cm">&mdash; auto-compaction</span><br><br>
      <span class="a-cm"># BYOK: Claude, GPT-4, Ollama &mdash; user's key, zero cost to owner</span><br>
      <span class="a-cm"># Skills: .md files &mdash; domain expertise injection</span><br>
      <span class="a-cm"># Strategies: .yaml playbooks &mdash; structured execution</span>
    </div>
  </section>

  <footer class="footer">
    <div class="footer-links">
      <a href="https://github.com/NikeGunn/haubaa">GitHub</a>
      <a href="https://pypi.org/project/hauba/">PyPI</a>
      <a href="https://github.com/NikeGunn/haubaa#readme">Docs</a>
      <a href="https://github.com/NikeGunn/haubaa/releases">Releases</a>
    </div>
    <p class="footer-credit">
      Built by <strong>Nikhil Bhagat</strong> and community &mdash; MIT License<br>
      <span style="color:var(--accent)">Powered by GitHub Copilot SDK</span>
    </p>
  </footer>

  <script>
    (function() {
      var html = document.documentElement;
      var saved = localStorage.getItem('hauba-theme');
      if (saved === 'light' || saved === 'dark') html.dataset.theme = saved;
      document.getElementById('themeBtn').addEventListener('click', function() {
        var next = html.dataset.theme === 'dark' ? 'light' : 'dark';
        html.dataset.theme = next;
        localStorage.setItem('hauba-theme', next);
      });
    })();

    function detectOS() {
      const ua = navigator.userAgent || navigator.platform || '';
      if (/Win/i.test(ua)) return 'windows';
      if (/Mac/i.test(ua)) return 'macos';
      if (/Linux/i.test(ua)) return 'linux';
      return 'pip';
    }
    const osCommands = {
      windows: { label: 'Install for Windows', cmd: 'irm hauba.tech/install.ps1 | iex' },
      macos:   { label: 'Install for macOS',   cmd: 'curl -fsSL https://hauba.tech/install.sh | sh' },
      linux:   { label: 'Install for Linux',   cmd: 'curl -fsSL https://hauba.tech/install.sh | sh' },
      pip:     { label: 'Install with pip',     cmd: 'pip install hauba' },
    };
    const userOS = detectOS();
    const osInfo = osCommands[userOS] || osCommands.pip;
    document.getElementById('downloadText').textContent = osInfo.label;

    function copyInstallCmd() {
      const btn = document.getElementById('downloadBtn');
      const text = document.getElementById('downloadText');
      navigator.clipboard.writeText(osInfo.cmd).then(() => {
        const orig = text.textContent;
        text.textContent = 'Copied: ' + osInfo.cmd;
        btn.style.background = 'var(--success)';
        setTimeout(function() { text.textContent = orig; btn.style.background = ''; }, 2500);
      });
    }

    function toggleInstallOpts(e) {
      e.preventDefault();
      document.getElementById('installOpts').classList.toggle('open');
    }

    function copyCmd(btn, text) {
      navigator.clipboard.writeText(text).then(() => {
        btn.textContent = 'Copied!'; btn.classList.add('copied');
        setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
      });
    }

    const obs = new IntersectionObserver(entries => {
      entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('visible'); });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
    document.querySelectorAll('.reveal').forEach(el => obs.observe(el));

    document.getElementById('mascot').addEventListener('click', function() {
      this.style.transform = 'scale(1.1) rotate(5deg)';
      setTimeout(() => this.style.transform = '', 350);
    });

    (function() {
      fetch('/api/version')
        .then(function(r) { return r.ok ? r.json() : null; })
        .then(function(info) {
          if (!info || !info.version) return;
          var el = document.getElementById('versionTag');
          if (el) { el.textContent = info.version + ' \\u2014 ' + info.label; el.style.visibility = ''; }
        })
        .catch(function() {});
    })();
  </script>
</body>
</html>
"""


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))

    _ensure_copilot_sdk()

    app = create_server_app()

    try:
        import uvicorn
    except ImportError:
        print("[hauba] Installing uvicorn...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "uvicorn[standard]"],
            check=True,
            capture_output=True,
        )
        import uvicorn

    print(f"[hauba] Hauba AI Engineer starting on port {PORT}")
    print(f"[hauba] Landing: http://0.0.0.0:{PORT}/")
    print(f"[hauba] Health:  http://0.0.0.0:{PORT}/health")

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
