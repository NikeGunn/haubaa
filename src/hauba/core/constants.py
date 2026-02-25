"""Core constants for Hauba."""

from __future__ import annotations

from pathlib import Path

# Default Hauba home directory
HAUBA_HOME = Path.home() / ".hauba"

# Subdirectories
AGENTS_DIR = HAUBA_HOME / "agents"
MEMORY_DIR = HAUBA_HOME / "memory"
SKILLS_DIR = HAUBA_HOME / "skills"
STRATEGIES_DIR = HAUBA_HOME / "strategies"
LOGS_DIR = HAUBA_HOME / "logs"
BACKUPS_DIR = HAUBA_HOME / "backups"

# Config files
SETTINGS_FILE = HAUBA_HOME / "settings.json"
KEYS_FILE = HAUBA_HOME / "keys.json"
DB_FILE = HAUBA_HOME / "hauba.db"

# Memory subdirs
OWNER_MEMORY_DIR = MEMORY_DIR / "owner"
KNOWLEDGE_DIR = MEMORY_DIR / "knowledge"
CONTEXT_DIR = MEMORY_DIR / "context"

# Defaults
DEFAULT_LLM_PROVIDER = "anthropic"
DEFAULT_LLM_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.7
DEFAULT_THINK_TIME_SECONDS = 2.0

# Event types
EVENT_TASK_CREATED = "task.created"
EVENT_TASK_STARTED = "task.started"
EVENT_TASK_COMPLETED = "task.completed"
EVENT_TASK_FAILED = "task.failed"
EVENT_AGENT_THINKING = "agent.thinking"
EVENT_AGENT_EXECUTING = "agent.executing"
EVENT_AGENT_REVIEWING = "agent.reviewing"
EVENT_LLM_REQUEST = "llm.request"
EVENT_LLM_RESPONSE = "llm.response"
EVENT_TOOL_CALLED = "tool.called"
EVENT_TOOL_RESULT = "tool.result"

# Phase 2: Multi-agent events
EVENT_AGENT_SPAWNED = "agent.spawned"
EVENT_AGENT_TERMINATED = "agent.terminated"
EVENT_MILESTONE_STARTED = "milestone.started"
EVENT_MILESTONE_COMPLETED = "milestone.completed"
EVENT_MILESTONE_FAILED = "milestone.failed"
EVENT_WORKER_RESULT = "worker.result"

# Phase 2: Cross-agent communication
EVENT_FINDING_SHARED = "cross.finding_shared"
EVENT_REQUEST_DATA = "cross.request_data"
EVENT_DATA_PROVIDED = "cross.data_provided"

# Phase 2: TaskLedger events
EVENT_LEDGER_CREATED = "ledger.created"
EVENT_LEDGER_TASK_STARTED = "ledger.task_started"
EVENT_LEDGER_TASK_COMPLETED = "ledger.task_completed"
EVENT_LEDGER_GATE_PASSED = "ledger.gate_passed"
EVENT_LEDGER_GATE_FAILED = "ledger.gate_failed"

# Phase 2: Quality gates
EVENT_QUALITY_CHECK = "quality.check"
EVENT_QUALITY_PASSED = "quality.passed"
EVENT_QUALITY_FAILED = "quality.failed"

# Phase 3: Browser events
EVENT_BROWSER_NAVIGATE = "browser.navigate"
EVENT_BROWSER_CLICK = "browser.click"
EVENT_BROWSER_TYPE = "browser.type"
EVENT_BROWSER_SCREENSHOT = "browser.screenshot"

# Phase 3: Screen control events
EVENT_SCREEN_CAPTURE = "screen.capture"
EVENT_SCREEN_CLICK = "screen.click"
EVENT_SCREEN_TYPE = "screen.type"

# Phase 3: Replay events
EVENT_REPLAY_STARTED = "replay.started"
EVENT_REPLAY_ENTRY = "replay.entry"
EVENT_REPLAY_FINISHED = "replay.finished"

# Phase 3: Web search events
EVENT_SEARCH_QUERY = "search.query"

# Screenshots directory
SCREENSHOTS_DIR = AGENTS_DIR / "screenshots"

# Phase 3: Defaults
DEFAULT_SCREEN_DELAY = 0.5
DEFAULT_COMPUTER_USE_MAX_ITERATIONS = 20
EMERGENCY_STOP_FILE = HAUBA_HOME / "STOP"

# Phase 4: Voice events
EVENT_VOICE_LISTENING = "voice.listening"
EVENT_VOICE_TRANSCRIBED = "voice.transcribed"
EVENT_VOICE_SPEAKING = "voice.speaking"

# Phase 4: Channel events
EVENT_CHANNEL_MESSAGE = "channel.message"
EVENT_CHANNEL_CONNECTED = "channel.connected"
EVENT_CHANNEL_DISCONNECTED = "channel.disconnected"

# Phase 4: Notification events
EVENT_NOTIFICATION_SENT = "notification.sent"

# Phase 5: Compose events
EVENT_COMPOSE_STARTED = "compose.started"
EVENT_COMPOSE_AGENT_CREATED = "compose.agent_created"
EVENT_COMPOSE_AGENT_STARTED = "compose.agent_started"
EVENT_COMPOSE_AGENT_COMPLETED = "compose.agent_completed"
EVENT_COMPOSE_AGENT_FAILED = "compose.agent_failed"
EVENT_COMPOSE_COMPLETED = "compose.completed"
EVENT_COMPOSE_FAILED = "compose.failed"

# Phase 5: Skill events
EVENT_SKILL_INSTALLED = "skill.installed"
EVENT_SKILL_MATCHED = "skill.matched"

# Phase 5: Bundled content directories (shipped inside the wheel)
BUNDLED_SKILLS_DIR = Path(__file__).resolve().parent.parent / "bundled_skills"
BUNDLED_STRATEGIES_DIR = Path(__file__).resolve().parent.parent / "bundled_strategies"

# Agent defaults
DEFAULT_SUBAGENT_THINK_TIME = 10.0
DEFAULT_WORKER_TIMEOUT = 300.0  # 5 minutes
DEFAULT_MAX_PARALLEL_WORKERS = 4
DEFAULT_MAX_AGENT_ITERATIONS = 50  # Max agentic loop iterations (prevent infinite loops)
DEFAULT_MAX_WORKER_ITERATIONS = 25  # Max iterations for worker agentic loops
