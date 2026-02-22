# Skill: Hauba Python Development

## Context
You are building Hauba — an open-source AI agent framework in Python 3.11+.
The codebase lives at `src/hauba/` and uses async/await throughout.

## Architecture Rules
- ALL I/O operations must be async (aiosqlite, httpx, asyncio.subprocess)
- Use `structlog` for all logging — structured JSON format
- Use `Typer` for CLI commands
- Use `Rich` for terminal output (progress bars, tables, panels)
- Use `litellm` as the unified LLM client (supports Claude, OpenAI, Ollama, etc.)
- Use `SQLite` (via aiosqlite) for ALL persistence — no Redis, no PostgreSQL
- Use `Pydantic v2` for all data models and validation

## Agent Implementation Pattern
Every agent must follow this lifecycle:
1. **Receive** task via event emitter
2. **Deliberate** — think before acting (minimum think time enforced)
3. **Plan** — decompose into sub-tasks with dependencies
4. **Create TaskLedger** — bit-vector + hash tracking before ANY execution
5. **Execute** — run plan respecting dependency DAG
6. **Review** — quality gate check on output
7. **Deliver** — only after GateCheck() passes on ledger

## File Conventions
- One primary class per file
- Type hints on ALL function signatures
- Docstrings on all public methods (Google style)
- Constants in UPPER_SNAKE_CASE
- Private methods prefixed with underscore

## Testing Rules
- Every module gets a corresponding test file: `src/hauba/core/engine.py` → `tests/unit/core/test_engine.py`
- Mock LLM calls in unit tests using recorded responses
- Use `pytest.mark.asyncio` for async test functions
- Use fixtures for common setup (agent instances, mock LLM, temp directories)

## Common Imports
```python
from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Any
from pydantic import BaseModel
import structlog

logger = structlog.get_logger()
```

## Error Handling
- Custom exceptions in `src/hauba/exceptions.py`
- Never catch bare `Exception` — always catch specific types
- Log errors with full context: task_id, agent_id, phase
- Use `Result[T, E]` pattern for operations that can fail gracefully
