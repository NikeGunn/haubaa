"""Type definitions for the Hauba Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class ProviderType(str, Enum):
    """Supported LLM provider types for BYOK."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    AZURE = "azure"
    OLLAMA = "ollama"


@dataclass
class EngineConfig:
    """Configuration for a Hauba Engine session.

    Users bring their own API key — Hauba owner pays nothing.

    Attributes:
        provider: The LLM provider type.
        api_key: User's API key for the provider.
        model: Model identifier (e.g., "claude-sonnet-4.5", "gpt-4").
        base_url: Optional custom API endpoint URL.
        working_directory: Directory where the agent operates.
        skill_directories: Directories to load skills from.
        streaming: Whether to stream responses.
        copilot_cli_path: Path to copilot CLI binary.
    """

    provider: ProviderType = ProviderType.ANTHROPIC
    api_key: str = ""
    model: str = "claude-sonnet-4-5-20250514"
    base_url: str | None = None
    working_directory: str = "."
    skill_directories: list[str] = field(default_factory=list)
    streaming: bool = True
    copilot_cli_path: str | None = None

    def to_provider_config(self) -> dict[str, Any]:
        """Convert to Copilot SDK ProviderConfig format."""
        config: dict[str, Any] = {}

        if self.provider == ProviderType.ANTHROPIC:
            config["type"] = "anthropic"
            config["base_url"] = self.base_url or "https://api.anthropic.com"
            if self.api_key:
                config["api_key"] = self.api_key
        elif self.provider == ProviderType.OPENAI:
            config["type"] = "openai"
            config["base_url"] = self.base_url or "https://api.openai.com/v1"
            if self.api_key:
                config["api_key"] = self.api_key
        elif self.provider == ProviderType.AZURE:
            config["type"] = "azure"
            if self.base_url:
                config["base_url"] = self.base_url
            if self.api_key:
                config["api_key"] = self.api_key
        elif self.provider == ProviderType.OLLAMA:
            config["type"] = "openai"
            config["base_url"] = self.base_url or "http://localhost:11434/v1"
            # Ollama doesn't need an API key

        return config


@dataclass
class EngineEvent:
    """An event emitted during engine execution.

    Attributes:
        type: Event type string (e.g., "assistant.message", "tool.execution_start").
        data: Event-specific data.
        timestamp: When the event occurred.
    """

    type: str
    data: Any = None
    timestamp: float = 0.0


@dataclass
class EngineResult:
    """Result of an engine execution.

    Attributes:
        success: Whether the task completed successfully.
        output: The final output text.
        events: List of events that occurred during execution.
        error: Error message if failed.
        session_id: The Copilot session ID (for resumption).
    """

    success: bool
    output: str = ""
    events: list[EngineEvent] = field(default_factory=list)
    error: str | None = None
    session_id: str | None = None

    @staticmethod
    def ok(output: str, session_id: str | None = None) -> EngineResult:
        return EngineResult(success=True, output=output, session_id=session_id)

    @staticmethod
    def fail(error: str) -> EngineResult:
        return EngineResult(success=False, error=error)


# Status of a running task
TaskExecutionStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
