"""Core constants for Hauba."""

from __future__ import annotations

from pathlib import Path

# Default Hauba home directory
HAUBA_HOME = Path.home() / ".hauba"

# Subdirectories
AGENTS_DIR = HAUBA_HOME / "agents"
MEMORY_DIR = HAUBA_HOME / "memory"
SKILLS_DIR = HAUBA_HOME / "skills"
LOGS_DIR = HAUBA_HOME / "logs"
BACKUPS_DIR = HAUBA_HOME / "backups"

# Config files
SETTINGS_FILE = HAUBA_HOME / "settings.json"
KEYS_FILE = HAUBA_HOME / "keys.json"
DB_FILE = HAUBA_HOME / "hauba.db"
LAST_SESSION_FILE = HAUBA_HOME / "last_session.json"

# Memory subdirs
OWNER_MEMORY_DIR = MEMORY_DIR / "owner"
KNOWLEDGE_DIR = MEMORY_DIR / "knowledge"
CONTEXT_DIR = MEMORY_DIR / "context"

# Defaults
DEFAULT_LLM_PROVIDER = "anthropic"
DEFAULT_LLM_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.7

# Event types — task lifecycle
EVENT_TASK_CREATED = "task.created"
EVENT_TASK_STARTED = "task.started"
EVENT_TASK_COMPLETED = "task.completed"
EVENT_TASK_FAILED = "task.failed"

# Engine events
EVENT_ENGINE_STARTED = "engine.started"
EVENT_ENGINE_EXECUTING = "engine.executing"
EVENT_ENGINE_COMPLETED = "engine.completed"
EVENT_ENGINE_ERROR = "engine.error"
EVENT_ENGINE_TIMEOUT = "engine.timeout"

# Tool events
EVENT_TOOL_CALLED = "tool.called"
EVENT_TOOL_RESULT = "tool.result"

# TaskLedger events
EVENT_LEDGER_CREATED = "ledger.created"
EVENT_LEDGER_TASK_STARTED = "ledger.task_started"
EVENT_LEDGER_TASK_COMPLETED = "ledger.task_completed"
EVENT_LEDGER_GATE_PASSED = "ledger.gate_passed"
EVENT_LEDGER_GATE_FAILED = "ledger.gate_failed"

# Quality gates
EVENT_QUALITY_CHECK = "quality.check"
EVENT_QUALITY_PASSED = "quality.passed"
EVENT_QUALITY_FAILED = "quality.failed"

# Browser events
EVENT_BROWSER_NAVIGATE = "browser.navigate"
EVENT_BROWSER_CLICK = "browser.click"
EVENT_BROWSER_TYPE = "browser.type"
EVENT_BROWSER_SCREENSHOT = "browser.screenshot"

# Screen control events
EVENT_SCREEN_CAPTURE = "screen.capture"
EVENT_SCREEN_CLICK = "screen.click"
EVENT_SCREEN_TYPE = "screen.type"

# Replay events
EVENT_REPLAY_STARTED = "replay.started"
EVENT_REPLAY_ENTRY = "replay.entry"
EVENT_REPLAY_FINISHED = "replay.finished"

# Web search events
EVENT_SEARCH_QUERY = "search.query"

# Screenshots directory
SCREENSHOTS_DIR = AGENTS_DIR / "screenshots"

# Screen defaults
DEFAULT_SCREEN_DELAY = 0.5
EMERGENCY_STOP_FILE = HAUBA_HOME / "STOP"

# Voice events
EVENT_VOICE_LISTENING = "voice.listening"
EVENT_VOICE_TRANSCRIBED = "voice.transcribed"
EVENT_VOICE_SPEAKING = "voice.speaking"

# Channel events
EVENT_CHANNEL_MESSAGE = "channel.message"
EVENT_CHANNEL_CONNECTED = "channel.connected"
EVENT_CHANNEL_DISCONNECTED = "channel.disconnected"

# Notification events
EVENT_NOTIFICATION_SENT = "notification.sent"

# Compose events
EVENT_COMPOSE_STARTED = "compose.started"
EVENT_COMPOSE_AGENT_CREATED = "compose.agent_created"
EVENT_COMPOSE_AGENT_STARTED = "compose.agent_started"
EVENT_COMPOSE_AGENT_COMPLETED = "compose.agent_completed"
EVENT_COMPOSE_AGENT_FAILED = "compose.agent_failed"
EVENT_COMPOSE_COMPLETED = "compose.completed"
EVENT_COMPOSE_FAILED = "compose.failed"

# Skill events
EVENT_SKILL_INSTALLED = "skill.installed"
EVENT_SKILL_MATCHED = "skill.matched"

# Bundled skills directory (shipped inside the wheel)
BUNDLED_SKILLS_DIR = Path(__file__).resolve().parent.parent / "bundled_skills"

# Plugin system
PLUGINS_DIR = HAUBA_HOME / "plugins"
BUNDLED_PLUGINS_DIR = Path(__file__).resolve().parent.parent / "bundled_plugins"

# Plugin events
EVENT_PLUGIN_LOADED = "plugin.loaded"
EVENT_PLUGIN_UNLOADED = "plugin.unloaded"
EVENT_PLUGIN_ERROR = "plugin.error"

# Email events
EVENT_EMAIL_SENT = "email.sent"
EVENT_EMAIL_FAILED = "email.failed"

# Auto-reply events
EVENT_AUTOREPLY_TRIGGERED = "autoreply.triggered"
EVENT_AUTOREPLY_ENABLED = "autoreply.enabled"
EVENT_AUTOREPLY_DISABLED = "autoreply.disabled"

# Web fetch events
EVENT_WEB_FETCH = "web.fetch"
