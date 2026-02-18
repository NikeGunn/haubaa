<p align="center">
  <h1 align="center">Hauba</h1>
  <p align="center"><strong>Your AI Engineering Team — In One Command</strong></p>
  <p align="center">
    <a href="https://github.com/NikeGunn/haubaa/actions"><img src="https://github.com/NikeGunn/haubaa/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
    <a href="https://pypi.org/project/hauba/"><img src="https://img.shields.io/pypi/v/hauba.svg" alt="PyPI"></a>
    <a href="https://pypi.org/project/hauba/"><img src="https://img.shields.io/pypi/pyversions/hauba.svg" alt="Python"></a>
    <a href="https://github.com/NikeGunn/haubaa/blob/main/LICENSE"><img src="https://img.shields.io/github/license/NikeGunn/haubaa.svg" alt="License"></a>
  </p>
  <p align="center">
    <a href="#install">Install</a> &bull;
    <a href="#quickstart">Quickstart</a> &bull;
    <a href="#features">Features</a> &bull;
    <a href="#architecture">Architecture</a> &bull;
    <a href="CONTRIBUTING.md">Contributing</a>
  </p>
</p>

---

Hauba is an open-source AI agent framework that orchestrates a full engineering team — architect, backend, frontend, DevOps — controlled by a Director agent that **thinks before it acts**.

One command. Zero external dependencies. Works offline with Ollama.

```bash
pip install hauba
hauba init
hauba run "build me a landing page with modern design"
```

## Why Hauba?

| Feature | Hauba | Others |
|---------|-------|--------|
| Multi-agent collaboration | Director → SubAgent → Worker hierarchy | Single agent or basic chains |
| Zero-hallucination tracking | TaskLedger with SHA-256 hash verification | Trust-based, no verification |
| Works offline | First-class Ollama support | Requires cloud API |
| Declarative teams | `hauba.yaml` (like docker-compose for AI) | Code-only configuration |
| Browser automation | Persistent sessions, stealth mode, crash recovery | Basic or none |
| Voice mode | Talk to your AI team | Text-only |
| Replay mode | Watch & share agent sessions | No replay |
| Single install | `pip install hauba` — no Docker, Redis, or Postgres | Complex setup |

## Install

```bash
# From PyPI (recommended)
pip install hauba

# From source
git clone https://github.com/NikeGunn/haubaa.git
cd haubaa
pip install -e ".[dev]"

# Optional extras
pip install hauba[computer-use]   # Browser + screen control
pip install hauba[voice]          # Voice mode (Whisper + TTS)
pip install hauba[web]            # Web dashboard
pip install hauba[all]            # Everything
```

**Requirements:** Python 3.11+ — nothing else.

## Quickstart

### 1. Initialize

```bash
hauba init
```

Pick your LLM provider (Anthropic, OpenAI, Ollama, DeepSeek) and enter your API key.

### 2. Run a task

```bash
hauba run "create a REST API with user authentication"
```

The Director agent will:
1. **Deliberate** — understand your request and assess complexity
2. **Plan** — decompose into steps with a dependency DAG
3. **Execute** — use tools (bash, files, git, browser) to build it
4. **Verify** — TaskLedger ensures every step completed with hash verification
5. **Deliver** — only after all 5 verification gates pass

### 3. Check system health

```bash
hauba doctor
```

## Hauba Compose

Define your AI team declaratively:

```yaml
# hauba.yaml
team: "my-saas"
model: "claude-sonnet-4-5-20250929"

agents:
  architect:
    role: "Senior Software Architect"
    skills: [system-design, database-design, api-design]

  backend:
    role: "Backend Engineer"
    skills: [fastapi, postgresql, auth]
    depends_on: [architect]

  frontend:
    role: "Frontend Engineer"
    skills: [nextjs, tailwind, react]
    depends_on: [architect]

  devops:
    role: "DevOps Engineer"
    skills: [docker, ci-cd, monitoring]
    depends_on: [backend, frontend]
```

```bash
hauba compose up "build a SaaS dashboard with auth and billing"
```

## Features

### Multi-Agent Hierarchy
- **Director** — receives your task, deliberates, creates a project plan
- **SubAgent** — manages a milestone, coordinates workers
- **Worker** — executes specific tasks with retry logic
- **CoWorker** — ephemeral helpers for sub-tasks

### TaskLedger (Zero-Hallucination System)
Every task is tracked with a bit-vector and SHA-256 hash chain. Five verification gates ensure nothing is skipped or faked:
1. **Pre-execution** — Ledger must exist before work begins
2. **Dependency** — All dependencies verified before task starts
3. **Completion** — Output hashed and verified on disk
4. **Delivery** — Full ledger gate check at each level
5. **Reconciliation** — Plan count matches ledger count

### Browser Automation (Persistent Sessions)
```bash
hauba run "scrape product data from the competitor website"
```
- Persistent browser context — sessions survive crashes
- Stealth mode — anti-bot detection evasion
- Auto-retry with crash recovery

### Voice Mode
```bash
hauba voice
```
Talk to your AI team. Uses Whisper (local) for speech-to-text and edge-tts for responses. Works fully offline with Ollama.

### Replay Mode
```bash
hauba replay <task_id>
hauba replay <task_id> --speed 5
```
Every agent action is recorded and replayable with speed control.

### Skills & Strategies
10 built-in skills and 6 strategies ship with Hauba:
```bash
hauba skill list                    # See all available skills
hauba skill show code-generation    # View a skill's details
hauba skill install ./my-skill.md   # Install a custom skill
```

### Web Dashboard
```bash
hauba serve
```
Real-time web dashboard with WebSocket event streaming at `http://localhost:8420`.

### Channels
```bash
hauba voice      # Voice conversation
hauba serve      # Web dashboard
```
Plus Telegram and Discord bot integrations.

## CLI Reference

```
hauba init                          # Interactive setup wizard
hauba run "task description"        # Execute a task
hauba status                        # Show config and status
hauba doctor                        # Diagnose setup issues
hauba logs                          # View recent logs
hauba config <key> [value]          # Get/set configuration

hauba compose up "task" [-f file]   # Run with agent team
hauba compose validate              # Check hauba.yaml syntax

hauba skill list                    # List all skills
hauba skill show <name>             # View skill details
hauba skill install <path>          # Install a skill
hauba skill create <name>           # Scaffold new skill

hauba voice                         # Voice conversation mode
hauba serve [--port 8420]           # Start web dashboard
hauba replay <task_id> [--speed 2]  # Replay a session
```

## Configuration

```bash
# Anthropic (default)
hauba config llm.provider anthropic
hauba config llm.api_key sk-ant-...

# OpenAI
hauba config llm.provider openai
hauba config llm.api_key sk-...

# Ollama (offline, free)
hauba config llm.provider ollama
hauba config llm.model llama3.2
```

## Architecture

```
Director (1 per task)
├── SubAgent (per milestone)
│   ├── Worker (per task)
│   │   └── CoWorker (ephemeral)
│   └── Worker
└── SubAgent
    └── Worker
```

**Stack:** Python 3.11+ | asyncio | SQLite | litellm | Typer | Rich | Pydantic v2

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

```bash
git clone https://github.com/NikeGunn/haubaa.git
cd haubaa
pip install -e ".[dev]"
pytest tests/ -v
```

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Hauba doesn't guess. Hauba verifies.</strong>
</p>
