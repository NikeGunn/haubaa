"""AgentEngine — Hauba V3 execution brain.

Powered by the OpenAI Agents SDK. Replaces the V2 CopilotEngine.

Features:
- Multi-agent orchestration (Director → Coder/Browser/Reviewer)
- MCP server integration (Playwright MCP for browser)
- Any LLM provider via LiteLLM
- Streaming events for real-time UI
- Session persistence
- Function tools (web search, web fetch, email)

Architecture:
    User Request → AgentEngine → OpenAI Agents SDK
                                      ↓
                              DirectorAgent (plans, delegates)
                                 ↓      ↓       ↓
                           Coder   Browser   Reviewer
                             ↓        ↓
                       Shell/Patch  Playwright MCP
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any

import structlog

from hauba.engine.types import EngineConfig, EngineEvent, EngineResult

logger = structlog.get_logger()


@dataclass
class StreamEvent:
    """A single streaming event from the agent execution."""

    type: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()


class AgentEngine:
    """The V3 execution brain for Hauba AI Workstation.

    Wraps the OpenAI Agents SDK to provide multi-agent orchestration
    with MCP server integration for browser automation and file access.

    Example:
        >>> config = EngineConfig(
        ...     provider=ProviderType.ANTHROPIC,
        ...     api_key="sk-ant-...",
        ...     model="claude-sonnet-4-5-20250514",
        ... )
        >>> engine = AgentEngine(config)
        >>> result = await engine.execute("Build a REST API with auth")
        >>> print(result.output)
    """

    def __init__(self, config: EngineConfig, skill_context: str = "") -> None:
        self._config = config
        self._skill_context = skill_context
        self._events: list[EngineEvent] = []
        self._event_handlers: list[Callable[[EngineEvent], None]] = []
        self._exit_stack: AsyncExitStack | None = None
        self._mcp_servers: list[Any] = []
        self._director: Any = None

    @property
    def is_available(self) -> bool:
        """Check if the OpenAI Agents SDK is available."""
        try:
            import agents  # noqa: F401

            return True
        except ImportError:
            return False

    def on_event(self, handler: Callable[[EngineEvent], None]) -> Callable[[], None]:
        """Subscribe to engine events for real-time streaming."""
        self._event_handlers.append(handler)

        def unsubscribe() -> None:
            if handler in self._event_handlers:
                self._event_handlers.remove(handler)

        return unsubscribe

    def _emit(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Emit an event to all handlers."""
        event = EngineEvent(type=event_type, data=data, timestamp=time.time())
        self._events.append(event)
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.warning("engine.event_handler_error", error=str(e))

    async def start(self) -> None:
        """Initialize MCP servers and agent team."""
        self._configure_env()

        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        # Start MCP servers
        self._mcp_servers = await self._start_mcp_servers()

        # Build model identifier
        model = self._resolve_model()

        # Create agent team
        from hauba.engine.agents import create_agent_team

        self._director = create_agent_team(
            model=model,
            mcp_servers=self._mcp_servers,
            skill_context=self._skill_context,
            working_directory=self._config.working_directory or ".",
        )

        self._emit("engine.started", {"model": model, "mcp_servers": len(self._mcp_servers)})
        logger.info("engine.started", model=model, mcp_count=len(self._mcp_servers))

    async def stop(self) -> None:
        """Shut down MCP servers and clean up."""
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
            except Exception:
                pass
            self._exit_stack = None
        self._mcp_servers = []
        self._director = None
        self._emit("engine.stopped")
        logger.info("engine.stopped")

    async def execute(
        self,
        instruction: str,
        *,
        timeout: float = 600.0,
    ) -> EngineResult:
        """Execute a task using the multi-agent team.

        Args:
            instruction: What to build/do (plain English).
            timeout: Maximum execution time in seconds (default: 10 minutes).

        Returns:
            EngineResult with success/failure, output, and events.
        """
        if not self._director:
            await self.start()

        self._events.clear()
        self._emit("engine.task_started", {"instruction": instruction[:200]})

        try:
            from agents import Runner

            result = await asyncio.wait_for(
                Runner.run(self._director, instruction, max_turns=50),
                timeout=timeout,
            )

            output = str(result.final_output) if result.final_output else ""

            self._emit("engine.task_completed", {"output_length": len(output)})

            return EngineResult.ok(output=output)

        except TimeoutError:
            self._emit("engine.timeout")
            return EngineResult.fail(
                f"Task timed out after {timeout}s. The agent may still be working."
            )
        except Exception as e:
            logger.error("engine.execute_error", error=str(e))
            self._emit("engine.error", {"error": str(e)})
            return EngineResult.fail(str(e))

    async def execute_streamed(
        self,
        instruction: str,
        *,
        timeout: float = 600.0,
    ) -> AsyncIterator[StreamEvent]:
        """Execute a task with streaming events.

        Yields StreamEvent objects as the agent works. The final event
        contains the complete result.

        Args:
            instruction: What to build/do.
            timeout: Maximum execution time.

        Yields:
            StreamEvent objects with real-time progress.
        """
        if not self._director:
            await self.start()

        self._events.clear()
        yield StreamEvent(type="task_started", data={"instruction": instruction[:200]})

        try:
            from agents import Runner

            result = Runner.run_streamed(self._director, instruction, max_turns=50)

            async for event in result.stream_events():
                event_type = getattr(event, "type", str(type(event).__name__))

                # Map SDK events to our stream events
                if event_type == "raw_response_event":
                    # Skip raw API events — too noisy
                    continue

                yield StreamEvent(
                    type=str(event_type),
                    data={"event": str(event)[:500]},
                )

            # Final output
            final_output = str(result.final_output) if result.final_output else ""
            yield StreamEvent(
                type="task_completed",
                data={"output": final_output},
            )

        except TimeoutError:
            yield StreamEvent(type="timeout", data={"timeout": timeout})
        except Exception as e:
            logger.error("engine.streamed_error", error=str(e))
            yield StreamEvent(type="error", data={"error": str(e)})

    def _configure_env(self) -> None:
        """Set environment variables for the agents SDK and LiteLLM."""
        # Set API key for the configured provider
        if self._config.api_key:
            provider = (
                self._config.provider.value
                if hasattr(self._config.provider, "value")
                else str(self._config.provider)
            )

            if provider == "openai":
                os.environ.setdefault("OPENAI_API_KEY", self._config.api_key)
            elif provider == "anthropic":
                os.environ.setdefault("ANTHROPIC_API_KEY", self._config.api_key)
            elif provider == "deepseek":
                os.environ.setdefault("DEEPSEEK_API_KEY", self._config.api_key)
            # LiteLLM reads these env vars automatically

        # If using non-OpenAI provider without an OpenAI key, disable tracing
        if not os.environ.get("OPENAI_API_KEY"):
            try:
                from agents import set_tracing_disabled

                set_tracing_disabled(True)
            except ImportError:
                pass

    def _resolve_model(self) -> str:
        """Resolve the model identifier, adding litellm/ prefix for non-OpenAI providers."""
        model = self._config.model or "gpt-4o"
        provider = (
            self._config.provider.value
            if hasattr(self._config.provider, "value")
            else str(self._config.provider)
        )

        # OpenAI models don't need a prefix
        if (
            provider == "openai"
            or model.startswith("gpt-")
            or model.startswith("o1-")
            or model.startswith("o3-")
        ):
            return model

        # Non-OpenAI models need litellm/ prefix
        if model.startswith("litellm/"):
            return model

        provider_prefixes = {
            "anthropic": "litellm/anthropic",
            "ollama": "litellm/ollama_chat",
            "deepseek": "litellm/deepseek",
        }
        prefix = provider_prefixes.get(provider, f"litellm/{provider}")
        return f"{prefix}/{model}"

    async def _start_mcp_servers(self) -> list[Any]:
        """Start MCP servers and register them in the exit stack."""
        servers: list[Any] = []

        from hauba.engine.mcp_servers import create_playwright_mcp

        playwright = create_playwright_mcp(headless=True)
        if playwright and self._exit_stack:
            try:
                await self._exit_stack.enter_async_context(playwright)
                servers.append(playwright)
                logger.info("mcp.playwright_started")
            except Exception as e:
                logger.warning("mcp.playwright_failed", error=str(e))

        return servers

    async def __aenter__(self) -> AgentEngine:
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()
