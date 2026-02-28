# Hauba V3 — AI Workstation Architecture

> **One engine. Seventeen skills. Infinite capabilities.**
>
> Hauba is an AI workstation powered by the GitHub Copilot SDK.
> Build software, edit videos, process data, train models, generate documents, and more.

---

## Table of Contents

- [Part A: What Is Hauba V3](#part-a-what-is-hauba-v3)
- [Part B: Architecture Overview](#part-b-architecture-overview)
- [Part C: The Engine — Copilot SDK](#part-c-the-engine)
- [Part D: Skills — The Intelligence Layer](#part-d-skills)
- [Part E: TaskLedger — Audit Trail](#part-e-taskledger)
- [Part F: Tools & Capabilities](#part-f-tools--capabilities)
- [Part G: Channels & Interfaces](#part-g-channels--interfaces)
- [Part H: Data Directory](#part-h-data-directory)
- [Part I: Security](#part-i-security)

---

## Part A: What Is Hauba V3

### The One-Liner

**Hauba is an AI workstation that builds real software, edits videos, processes data, and automates workflows — powered by the GitHub Copilot SDK.**

```bash
pip install hauba
hauba init
hauba run "build me a SaaS dashboard with auth and Stripe billing"
hauba run "edit this video: trim first 10s, add subtitles, export as mp4"
hauba run "analyze sales.csv and create a visualization dashboard"
```

### What Changed in V3

| V2 (Agent Framework) | V3 (AI Workstation) |
|-----------------------|---------------------|
| Multi-agent hierarchy (Director → SubAgent → Worker) | Single CopilotEngine |
| Custom LLM routing via litellm | GitHub Copilot SDK (production-tested) |
| Strategy YAML playbooks + Skill .md files | Skills only (.md) — strategies merged in |
| DAG executor for complex tasks | Copilot SDK handles planning natively |
| 10 bundled skills (software only) | 17 bundled skills (software + video + data + ML + docs + automation) |
| Custom agentic loops | Copilot SDK agent runtime |

### Design Principles

1. **Single Engine** — One execution path (CopilotEngine). No fallbacks, no legacy modes.
2. **Skills as Intelligence** — Domain knowledge lives in `.md` files. Human-readable, LLM-consumable.
3. **BYOK (Bring Your Own Key)** — Users provide their API key. Hauba owner pays nothing.
4. **Python-First** — Every tool and capability runs through Python. Install packages as needed.
5. **Zero-Hallucination Audit** — TaskLedger records every output with SHA-256 hash verification.
6. **Offline-Capable** — Works with Ollama local models. No internet required.

---

## Part B: Architecture Overview

```
User Request
    │
    ├── CLI (hauba run "...")
    ├── API (POST /api/v1/tasks)
    ├── Web Dashboard (hauba serve)
    ├── Discord / Telegram
    └── Voice (hauba voice)
         │
         ▼
    ┌─────────────────────────────────────────┐
    │           Hauba Core                     │
    │                                          │
    │   Skill Matcher ─── Matched Skills       │
    │        │                  │               │
    │        ▼                  ▼               │
    │   CopilotEngine                          │
    │   ├── System Prompt (AI Workstation)     │
    │   ├── Skill Context (top-3 matched)      │
    │   ├── skill_directories (all .md files)  │
    │   └── BYOK Provider Config               │
    │        │                                  │
    └────────│──────────────────────────────────┘
             │
             ▼
    ┌─────────────────────────────────────────┐
    │       GitHub Copilot SDK                 │
    │                                          │
    │   Agent Runtime                          │
    │   ├── Planning & Reasoning               │
    │   ├── Tool Execution                     │
    │   │   ├── bash (shell commands)          │
    │   │   ├── files (read/write/edit)        │
    │   │   └── git (version control)          │
    │   ├── Infinite Sessions (compaction)     │
    │   └── Streaming Events                   │
    │                                          │
    └─────────────────────────────────────────┘
             │
             ▼
    Workspace Directory (files, code, outputs)
```

### Package Structure

```
src/hauba/
├── cli.py               # Typer CLI entry point
├── engine/              # CopilotEngine (THE brain)
│   ├── copilot_engine.py
│   └── types.py
├── core/                # Config, events, types, constants
├── skills/              # SkillLoader, SkillMatcher
├── bundled_skills/      # 17 built-in .md skills
├── tools/               # Bash, Files, Git, Browser, Screen, Web
├── ledger/              # TaskLedger (audit trail)
├── memory/              # SQLite store
├── ui/                  # Terminal (Rich), Web (FastAPI), Replay
├── channels/            # Discord, Telegram, Voice
├── compose/             # hauba.yaml declarative teams
├── api/                 # REST API server
├── security.py          # Encryption & sandboxing
└── exceptions.py        # Custom exceptions
```

---

## Part C: The Engine

### CopilotEngine

The single execution brain. Wraps the GitHub Copilot SDK to provide:

- **BYOK**: Anthropic, OpenAI, Azure, Ollama — user provides API key
- **Agent Runtime**: Planning, tool invocation, file edits, git operations
- **Skill Injection**: Matched skills appended to system prompt + skill_directories
- **Infinite Sessions**: Automatic context compaction for long tasks
- **Streaming Events**: Real-time UI updates
- **Session Persistence**: Resume interrupted tasks with `--continue`

### Execution Flow

```python
# 1. User submits task
hauba run "build a React dashboard with auth"

# 2. Skill Matcher finds top-3 relevant skills
matched = ["full-stack-engineering", "code-generation", "security-hardening"]

# 3. CopilotEngine builds session config
config = {
    "model": "claude-sonnet-4-5",
    "provider": {"type": "anthropic", "api_key": "sk-ant-..."},
    "system_message": {"mode": "append", "content": hauba_system_prompt + skill_context},
    "skill_directories": ["~/.hauba/skills/", "bundled_skills/"],
    "working_directory": "./hauba-output/",
    "infinite_sessions": {"enabled": True},
}

# 4. Copilot SDK executes (planning, tools, file creation, git)
result = await engine.execute(task)

# 5. TaskLedger records output hash for audit
ledger.record(task_hash, output_hash)
```

### System Prompt

The CopilotEngine injects a comprehensive system prompt that transforms the Copilot SDK agent into a professional AI workstation. Key sections:

1. **Identity**: "You are Hauba AI Workstation — a professional AI that builds real software, edits videos, processes data, trains models, and automates workflows."
2. **Execution Protocol**: UNDERSTAND → PLAN → IMPLEMENT → VERIFY → DELIVER
3. **Tool Awareness**: Install Python packages as needed (`pip install moviepy pandas scikit-learn`)
4. **Skill Reference**: Check matched skills for domain-specific guidance
5. **Self-Correction**: Max 3 retries per step, analyze errors before retrying

---

## Part D: Skills

### What Are Skills?

Skills are `.md` files that provide domain-specific intelligence to the Copilot SDK agent. They are human-readable, LLM-consumable, and pluggable.

### Bundled Skills (17)

| # | Skill | Domain |
|---|-------|--------|
| 1 | code-generation | Writing production code |
| 2 | api-design-and-integration | REST APIs, GraphQL, integrations |
| 3 | data-engineering | ETL, pipelines, databases |
| 4 | debugging-and-repair | Error diagnosis, bug fixing |
| 5 | devops-and-deployment | Docker, CI/CD, infrastructure |
| 6 | full-stack-engineering | End-to-end web applications |
| 7 | refactoring-and-migration | Code modernization |
| 8 | research-and-analysis | Knowledge gathering, synthesis |
| 9 | security-hardening | OWASP, encryption, audit |
| 10 | testing-and-quality | Tests, coverage, CI |
| 11 | video-editing | MoviePy video editing, effects, subtitles |
| 12 | image-generation | PIL/Pillow, AI image gen, thumbnails |
| 13 | data-processing | pandas, visualization, statistics |
| 14 | web-scraping | BeautifulSoup, Playwright, extraction |
| 15 | automation-and-scripting | System automation, batch processing |
| 16 | document-generation | PDF, presentations, spreadsheets |
| 17 | machine-learning | scikit-learn, training, evaluation |

### Skill Format

```markdown
# Skill: skill-name

## Capabilities
- What this skill enables

## When To Use
- Trigger conditions (keywords, patterns)

## Approach
1. Step-by-step methodology

## Constraints
- Safety rules, limitations

## Tools Required
- Python packages needed (pip install ...)

## Error Recovery
- Common failures and fixes

## Playbook: {Domain Workflow} (optional)
### Milestone 1: ...
### Milestone 2: ...
```

### How Skills Are Used

1. **Skill Matcher** (TF-IDF) matches user task to top-3 skills
2. Matched skill `Approach` + `Constraints` are injected into system prompt
3. `skill_directories` config gives the SDK access to ALL skill files
4. Agent can reference any skill during execution for guidance

### Custom Skills

Users can create custom skills at `~/.hauba/skills/my-skill.md` and they are automatically loaded.

---

## Part E: TaskLedger

The TaskLedger provides zero-hallucination audit trailing:

- **Bit-vector**: O(1) per-task state (NOT_STARTED → IN_PROGRESS → VERIFIED)
- **Hash-chain**: SHA-256 verification of all outputs
- **WAL**: Write-ahead log for crash-safe persistence
- **5 Gates**: Pre-execution, dependency, completion, delivery, reconciliation

In V3, the TaskLedger operates at the engine level — recording task inputs, outputs, and hashes for every `CopilotEngine.execute()` call. This provides an audit trail without the multi-level complexity of V2.

---

## Part F: Tools & Capabilities

### Built-in (via Copilot SDK)
- **bash**: Execute shell commands
- **files**: Read, write, edit files
- **git**: Version control operations

### Hauba Tools (available to agent)
- **BashTool**: Enhanced shell with timeout, output limiting, Git Bash on Windows
- **FileTool**: File operations with workspace isolation
- **GitTool**: Git operations wrapper
- **BrowserTool**: Playwright-based web browsing (stealth mode)
- **ScreenTool**: PyAutoGUI desktop automation
- **WebTool**: HTTP client (httpx)

### Python Package Ecosystem
The agent can `pip install` any Python package to extend capabilities:
- **moviepy** for video editing
- **pandas/polars** for data processing
- **scikit-learn** for machine learning
- **Pillow** for image manipulation
- **reportlab/weasyprint** for PDF generation
- **beautifulsoup4** for web scraping
- And anything else on PyPI

---

## Part G: Channels & Interfaces

| Channel | Access Method |
|---------|-------------|
| CLI | `hauba run "task"` |
| Web Dashboard | `hauba serve` (FastAPI + WebSocket) |
| REST API | `hauba api` (BYOK, POST /api/v1/tasks) |
| Discord | Bot integration |
| Telegram | Bot integration |
| Voice | `hauba voice` (Whisper STT + edge-tts) |

---

## Part H: Data Directory

```
~/.hauba/
├── settings.json          # User config (provider, API key, model)
├── last_session.json      # Last Copilot session ID (for --continue)
├── hauba.db               # SQLite (memory, task history, events)
├── skills/                # User-installed custom skills
├── logs/                  # System logs
└── backups/               # Daily snapshots
```

---

## Part I: Security

- **BYOK**: API keys stored locally, never sent to Hauba servers
- **Workspace isolation**: Each task operates in its own directory
- **No Docker required**: Subprocess + resource limits for isolation
- **Encryption**: AES-256-GCM for stored API keys
- **Permission handling**: Copilot SDK auto-approves tool usage within workspace

---

## Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Language | Python 3.11+ | Best LLM ecosystem |
| CLI | Typer | Type-hint based, auto-complete |
| Engine | GitHub Copilot SDK | Production-tested agent runtime |
| Storage | SQLite (aiosqlite) | Zero setup, embedded |
| Terminal UI | Rich | Beautiful output |
| Web UI | FastAPI + WebSocket | Real-time, async |
| HTTP | httpx | Async, modern |
| Testing | pytest + pytest-asyncio | Standard, reliable |
| Linting | ruff | Fast, comprehensive |
