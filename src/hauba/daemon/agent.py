"""Hauba Daemon Agent — polls server for queued tasks and executes locally.

This runs on the user's machine via `hauba agent`. It:
1. Authenticates with hauba.tech using the owner_id
2. Polls /api/v1/queue/{owner_id} for pending tasks
3. Claims and executes tasks locally via CopilotEngine
4. Reports progress and results back to the server
5. Server notifies the originating channel (WhatsApp, etc.)

Architecture:
    User's Machine                          Server (hauba.tech)
    ─────────────                          ─────────────────
    hauba agent                            /api/v1/queue/*
        │                                       │
        ├─ poll ─────────────────────────────── GET  /{owner_id}
        │                                       │
        ├─ claim ────────────────────────────── POST /{task_id}/claim
        │                                       │
        ├─ CopilotEngine.execute()              │
        │   (builds locally on user's machine)  │
        │                                       │
        ├─ progress ─────────────────────────── POST /{task_id}/progress
        │                                       │
        └─ complete ─────────────────────────── POST /{task_id}/complete
                                                │
                                           notify WhatsApp/Telegram/Discord
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

# Default polling interval (seconds)
DEFAULT_POLL_INTERVAL = 10.0

# Default server URL
DEFAULT_SERVER_URL = "https://hauba.tech"

# Progress report interval during execution
PROGRESS_REPORT_INTERVAL = 15.0

# Cost estimation per 1K tokens (approximate USD)
# Used for cost alerts — not billing, just owner awareness
COST_PER_1K_TOKENS = {
    "anthropic": 0.015,  # Claude Sonnet average
    "openai": 0.010,  # GPT-4o average
    "ollama": 0.0,  # Free (local)
    "deepseek": 0.002,  # DeepSeek
}

# Default cost alert threshold (USD per task)
DEFAULT_COST_ALERT_THRESHOLD = 5.0


class HaubaDaemon:
    """Background daemon that polls the server for queued tasks.

    Runs on the user's machine. Executes tasks locally using CopilotEngine
    with the user's own API key (from ~/.hauba/settings.json).

    Usage:
        daemon = HaubaDaemon(
            owner_id="whatsapp:+9779812345678",
            server_url="https://hauba.tech",
        )
        await daemon.start()
    """

    def __init__(
        self,
        owner_id: str,
        server_url: str = DEFAULT_SERVER_URL,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        workspace: str = "",
        cost_alert_threshold: float = DEFAULT_COST_ALERT_THRESHOLD,
    ) -> None:
        self._owner_id = owner_id
        self._server_url = server_url.rstrip("/")
        self._poll_interval = poll_interval
        self._workspace = workspace
        self._cost_alert_threshold = cost_alert_threshold
        self._running = False
        self._active_tasks: dict[str, asyncio.Task[None]] = {}
        self._http: httpx.AsyncClient | None = None

        # Cost tracking — estimates based on tool calls
        self._session_cost: float = 0.0
        self._task_costs: dict[str, float] = {}
        self._cost_alerts_sent: set[str] = set()

    @property
    def owner_id(self) -> str:
        """The owner identity for task polling."""
        return self._owner_id

    @property
    def is_running(self) -> bool:
        """Whether the daemon is currently running."""
        return self._running

    async def start(self) -> None:
        """Start the daemon polling loop.

        This blocks until stop() is called or KeyboardInterrupt.
        """
        self._running = True
        self._http = httpx.AsyncClient(
            base_url=self._server_url,
            timeout=30.0,
            headers={"User-Agent": "hauba-agent/0.4.0"},
        )

        logger.info(
            "daemon.started",
            owner_id=self._owner_id,
            server=self._server_url,
            poll_interval=self._poll_interval,
        )

        try:
            while self._running:
                try:
                    await self._poll_and_execute()
                except Exception as exc:
                    logger.error("daemon.poll_error", error=str(exc))

                await asyncio.sleep(self._poll_interval)
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop the daemon and clean up."""
        self._running = False

        # Cancel active tasks
        for task_id, task in self._active_tasks.items():
            task.cancel()
            logger.info("daemon.task_cancelled", task_id=task_id)

        self._active_tasks.clear()

        if self._http:
            await self._http.aclose()
            self._http = None

        logger.info("daemon.stopped")

    async def _poll_and_execute(self) -> None:
        """Poll the server for queued tasks and execute them."""
        if not self._http:
            return

        try:
            resp = await self._http.get(
                f"/api/v1/queue/{self._owner_id}",
            )

            if resp.status_code == 404:
                # No tasks — normal
                return

            if resp.status_code != 200:
                logger.warning(
                    "daemon.poll_failed",
                    status=resp.status_code,
                    body=resp.text[:200],
                )
                return

            tasks = resp.json()
            if not tasks:
                return

            for task_data in tasks:
                task_id = task_data["task_id"]

                # Skip if already executing
                if task_id in self._active_tasks:
                    continue

                # Claim the task
                claimed = await self._claim_task(task_id)
                if not claimed:
                    continue

                # Execute in background
                self._active_tasks[task_id] = asyncio.create_task(self._execute_task(task_data))

        except httpx.ConnectError:
            logger.debug("daemon.server_unreachable", server=self._server_url)
        except Exception as exc:
            logger.error("daemon.poll_error", error=str(exc))

    async def _claim_task(self, task_id: str) -> bool:
        """Claim a task on the server."""
        if not self._http:
            return False

        try:
            resp = await self._http.post(f"/api/v1/queue/{task_id}/claim")
            if resp.status_code == 200:
                logger.info("daemon.task_claimed", task_id=task_id)
                return True
            logger.debug(
                "daemon.claim_failed",
                task_id=task_id,
                status=resp.status_code,
            )
            return False
        except Exception as exc:
            logger.error("daemon.claim_error", task_id=task_id, error=str(exc))
            return False

    async def _execute_task(self, task_data: dict[str, Any]) -> None:
        """Execute a single task locally via CopilotEngine."""
        from hauba.core.config import ConfigManager
        from hauba.engine.copilot_engine import CopilotEngine
        from hauba.engine.types import EngineConfig, ProviderType

        task_id = task_data["task_id"]
        instruction = task_data["instruction"]

        logger.info(
            "daemon.task_started",
            task_id=task_id,
            instruction=instruction[:100],
        )

        # Load user's local config
        config = ConfigManager()

        provider_map = {
            "anthropic": ProviderType.ANTHROPIC,
            "openai": ProviderType.OPENAI,
            "ollama": ProviderType.OLLAMA,
        }
        provider = provider_map.get(config.settings.llm.provider, ProviderType.ANTHROPIC)

        base_url = None
        if config.settings.llm.provider == "ollama":
            base_url = config.settings.llm.base_url or "http://localhost:11434/v1"
        elif config.settings.llm.provider == "deepseek":
            base_url = "https://api.deepseek.com/v1"

        # Resolve workspace
        workspace = self._workspace
        if not workspace:
            from pathlib import Path

            workspace = str(Path.cwd() / "hauba-output")
            Path(workspace).mkdir(parents=True, exist_ok=True)

        engine_config = EngineConfig(
            provider=provider,
            api_key=config.settings.llm.api_key,
            model=config.settings.llm.model,
            base_url=base_url,
            working_directory=workspace,
        )

        # Build skill context
        try:
            from hauba.cli import _build_skill_context

            skill_context = _build_skill_context(instruction)
        except Exception:
            skill_context = ""

        engine = CopilotEngine(engine_config, skill_context=skill_context)

        # Track cost via engine events (tool calls = LLM usage)
        self._task_costs[task_id] = 0.0
        provider_name = config.settings.llm.provider
        cost_per_1k = COST_PER_1K_TOKENS.get(provider_name, 0.01)

        def _track_cost(event: Any) -> None:
            """Estimate cost from engine events (each tool call ~ 1-2K tokens)."""
            etype = getattr(event, "type", "")
            if etype in (
                "engine.executing",
                "tool.execution_start",
                "assistant.message_delta",
            ):
                # Rough estimate: each event ~ 0.5K tokens
                est_cost = cost_per_1k * 0.5
                self._task_costs[task_id] = self._task_costs.get(task_id, 0) + est_cost
                self._session_cost += est_cost

        unsub = engine.on_event(_track_cost)

        # Start progress reporter
        stop_progress = asyncio.Event()
        progress_task = asyncio.create_task(self._report_progress_loop(task_id, stop_progress))

        try:
            # No timeout — daemon runs autonomously 24/7
            # The engine itself has infinite sessions with auto-compaction
            result = await engine.execute(instruction, timeout=3600.0)

            task_cost = self._task_costs.get(task_id, 0)

            # Check cost threshold and alert owner
            if task_cost > self._cost_alert_threshold:
                await self._send_cost_alert(task_id, instruction, task_cost)

            # Report completion with cost info
            output = result.output or "Task completed."
            if task_cost > 0.01:
                output += f"\n\n_Estimated cost: ${task_cost:.2f}_"

            await self._report_completion(
                task_id=task_id,
                output=output,
                success=result.success,
                error=result.error or "",
            )

        except Exception as exc:
            logger.error("daemon.task_error", task_id=task_id, error=str(exc))
            await self._report_completion(
                task_id=task_id,
                output="",
                success=False,
                error=str(exc),
            )
        finally:
            unsub()
            stop_progress.set()
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass
            await engine.stop()
            self._active_tasks.pop(task_id, None)

    async def _report_progress_loop(self, task_id: str, stop: asyncio.Event) -> None:
        """Periodically report progress to the server."""
        elapsed = 0.0
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=PROGRESS_REPORT_INTERVAL)
                return
            except TimeoutError:
                elapsed += PROGRESS_REPORT_INTERVAL
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)
                cost = self._task_costs.get(task_id, 0)
                cost_str = f" | ~${cost:.2f}" if cost > 0.01 else ""
                progress = f"Working... ({minutes}m {seconds}s{cost_str})"
                await self._report_progress(task_id, progress)

    async def _report_progress(self, task_id: str, progress: str) -> None:
        """Report progress for a task to the server."""
        if not self._http:
            return
        try:
            await self._http.post(
                f"/api/v1/queue/{task_id}/progress",
                json={"progress": progress},
            )
        except Exception:
            pass  # Non-critical

    async def _report_completion(
        self,
        task_id: str,
        output: str,
        success: bool,
        error: str,
    ) -> None:
        """Report task completion to the server."""
        if not self._http:
            return
        try:
            resp = await self._http.post(
                f"/api/v1/queue/{task_id}/complete",
                json={
                    "output": output[:4000],  # Cap output size
                    "success": success,
                    "error": error[:500],
                },
            )
            if resp.status_code == 200:
                logger.info(
                    "daemon.task_reported",
                    task_id=task_id,
                    success=success,
                )
            else:
                logger.warning(
                    "daemon.report_failed",
                    task_id=task_id,
                    status=resp.status_code,
                )
        except Exception as exc:
            logger.error(
                "daemon.report_error",
                task_id=task_id,
                error=str(exc),
            )

    async def _send_cost_alert(self, task_id: str, instruction: str, cost: float) -> None:
        """Notify the owner when a task exceeds the cost threshold.

        Sends an alert via the server so it reaches the originating channel.
        Only alerts once per task to avoid spam.
        """
        if task_id in self._cost_alerts_sent:
            return
        self._cost_alerts_sent.add(task_id)

        logger.warning(
            "daemon.cost_alert",
            task_id=task_id,
            estimated_cost=f"${cost:.2f}",
            threshold=f"${self._cost_alert_threshold:.2f}",
            session_total=f"${self._session_cost:.2f}",
        )

        if not self._http:
            return

        try:
            await self._http.post(
                f"/api/v1/queue/{task_id}/progress",
                json={
                    "progress": (
                        f"⚠️ Cost alert: ~${cost:.2f} estimated for this task "
                        f"(threshold: ${self._cost_alert_threshold:.2f}). "
                        f"Session total: ~${self._session_cost:.2f}. "
                        f"Task: {instruction[:80]}"
                    ),
                },
            )
        except Exception:
            pass

    @property
    def session_cost(self) -> float:
        """Total estimated cost for this daemon session."""
        return self._session_cost

    @property
    def task_costs(self) -> dict[str, float]:
        """Estimated cost per task."""
        return dict(self._task_costs)
