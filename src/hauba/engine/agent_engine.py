"""AgentEngine — Hauba V4 execution brain.

Custom agent loop inspired by OpenClaw/Pi architecture.
No SDK delegation — direct LLM API calls with full tool control.

Architecture:
    1. User sends message
    2. LLM receives message + system prompt + tool definitions
    3. LLM responds with tool_use calls (standard API feature)
    4. Hauba executes tools locally, feeds results back
    5. LLM reasons about results, calls more tools or responds
    6. Loop continues until task is done

Key innovations over V3:
- Custom turn-based loop (not delegated to SDK)
- Full visibility into every turn
- Auto-compaction when approaching context limits
- Token-level streaming with tool interleaving
- Progressive tool disclosure
- Single-agent with all tools (no handoff overhead)
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

import structlog

from hauba.engine.context import ContextManager
from hauba.engine.llm import LLMClient, LLMResponse
from hauba.engine.prompts import build_system_prompt
from hauba.engine.tool_registry import ToolRegistry
from hauba.engine.types import EngineConfig, EngineEvent, EngineResult

logger = structlog.get_logger()

# Maximum turns before forcing stop (safety valve)
MAX_TURNS = 200
# Default timeout per task (seconds)
DEFAULT_TIMEOUT = 600.0


@dataclass
class StreamEvent:
    """A single streaming event from the agent execution."""

    type: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class TurnResult:
    """Result of a single agent turn."""

    response_text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


class AgentEngine:
    """The V4 execution brain for Hauba AI.

    Custom agent loop — direct LLM calls, full tool control,
    auto-compaction, streaming. Inspired by OpenClaw/Pi.

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

        # Core components
        self._llm: LLMClient | None = None
        self._tools: ToolRegistry | None = None
        self._context: ContextManager | None = None
        self._started = False

        # Stats
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_turns = 0

    @property
    def is_available(self) -> bool:
        """Check if litellm is available for LLM calls."""
        try:
            import litellm  # noqa: F401

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
        """Initialize LLM client, tools, and context manager."""
        if self._started:
            return

        # Build tool registry
        self._tools = ToolRegistry(
            working_directory=self._config.working_directory or ".",
        )

        # Build LLM client
        self._llm = LLMClient(
            provider=self._config.provider,
            api_key=self._config.api_key,
            model=self._config.model,
            base_url=self._config.base_url,
        )

        # Build context manager
        system_prompt = build_system_prompt(
            skill_context=self._skill_context,
            tool_names=[t.name for t in self._tools.list_tools()],
        )
        self._context = ContextManager(
            system_prompt=system_prompt,
            max_context_tokens=120_000,
            compaction_threshold=0.75,
        )

        self._started = True
        self._emit(
            "engine.started",
            {
                "model": self._config.model,
                "tools": len(self._tools.list_tools()),
            },
        )
        logger.info(
            "engine.started",
            model=self._config.model,
            tool_count=len(self._tools.list_tools()),
        )

    async def stop(self) -> None:
        """Clean up resources."""
        self._started = False
        self._llm = None
        self._tools = None
        self._context = None
        self._emit("engine.stopped")
        logger.info("engine.stopped")

    async def execute(
        self,
        instruction: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> EngineResult:
        """Execute a task using the agent loop.

        The loop:
        1. Send messages to LLM with tool definitions
        2. If LLM returns tool_use → execute tools → feed results back → loop
        3. If LLM returns text only → done

        Args:
            instruction: What to build/do (plain English).
            timeout: Maximum execution time in seconds.

        Returns:
            EngineResult with success/failure, output, and events.
        """
        if not self._started:
            await self.start()

        assert self._llm is not None
        assert self._tools is not None
        assert self._context is not None

        self._events.clear()
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_turns = 0
        self._emit("engine.task_started", {"instruction": instruction[:200]})

        # Add user message to context
        self._context.add_user_message(instruction)

        try:
            final_text = await asyncio.wait_for(
                self._run_loop(),
                timeout=timeout,
            )

            self._emit(
                "engine.task_completed",
                {
                    "output_length": len(final_text),
                    "turns": self._total_turns,
                    "input_tokens": self._total_input_tokens,
                    "output_tokens": self._total_output_tokens,
                },
            )

            return EngineResult.ok(output=final_text)

        except TimeoutError:
            self._emit("engine.timeout", {"timeout": timeout})
            return EngineResult.fail(
                f"Task timed out after {timeout}s. The agent may still be working."
            )
        except Exception as e:
            logger.error("engine.execute_error", error=str(e))
            self._emit("engine.error", {"error": str(e)})
            return EngineResult.fail(str(e))

    async def _run_loop(self) -> str:
        """The core agent loop. Runs until the LLM stops calling tools."""
        assert self._llm is not None
        assert self._tools is not None
        assert self._context is not None

        final_text = ""

        for turn in range(MAX_TURNS):
            self._total_turns += 1

            # Auto-compact if needed
            if self._context.should_compact():
                self._emit("engine.compacting", {"turn": turn})
                await self._context.compact(self._llm)

            # Get messages and tool definitions
            messages = self._context.get_messages()
            tool_defs = self._tools.get_tool_definitions()

            # Call LLM
            self._emit("engine.llm_call", {"turn": turn, "message_count": len(messages)})

            response = await self._llm.complete(
                messages=messages,
                tools=tool_defs,
                system=self._context.system_prompt,
            )

            self._total_input_tokens += response.input_tokens
            self._total_output_tokens += response.output_tokens

            # Process response
            if response.text:
                final_text = response.text
                self._emit(
                    "engine.assistant_text",
                    {
                        "text": response.text[:500],
                        "turn": turn,
                    },
                )

            # If no tool calls, we're done
            if not response.tool_calls:
                # Add assistant message to context
                self._context.add_assistant_message(
                    text=response.text,
                    tool_calls=None,
                )
                break

            # Add assistant message with tool calls to context
            self._context.add_assistant_message(
                text=response.text,
                tool_calls=response.tool_calls,
            )

            # Execute tool calls
            tool_results = await self._execute_tools(response.tool_calls)

            # Add tool results to context
            for result in tool_results:
                self._context.add_tool_result(
                    tool_use_id=result["tool_use_id"],
                    content=result["content"],
                    is_error=result.get("is_error", False),
                )

        else:
            # Hit MAX_TURNS
            self._emit("engine.max_turns", {"turns": MAX_TURNS})
            if not final_text:
                final_text = f"[Reached maximum {MAX_TURNS} turns without completing]"

        return final_text

    async def _execute_tools(self, tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Execute tool calls and return results."""
        assert self._tools is not None

        results: list[dict[str, Any]] = []

        for call in tool_calls:
            tool_name = call.get("name", "")
            tool_input = call.get("input", {})
            tool_use_id = call.get("id", "")

            self._emit(
                "engine.tool_start",
                {
                    "tool": tool_name,
                    "input": str(tool_input)[:300],
                },
            )

            try:
                result = await self._tools.execute(tool_name, tool_input)

                self._emit(
                    "engine.tool_end",
                    {
                        "tool": tool_name,
                        "success": result.success,
                        "output_length": len(result.output),
                    },
                )

                results.append(
                    {
                        "tool_use_id": tool_use_id,
                        "content": result.output,
                        "is_error": not result.success,
                    }
                )

            except Exception as e:
                logger.error("engine.tool_error", tool=tool_name, error=str(e))
                self._emit("engine.tool_error", {"tool": tool_name, "error": str(e)})
                results.append(
                    {
                        "tool_use_id": tool_use_id,
                        "content": f"Tool execution error: {e}",
                        "is_error": True,
                    }
                )

        return results

    async def execute_streamed(
        self,
        instruction: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> AsyncIterator[StreamEvent]:
        """Execute a task with streaming events.

        Yields StreamEvent objects as the agent works.

        Args:
            instruction: What to build/do.
            timeout: Maximum execution time.

        Yields:
            StreamEvent objects with real-time progress.
        """
        if not self._started:
            await self.start()

        assert self._llm is not None
        assert self._tools is not None
        assert self._context is not None

        self._events.clear()
        self._total_turns = 0
        yield StreamEvent(type="task_started", data={"instruction": instruction[:200]})

        # Add user message
        self._context.add_user_message(instruction)

        try:
            final_text = ""

            for turn in range(MAX_TURNS):
                self._total_turns += 1

                # Auto-compact if needed
                if self._context.should_compact():
                    yield StreamEvent(type="compacting", data={"turn": turn})
                    await self._context.compact(self._llm)

                messages = self._context.get_messages()
                tool_defs = self._tools.get_tool_definitions()

                yield StreamEvent(type="llm_call", data={"turn": turn})

                # Stream the LLM response
                text_chunks: list[str] = []
                response: LLMResponse | None = None

                async for chunk in self._llm.stream(
                    messages=messages,
                    tools=tool_defs,
                    system=self._context.system_prompt,
                ):
                    if chunk.text:
                        text_chunks.append(chunk.text)
                        yield StreamEvent(
                            type="text_delta",
                            data={"text": chunk.text, "turn": turn},
                        )
                    if chunk.is_final:
                        response = chunk.final_response

                if response is None:
                    # Build response from chunks
                    full_text = "".join(text_chunks)
                    response = LLMResponse(text=full_text, tool_calls=[])

                if response.text:
                    final_text = response.text

                # No tool calls → done
                if not response.tool_calls:
                    self._context.add_assistant_message(
                        text=response.text,
                        tool_calls=None,
                    )
                    break

                # Add assistant message with tool calls
                self._context.add_assistant_message(
                    text=response.text,
                    tool_calls=response.tool_calls,
                )

                # Execute tools
                for call in response.tool_calls:
                    tool_name = call.get("name", "")
                    tool_input = call.get("input", {})
                    tool_use_id = call.get("id", "")

                    yield StreamEvent(
                        type="tool_start",
                        data={
                            "tool": tool_name,
                            "input": str(tool_input)[:300],
                        },
                    )

                    try:
                        result = await self._tools.execute(tool_name, tool_input)
                        yield StreamEvent(
                            type="tool_end",
                            data={
                                "tool": tool_name,
                                "success": result.success,
                                "output": result.output[:500],
                            },
                        )
                        self._context.add_tool_result(
                            tool_use_id=tool_use_id,
                            content=result.output,
                            is_error=not result.success,
                        )
                    except Exception as e:
                        yield StreamEvent(
                            type="tool_error",
                            data={
                                "tool": tool_name,
                                "error": str(e),
                            },
                        )
                        self._context.add_tool_result(
                            tool_use_id=tool_use_id,
                            content=f"Tool error: {e}",
                            is_error=True,
                        )

            yield StreamEvent(
                type="task_completed",
                data={"output": final_text, "turns": self._total_turns},
            )

        except TimeoutError:
            yield StreamEvent(type="timeout", data={"timeout": timeout})
        except Exception as e:
            logger.error("engine.streamed_error", error=str(e))
            yield StreamEvent(type="error", data={"error": str(e)})

    async def __aenter__(self) -> AgentEngine:
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()
