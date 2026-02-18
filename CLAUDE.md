# Hauba — AI Agent Operating System

> **IMPORTANT: Read this entire file before writing any code.**

## What Is Hauba?

Hauba is an **open-source AI agent framework** that orchestrates teams of AI agents to complete complex tasks — like a real software company, not a chatbot.

**One command. An AI engineering team at your service.**

```bash
pip install hauba
hauba init
hauba run "build me a SaaS dashboard with auth and Stripe billing"
```

## Architecture Overview

```
Python-first. Single process. SQLite storage. Zero external dependencies.

hauba/
├── src/hauba/           # Core Python package
│   ├── cli.py           # Typer CLI (entry point)
│   ├── core/            # Engine, events, config, sandbox
│   ├── agents/          # Director, SubAgent, Worker, CoWorker
│   ├── brain/           # LLM router, deliberation, planner, intent
│   ├── memory/          # SQLite store, context, embeddings
│   ├── skills/          # Skill loader, matcher, executor
│   ├── tools/           # Bash, files, git, web, browser
│   ├── ledger/          # TaskLedger (zero-hallucination tracker)
│   └── ui/              # Terminal (Rich) + Web (FastAPI)
├── skills/              # Built-in skill .md files
├── strategies/          # Strategy .yaml playbooks
├── tests/               # pytest test suite
├── pyproject.toml       # Project config
└── hauba.yaml.example   # Example agent team composition
```

## Core Design Principles

1. **Python-first** — No Go, no gRPC, no protobuf until profiling proves necessity. Use `asyncio` for concurrency.
2. **Zero dependencies beyond pip** — No Docker, Redis, or PostgreSQL required. SQLite for everything.
3. **Think-Then-Act** — Every agent deliberates before executing. Minimum think times enforced.
4. **TaskLedger** — Zero-hallucination tracking via bit-vector + SHA-256 hash-chain + WAL. No task forgotten, no output faked.
5. **Wait Architecture** — Dependent agents WAIT. Independent agents run in PARALLEL.
6. **Skills as .md files** — Human-readable, composable, installable.
7. **Strategies as .yaml** — Cognitive playbooks that teach agents HOW to think about a domain.
8. **File-based memory** — Agents write `.md` notes before acting. If it's not on disk, it didn't happen.
9. **Event-driven** — All agent communication via events. Full audit trail.
10. **Offline-capable** — Works with Ollama local models. No internet required.

## Agent Hierarchy

```
Owner (Human)
  └── Director Agent (CEO) — deliberates, plans, delegates
       ├── SubAgent (Team Lead) — manages milestone, spawns workers
       │    ├── Worker (Specialist) — executes in sandbox, produces artifacts
       │    │    └── CoWorker (Helper) — ephemeral, single task, dies
       │    └── Worker ...
       └── SubAgent ...
```

**Communication:** All via async event emitter. No tight coupling.
**Memory:** Every agent writes plans/logs to `~/.hauba/` before executing.
**TaskLedger:** Every level maintains its own ledger. GateCheck before delivery.

## Coding Standards

### Python
- **Version:** 3.11+
- **Type hints:** Mandatory on all functions
- **Async:** Use `async/await` for all I/O operations
- **Logging:** `structlog` with structured JSON output
- **Testing:** `pytest` + `pytest-asyncio`. 80%+ coverage target.
- **Linting:** `ruff` for formatting and linting
- **Imports:** Use absolute imports (`from hauba.core.engine import Engine`)

### File Organization
- One class per file for agents and major components
- Shared types in `types.py` within each module
- Constants in `constants.py` within each module
- No circular imports — use dependency injection

### Error Handling
- Custom exception classes in `hauba/exceptions.py`
- Never swallow exceptions silently
- Always log errors with context (task_id, agent_id, etc.)
- Use `Result` pattern for operations that can fail gracefully

### Git
- Conventional commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`
- One logical change per commit
- Tests must pass before commit

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python 3.11+ | Fastest to MVP, best LLM library ecosystem |
| CLI framework | Typer | Modern, type-hint based, auto-completion |
| Storage | SQLite (aiosqlite) | Zero setup, embedded, surprisingly fast |
| Embeddings | sqlite-vec or chromadb | Local-first, no external DB |
| LLM clients | litellm | Single interface for all providers |
| Event system | Python asyncio + custom EventEmitter | Simple, no external deps |
| Terminal UI | Rich + rich-click | Beautiful output, progress bars, tables |
| Web UI | FastAPI + WebSocket | Real-time, lightweight, async-native |
| HTTP client | httpx | Async, modern, type-safe |
| Testing | pytest + pytest-asyncio | Standard, reliable |
| Linting | ruff | Fast, comprehensive, replaces flake8+black+isort |
| Process isolation | subprocess + resource limits | No Docker required |

## Data Directory Structure

All state stored at `~/.hauba/`:

```
~/.hauba/
├── settings.json          # User config (LLM provider, API keys ref)
├── keys.json              # Encrypted API keys (AES-256-GCM)
├── hauba.db               # SQLite database (tasks, memory, events)
├── agents/                # Agent workspace files
│   └── {task_id}/
│       ├── understanding.md
│       ├── plan.md
│       ├── ledger.json    # TaskLedger
│       ├── todo.md        # Human-readable progress
│       └── workers/
│           └── {worker_id}/
├── memory/
│   ├── owner/profile.md   # Owner preferences
│   ├── knowledge/         # Learned solutions
│   └── context/           # Active context
├── skills/                # Installed skills
├── strategies/            # Installed strategies
├── logs/                  # System logs
└── backups/               # Daily snapshots
```

## TaskLedger — Zero Hallucination System

**This is Hauba's most important innovation. Never remove or simplify it.**

```python
# Three data structures that guarantee zero hallucination:
# 1. Bit-vector (uint8[]) — O(1) per-task state tracking
# 2. Hash-chain (SHA-256) — Artifact verification
# 3. WAL checkpoints — Crash-safe state persistence

# States: 0=NOT_STARTED, 1=IN_PROGRESS, 2=VERIFIED

# Five anti-hallucination gates:
# Gate 1: PRE-EXECUTION — Ledger must exist before work
# Gate 2: DEPENDENCY — All deps VERIFIED before task start
# Gate 3: COMPLETION — Hash output, verify on disk
# Gate 4: DELIVERY — Full ledger GateCheck at each level
# Gate 5: RECONCILIATION — Plan count vs ledger count
```

## Build Order

**Phase 0** (NOW): Project scaffolding, CLAUDE.md, README, pyproject.toml
**Phase 1** (Days 1-5): CLI + single agent + LLM integration + basic tools
**Phase 2** (Days 6-10): Multi-agent hierarchy + TaskLedger + DAG executor
**Phase 3** (Days 11-15): Computer use + browser agent + replay mode
**Phase 4** (Days 16-20): Voice mode + channels (Telegram, Discord, Web)
**Phase 5** (Days 21-25): Hauba Compose (hauba.yaml) + skill system
**Phase 6** (Days 26-30): Distribution (PyPI, Homebrew, Windows)

## Testing Strategy

- Unit tests for every module (`tests/unit/`)
- Integration tests for agent workflows (`tests/integration/`)
- E2E tests for CLI commands (`tests/e2e/`)
- Use `pytest` fixtures for common setup
- Mock LLM calls in unit tests (use recorded responses)
- Real LLM calls only in integration tests (mark with `@pytest.mark.integration`)

## Common Patterns

### Creating a new agent type
```python
from hauba.agents.base import BaseAgent

class MyAgent(BaseAgent):
    async def deliberate(self, task: Task) -> Plan:
        """Think before acting."""
        ...

    async def execute(self, plan: Plan) -> Result:
        """Execute the plan."""
        ...

    async def review(self, result: Result) -> ReviewResult:
        """Review the output."""
        ...
```

### Adding a new tool
```python
from hauba.tools.base import BaseTool

class MyTool(BaseTool):
    name = "my_tool"
    description = "What this tool does"

    async def execute(self, **kwargs) -> ToolResult:
        ...
```

### Adding a new skill
Create a `.md` file in `skills/core/`:
```markdown
# Skill: my-skill
## Capabilities
- What this skill enables
## When To Use
- Trigger conditions
## Approach
1. Step-by-step approach
## Constraints
- Limitations and safety rules
```

## What NOT to Do

- Do NOT add Go code until Phase 7
- Do NOT require Docker for basic functionality
- Do NOT add Redis or PostgreSQL dependencies
- Do NOT build the marketplace/economy before skills work
- Do NOT build Janta before Hauba Core is solid
- Do NOT skip TaskLedger gates — they are non-negotiable
- Do NOT use synchronous I/O for network or file operations
- Do NOT store API keys in plaintext
