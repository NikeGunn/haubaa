"""LLM client — direct API calls via litellm.

Supports Anthropic, OpenAI, Google, Ollama, DeepSeek, and any
litellm-compatible provider. No SDK abstraction layers — just
clean request/response with tool calling support.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class LLMMessage:
    """A single message in the conversation."""

    role: str  # "system", "user", "assistant", "tool"
    content: Any = ""  # str or list of content blocks
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class LLMResponse:
    """Response from an LLM call."""

    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


@dataclass
class StreamChunk:
    """A single chunk from a streaming LLM response."""

    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    is_final: bool = False
    final_response: LLMResponse | None = None


class LLMClient:
    """Direct LLM API client via litellm.

    Handles provider-specific quirks, model resolution,
    and tool calling normalization across all providers.
    """

    def __init__(
        self,
        provider: Any,
        api_key: str = "",
        model: str = "",
        base_url: str | None = None,
    ) -> None:
        self._provider = provider.value if hasattr(provider, "value") else str(provider)
        self._api_key = api_key
        self._model = model or "claude-sonnet-4-5-20250514"
        self._base_url = base_url
        self._configure_env()

    def _configure_env(self) -> None:
        """Set environment variables for litellm."""
        if self._api_key:
            env_map = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
                "google": "GEMINI_API_KEY",
            }
            env_var = env_map.get(self._provider)
            if env_var:
                os.environ.setdefault(env_var, self._api_key)

    def _resolve_model(self) -> str:
        """Resolve model identifier with provider prefix for litellm."""
        model = self._model

        # OpenAI models don't need prefix
        if (
            self._provider == "openai"
            or model.startswith("gpt-")
            or model.startswith("o1-")
            or model.startswith("o3-")
            or model.startswith("o4-")
        ):
            return model

        # Already has prefix
        if "/" in model:
            return model

        # Add provider prefix
        prefix_map = {
            "anthropic": "anthropic",
            "ollama": "ollama_chat",
            "deepseek": "deepseek",
            "google": "gemini",
        }
        prefix = prefix_map.get(self._provider, self._provider)
        return f"{prefix}/{model}"

    def _build_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert tool definitions to litellm/OpenAI format."""
        result = []
        for tool in tools:
            result.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                    },
                }
            )
        return result

    def _build_messages(
        self,
        messages: list[LLMMessage],
        system: str = "",
    ) -> list[dict[str, Any]]:
        """Convert LLMMessages to litellm format."""
        result: list[dict[str, Any]] = []

        # System message first
        if system:
            result.append({"role": "system", "content": system})

        for msg in messages:
            if msg.role == "assistant" and msg.tool_calls:
                # Assistant message with tool calls
                entry: dict[str, Any] = {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tc.get("name", ""),
                                "arguments": _json_dumps(tc.get("input", {})),
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
                result.append(entry)
            elif msg.role == "tool":
                result.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id or "",
                        "content": str(msg.content) if msg.content else "",
                    }
                )
            else:
                result.append(
                    {
                        "role": msg.role,
                        "content": msg.content or "",
                    }
                )

        return result

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse litellm response into LLMResponse."""
        choice = response.choices[0] if response.choices else None
        if not choice:
            return LLMResponse()

        message = choice.message

        # Extract text
        text = message.content or ""

        # Extract tool calls
        tool_calls: list[dict[str, Any]] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "input": _json_loads(tc.function.arguments),
                    }
                )

        # Token usage
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason=getattr(choice, "finish_reason", ""),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=getattr(response, "model", ""),
        )

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        system: str = "",
    ) -> LLMResponse:
        """Make a single LLM completion call with tool support.

        Args:
            messages: Conversation messages.
            tools: Tool definitions (optional).
            system: System prompt.

        Returns:
            LLMResponse with text and/or tool calls.
        """
        import litellm

        model = self._resolve_model()
        litellm_messages = self._build_messages(messages, system)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": litellm_messages,
            "max_tokens": 16384,
        }

        if self._base_url:
            kwargs["api_base"] = self._base_url

        if tools:
            kwargs["tools"] = self._build_tools(tools)
            kwargs["tool_choice"] = "auto"

        try:
            response = await litellm.acompletion(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            logger.error("llm.completion_error", model=model, error=str(e))
            raise

    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        system: str = "",
    ) -> Any:
        """Stream an LLM completion with tool support.

        Yields StreamChunk objects as tokens arrive.
        The final chunk has is_final=True with the complete response.

        Args:
            messages: Conversation messages.
            tools: Tool definitions.
            system: System prompt.

        Yields:
            StreamChunk objects.
        """
        import litellm

        model = self._resolve_model()
        litellm_messages = self._build_messages(messages, system)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": litellm_messages,
            "max_tokens": 16384,
            "stream": True,
        }

        if self._base_url:
            kwargs["api_base"] = self._base_url

        if tools:
            kwargs["tools"] = self._build_tools(tools)
            kwargs["tool_choice"] = "auto"

        try:
            response = await litellm.acompletion(**kwargs)

            full_text = ""
            tool_calls_acc: dict[int, dict[str, Any]] = {}

            async for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                # Text content
                if delta.content:
                    full_text += delta.content
                    yield StreamChunk(text=delta.content)

                # Tool calls (accumulated across chunks)
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {
                                "id": "",
                                "name": "",
                                "arguments": "",
                            }
                        if tc_delta.id:
                            tool_calls_acc[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tool_calls_acc[idx]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                tool_calls_acc[idx]["arguments"] += tc_delta.function.arguments

                # Check finish reason
                finish_reason = chunk.choices[0].finish_reason if chunk.choices else None
                if finish_reason:
                    # Build final tool calls
                    final_tool_calls = []
                    for _idx, tc in sorted(tool_calls_acc.items()):
                        final_tool_calls.append(
                            {
                                "id": tc["id"],
                                "name": tc["name"],
                                "input": _json_loads(tc["arguments"]),
                            }
                        )

                    final_response = LLMResponse(
                        text=full_text,
                        tool_calls=final_tool_calls,
                        stop_reason=finish_reason,
                    )

                    yield StreamChunk(
                        is_final=True,
                        final_response=final_response,
                    )

        except Exception as e:
            logger.error("llm.stream_error", model=model, error=str(e))
            raise

    async def summarize(self, text: str, max_tokens: int = 500) -> str:
        """Summarize text for context compaction.

        Args:
            text: Text to summarize.
            max_tokens: Maximum tokens in summary.

        Returns:
            Summarized text.
        """
        messages = [
            LLMMessage(
                role="user",
                content=(
                    "Summarize the following conversation history concisely. "
                    "Preserve all key decisions, file paths, code changes, errors, "
                    "and important context. Be specific — names, paths, and values matter.\n\n"
                    f"{text}"
                ),
            )
        ]

        response = await self.complete(messages=messages, system="You are a precise summarizer.")
        return response.text


def _json_dumps(obj: Any) -> str:
    """Safely serialize to JSON string."""
    import json

    if isinstance(obj, str):
        return obj
    try:
        return json.dumps(obj)
    except (TypeError, ValueError):
        return str(obj)


def _json_loads(s: str) -> dict[str, Any]:
    """Safely parse JSON string."""
    import json

    if not s:
        return {}
    try:
        result = json.loads(s)
        return result if isinstance(result, dict) else {"value": result}
    except (json.JSONDecodeError, TypeError):
        return {"raw": s}
