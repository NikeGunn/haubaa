"""Core type definitions for Hauba."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")
E = TypeVar("E")


class Result(BaseModel, Generic[T, E]):
    """Result pattern for operations that can fail gracefully."""

    success: bool
    value: T | None = None
    error: E | None = None

    @classmethod
    def ok(cls, value: T) -> Result[T, E]:
        return cls(success=True, value=value)

    @classmethod
    def fail(cls, error: E) -> Result[T, E]:
        return cls(success=False, error=error)


class TaskStatus(str, Enum):
    """Task status values."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    VERIFIED = "verified"
    FAILED = "failed"


class ActionType(str, Enum):
    """Detected intent action types."""

    BUILD = "build"
    EDIT = "edit"
    ANALYZE = "analyze"
    DEPLOY = "deploy"
    RESEARCH = "research"
    DEBUG = "debug"
    TEST = "test"
    UNKNOWN = "unknown"


class Event(BaseModel):
    """An event in the Hauba event system."""

    id: str = Field(default_factory=lambda: "")
    topic: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = ""
    task_id: str = ""


class TaskStep(BaseModel):
    """A single step in a task plan."""

    id: str
    description: str
    dependencies: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.NOT_STARTED
    tool: str | None = None
    estimated_complexity: int = 1  # 1-5


class Milestone(BaseModel):
    """A milestone is a major deliverable assigned to a SubAgent."""

    id: str
    description: str
    dependencies: list[str] = Field(default_factory=list)
    tasks: list[TaskStep] = Field(default_factory=list)
    assigned_to: str | None = None
    status: TaskStatus = TaskStatus.NOT_STARTED


class ToolResult(BaseModel):
    """Result from a tool execution."""

    tool_name: str
    success: bool
    output: str = ""
    error: str = ""
    exit_code: int = 0


class BrowserAction(str, Enum):
    """Browser automation actions."""

    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    EXTRACT = "extract"
    SCREENSHOT = "screenshot"
    WAIT = "wait"


class ScreenAction(str, Enum):
    """Screen control actions."""

    CAPTURE = "capture"
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    HOTKEY = "hotkey"


class SearchResult(BaseModel):
    """A single web search result."""

    title: str
    snippet: str
    url: str
    rank: int = 0


class ReplayEntry(BaseModel):
    """A single entry in a replay recording."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    topic: str
    data: dict[str, Any] = Field(default_factory=dict)
    source: str = ""
    task_id: str = ""


# Compose types


class ComposeAgentConfig(BaseModel):
    """Configuration for a single agent in a compose file."""

    role: str
    description: str = ""
    skills: list[str] = Field(default_factory=list)
    model: str = ""
    depends_on: list[str] = Field(default_factory=list)


class ComposeSettings(BaseModel):
    """Global settings in a compose file."""

    max_parallel_agents: int = 4
    deliberation_min_seconds: float = 30.0
    sandbox: str = "process"
    memory: str = "sqlite"


class ComposeConfig(BaseModel):
    """Parsed hauba.yaml compose configuration."""

    team: str
    description: str = ""
    model: str = ""
    settings: ComposeSettings = Field(default_factory=ComposeSettings)
    agents: dict[str, ComposeAgentConfig] = Field(default_factory=dict)
    output: str = "./output"


# --- V4.0 Types ---


class WebFetchResult(BaseModel):
    """Result of fetching a web page."""

    url: str
    title: str = ""
    content: str = ""
    status_code: int = 0
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PluginHook(str, Enum):
    """Hook types for the plugin system."""

    ON_MESSAGE = "on_message"
    ON_TASK_COMPLETE = "on_task_complete"
    ON_TASK_QUEUED = "on_task_queued"
    ON_STARTUP = "on_startup"
    ON_SHUTDOWN = "on_shutdown"


class EmailMessage(BaseModel):
    """An email message to send on owner's behalf."""

    to: str
    subject: str
    body: str
    cc: str = ""
    bcc: str = ""
    reply_to: str = ""
