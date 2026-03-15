"""Tests for LLMClient — direct API calls via litellm."""

from __future__ import annotations

from hauba.engine.llm import (
    LLMClient,
    LLMMessage,
    LLMResponse,
    StreamChunk,
    _json_dumps,
    _json_loads,
)
from hauba.engine.types import ProviderType

# --- LLMMessage tests ---


def test_llm_message_defaults() -> None:
    """LLMMessage has sensible defaults."""
    msg = LLMMessage(role="user", content="hello")
    assert msg.role == "user"
    assert msg.content == "hello"
    assert msg.tool_calls is None
    assert msg.tool_call_id is None


def test_llm_message_with_tool_calls() -> None:
    """LLMMessage stores tool calls."""
    msg = LLMMessage(
        role="assistant",
        content="Let me check.",
        tool_calls=[{"id": "1", "name": "bash", "input": {"command": "ls"}}],
    )
    assert len(msg.tool_calls) == 1
    assert msg.tool_calls[0]["name"] == "bash"


def test_llm_message_tool_result() -> None:
    """LLMMessage can be a tool result."""
    msg = LLMMessage(role="tool", content="file1.txt\nfile2.txt", tool_call_id="call_1")
    assert msg.role == "tool"
    assert msg.tool_call_id == "call_1"


# --- LLMResponse tests ---


def test_llm_response_defaults() -> None:
    """LLMResponse has empty defaults."""
    resp = LLMResponse()
    assert resp.text == ""
    assert resp.tool_calls == []
    assert resp.input_tokens == 0
    assert resp.output_tokens == 0


def test_llm_response_with_data() -> None:
    """LLMResponse stores all fields."""
    resp = LLMResponse(
        text="Hello",
        tool_calls=[{"id": "1", "name": "bash", "input": {}}],
        stop_reason="stop",
        input_tokens=100,
        output_tokens=50,
        model="test-model",
    )
    assert resp.text == "Hello"
    assert len(resp.tool_calls) == 1
    assert resp.model == "test-model"


# --- StreamChunk tests ---


def test_stream_chunk_text() -> None:
    """StreamChunk holds text delta."""
    chunk = StreamChunk(text="Hello ")
    assert chunk.text == "Hello "
    assert not chunk.is_final
    assert chunk.final_response is None


def test_stream_chunk_final() -> None:
    """StreamChunk marks final response."""
    resp = LLMResponse(text="done")
    chunk = StreamChunk(is_final=True, final_response=resp)
    assert chunk.is_final
    assert chunk.final_response.text == "done"


# --- LLMClient init tests ---


def test_client_init_anthropic() -> None:
    """Client initializes for Anthropic provider."""
    client = LLMClient(
        provider=ProviderType.ANTHROPIC,
        api_key="test-key",
        model="claude-sonnet-4-5-20250514",
    )
    assert client._provider == "anthropic"
    assert client._model == "claude-sonnet-4-5-20250514"


def test_client_init_openai() -> None:
    """Client initializes for OpenAI provider."""
    client = LLMClient(
        provider=ProviderType.OPENAI,
        api_key="test-key",
        model="gpt-4o",
    )
    assert client._provider == "openai"


# --- Model resolution tests ---


def test_resolve_model_openai() -> None:
    """OpenAI models don't get prefix."""
    client = LLMClient(provider=ProviderType.OPENAI, model="gpt-4o")
    assert client._resolve_model() == "gpt-4o"


def test_resolve_model_openai_o1() -> None:
    """o1 models don't get prefix."""
    client = LLMClient(provider=ProviderType.OPENAI, model="o1-mini")
    assert client._resolve_model() == "o1-mini"


def test_resolve_model_anthropic() -> None:
    """Anthropic models get anthropic/ prefix."""
    client = LLMClient(provider=ProviderType.ANTHROPIC, model="claude-sonnet-4-5-20250514")
    assert client._resolve_model() == "anthropic/claude-sonnet-4-5-20250514"


def test_resolve_model_ollama() -> None:
    """Ollama models get ollama_chat/ prefix."""
    client = LLMClient(provider=ProviderType.OLLAMA, model="llama3")
    assert client._resolve_model() == "ollama_chat/llama3"


def test_resolve_model_already_prefixed() -> None:
    """Already-prefixed models are returned as-is."""
    client = LLMClient(provider=ProviderType.ANTHROPIC, model="anthropic/claude-3-haiku")
    assert client._resolve_model() == "anthropic/claude-3-haiku"


# --- Message building tests ---


def test_build_messages_simple() -> None:
    """Builds simple user/assistant messages."""
    client = LLMClient(provider=ProviderType.ANTHROPIC)
    messages = [
        LLMMessage(role="user", content="hello"),
        LLMMessage(role="assistant", content="hi"),
    ]
    built = client._build_messages(messages, system="Be helpful")

    assert built[0]["role"] == "system"
    assert built[0]["content"] == "Be helpful"
    assert built[1]["role"] == "user"
    assert built[1]["content"] == "hello"
    assert built[2]["role"] == "assistant"
    assert built[2]["content"] == "hi"


def test_build_messages_with_tool_calls() -> None:
    """Builds assistant messages with tool calls."""
    client = LLMClient(provider=ProviderType.ANTHROPIC)
    messages = [
        LLMMessage(
            role="assistant",
            content="Let me check.",
            tool_calls=[{"id": "call_1", "name": "bash", "input": {"command": "ls"}}],
        ),
        LLMMessage(role="tool", content="file1.txt", tool_call_id="call_1"),
    ]
    built = client._build_messages(messages)

    assert built[0]["role"] == "assistant"
    assert "tool_calls" in built[0]
    assert built[0]["tool_calls"][0]["function"]["name"] == "bash"
    assert built[1]["role"] == "tool"
    assert built[1]["tool_call_id"] == "call_1"


def test_build_messages_no_system() -> None:
    """No system message when system prompt is empty."""
    client = LLMClient(provider=ProviderType.ANTHROPIC)
    messages = [LLMMessage(role="user", content="hello")]
    built = client._build_messages(messages, system="")

    assert built[0]["role"] == "user"


# --- Tool building tests ---


def test_build_tools() -> None:
    """Converts tool definitions to litellm format."""
    client = LLMClient(provider=ProviderType.ANTHROPIC)
    tools = [
        {
            "name": "bash",
            "description": "Run shell commands",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        }
    ]
    built = client._build_tools(tools)

    assert len(built) == 1
    assert built[0]["type"] == "function"
    assert built[0]["function"]["name"] == "bash"
    assert built[0]["function"]["description"] == "Run shell commands"


# --- JSON helpers ---


def test_json_dumps_dict() -> None:
    """_json_dumps serializes dicts."""
    assert _json_dumps({"a": 1}) == '{"a": 1}'


def test_json_dumps_string() -> None:
    """_json_dumps passes strings through."""
    assert _json_dumps("already json") == "already json"


def test_json_loads_valid() -> None:
    """_json_loads parses valid JSON."""
    assert _json_loads('{"a": 1}') == {"a": 1}


def test_json_loads_empty() -> None:
    """_json_loads returns empty dict for empty string."""
    assert _json_loads("") == {}


def test_json_loads_invalid() -> None:
    """_json_loads returns raw value for invalid JSON."""
    result = _json_loads("not json")
    assert "raw" in result
