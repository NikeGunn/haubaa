"""Type definitions for the Hauba Engine V4."""

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
    DEEPSEEK = "deepseek"
    GOOGLE = "google"


@dataclass
class EngineConfig:
    """Configuration for a Hauba Engine session.

    Users bring their own API key — Hauba owner pays nothing.

    Attributes:
        provider: The LLM provider type.
        api_key: User's API key for the provider.
        model: Model identifier (e.g., "claude-sonnet-4-5-20250514", "gpt-4o").
        base_url: Optional custom API endpoint URL.
        working_directory: Directory where the agent operates.
        skill_directories: Directories to load skills from.
        streaming: Whether to stream responses.
        session_persist: Whether to persist session state.
        auto_install_deps: Whether to auto-install dependencies.
    """

    provider: ProviderType = ProviderType.ANTHROPIC
    api_key: str = ""
    model: str = "claude-sonnet-4-5-20250514"
    base_url: str | None = None
    working_directory: str = "."
    skill_directories: list[str] = field(default_factory=list)
    streaming: bool = True
    copilot_cli_path: str | None = None  # V3 compat — unused in V4
    session_persist: bool = True
    auto_install_deps: bool = True

    def to_provider_config(self) -> dict[str, Any]:
        """Convert to provider config format (V3 compat)."""
        config: dict[str, Any] = {}
        provider = self.provider.value if hasattr(self.provider, "value") else str(self.provider)

        if provider == "anthropic":
            config["type"] = "anthropic"
            config["base_url"] = self.base_url or "https://api.anthropic.com"
        elif provider == "openai":
            config["type"] = "openai"
            config["base_url"] = self.base_url or "https://api.openai.com/v1"
        elif provider == "azure":
            config["type"] = "azure"
            if self.base_url:
                config["base_url"] = self.base_url
        elif provider == "ollama":
            config["type"] = "openai"
            config["base_url"] = self.base_url or "http://localhost:11434/v1"
        elif provider == "deepseek":
            config["type"] = "deepseek"
            config["base_url"] = self.base_url or "https://api.deepseek.com"
        elif provider == "google":
            config["type"] = "google"

        if self.api_key:
            config["api_key"] = self.api_key

        return config


@dataclass
class EngineEvent:
    """An event emitted during engine execution.

    Attributes:
        type: Event type string (e.g., "engine.tool_start", "engine.llm_call").
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
        session_id: Session ID (for resumption).
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
