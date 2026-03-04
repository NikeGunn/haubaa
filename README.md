<div align="center">

# Hauba

### The AI Workstation That Builds While You Sleep

**One command. Full engineering team. Your API key. Your machine.**

[![CI](https://github.com/NikeGunn/haubaa/actions/workflows/ci.yml/badge.svg)](https://github.com/NikeGunn/haubaa/actions)
[![PyPI](https://img.shields.io/pypi/v/hauba.svg?color=blue)](https://pypi.org/project/hauba/)
[![Python](https://img.shields.io/pypi/pyversions/hauba.svg)](https://pypi.org/project/hauba/)
[![License](https://img.shields.io/github/license/NikeGunn/haubaa.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-432%20passed-brightgreen)]()
[![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macos%20%7C%20windows-lightgrey)]()

<br>

[Get Started](#-get-started) · [See It In Action](#-see-it-in-action) · [Features](#-features) · [Architecture](#-architecture) · [Docs](#-full-cli-reference)

<br>

```
pip install hauba && hauba init && hauba run "build me a SaaS"
```

</div>

<br>

---

<br>

## What is Hauba?

Hauba is a **production-grade AI workstation** that turns natural language into real software, data pipelines, ML models, video edits, and more.

It's not a chatbot. It's not a wrapper. It's an **autonomous engineering agent** powered by the GitHub Copilot SDK — with a zero-hallucination verification layer, 17 domain skills, multi-channel access, and a 24/7 daemon that builds while you're away.

**The key insight:** Your AI agent should run on **your machine**, with **your API key**, at **your cost**. The server is just a message queue. We call this **BYOK** — Bring Your Own Key.

```
You (WhatsApp) → "build me an API with auth"
                        ↓
              Server queues the task
                        ↓
        Your machine picks it up automatically
                        ↓
         Builds it with YOUR Claude/GPT key
                        ↓
            Notifies you when it's done ✓
```

<br>

---

<br>

## See It In Action

<table>
<tr>
<td width="50%" align="center">

**Run a task**

<img src="assets/hauba-run.gif" alt="hauba run demo" width="100%">

`hauba run "build a REST API with auth"`<br>
<sub>Think → Plan → Execute → Verify → Deliver</sub>

</td>
<td width="50%" align="center">

**Setup in 30 seconds**

<img src="assets/hauba-init.gif" alt="hauba init demo" width="100%">

`hauba init`<br>
<sub>Pick provider → Enter key → Ready</sub>

</td>
</tr>
<tr>
<td width="50%" align="center">

**24/7 Daemon Agent**

<img src="assets/hauba-agent.gif" alt="hauba agent demo" width="100%">

`hauba agent --server https://hauba.tech`<br>
<sub>Auto-polls → Claims → Builds → Notifies</sub>

</td>
<td width="50%" align="center">

**WhatsApp Bot**

<img src="assets/hauba-whatsapp.gif" alt="whatsapp bot demo" width="100%">

<sub>Message your bot → Task queued → Built locally → Results on phone</sub>

</td>
</tr>
<tr>
<td width="50%" align="center">

**Declarative AI Teams**

<img src="assets/hauba-compose.gif" alt="hauba compose demo" width="100%">

`hauba compose up "build a SaaS"`<br>
<sub>Architect → Backend ∥ Frontend → DevOps</sub>

</td>
<td width="50%" align="center">

**Queue + Poll Architecture**

<img src="assets/hauba-architecture.gif" alt="architecture demo" width="100%">

<sub>Your machine ↔ Server relay ↔ Channels</sub>

</td>
</tr>
</table>

<br>

---

<br>

## Get Started

### Install

```bash
pip install hauba
```

<details>
<summary><strong>More install options</strong></summary>

```bash
# One-liner (Linux/macOS)
curl -fsSL https://hauba.tech/install.sh | sh

# One-liner (Windows PowerShell)
irm https://hauba.tech/install.ps1 | iex

# From source
git clone https://github.com/NikeGunn/haubaa.git && cd haubaa
pip install -e ".[dev]"

# With extras
pip install hauba[all]            # Everything
pip install hauba[computer-use]   # Browser + screen control
pip install hauba[voice]          # Voice mode (Whisper + TTS)
pip install hauba[web]            # Web dashboard
pip install hauba[channels]       # WhatsApp, Telegram, Discord
pip install hauba[services]       # Email (SMTP)
```

</details>

**Requirements:** Python 3.11+ — nothing else.

### Initialize

```bash
hauba init
```

Choose your LLM provider, enter your API key, and you're ready.

### Run your first task

```bash
hauba run "create a REST API with JWT auth, database models, and full test suite"
```

The engine **thinks before it acts** — plans the approach, shows you for approval, executes with real tools (bash, files, git, web), verifies everything passes, then delivers.

The session stays open for multi-turn follow-ups:

```
> "add rate limiting and CORS"
> "write a Dockerfile for production"
> "deploy to Railway"
```

<br>

---

<br>

## Features

### BYOK — Bring Your Own Key

Your API key never leaves your machine. The server is a stateless relay. You control cost, model, and provider.

| Provider | Models | Offline |
|----------|--------|---------|
| **Anthropic** | Claude Opus 4.6, Sonnet 4.5, Haiku 4.5 | No |
| **OpenAI** | GPT-4o, o3 | No |
| **Azure** | Any Azure OpenAI deployment | No |
| **Ollama** | Qwen 2.5 Coder 32B, Llama 3, any local model | **Yes** |

```bash
hauba config llm.provider anthropic
hauba config llm.model claude-sonnet-4-5-20250929
```

### 24/7 Daemon Agent

```bash
hauba agent --server https://hauba.tech
```

Your personal AI engineer that never sleeps:

- **Polls** the server every 10s for tasks from WhatsApp/Telegram/Discord
- **Claims and builds** locally with your API key
- **Reports progress** every 15s — you see live updates on your phone
- **Cost tracking** — alerts when spend exceeds threshold (default $5)
- **Auto-retry** — up to 3 attempts on failures
- **Remote cancel** — cancel tasks from WhatsApp mid-execution

### WhatsApp / Telegram / Discord

Message your Hauba bot from anywhere:

| Command | What It Does |
|---------|-------------|
| *"build me a dashboard"* | Queues a build task for your daemon |
| `/tasks` | List all tasks with status |
| `/cancel <id>` | Cancel a running task |
| `/retry <id>` | Retry a failed task |
| `/web <url>` | Fetch and summarize any URL |
| `/email <to> <subj> \| <body>` | Send an email |
| `/reply <msg\|off>` | Set/disable auto-reply |
| `/usage` | Cost and usage stats |
| `/status` | Quick health check |
| `/plugins` | List active plugins |
| `/feedback <msg>` | Submit feedback |
| `/new` | Clear session |

**Smart routing:** "build me an API" goes to the task queue. "what's the weather?" gets an instant chat response. Zero false positives via word-boundary regex matching.

```bash
hauba setup whatsapp   # Interactive Twilio setup wizard
```

### Hauba Compose — Declarative AI Teams

Like `docker-compose`, but for AI agents:

```yaml
# hauba.yaml
team: "my-saas"
model: "claude-sonnet-4-5-20250929"

agents:
  architect:
    role: "Senior Software Architect"
    skills: [system-design, api-design]

  backend:
    role: "Backend Engineer"
    skills: [fastapi, auth, database]
    depends_on: [architect]

  frontend:
    role: "Frontend Engineer"
    skills: [nextjs, tailwind, react]
    depends_on: [architect]

  devops:
    role: "DevOps Engineer"
    skills: [docker, ci-cd, monitoring]
    depends_on: [backend, frontend]

output: "./output"
```

```bash
hauba compose up "build a SaaS with auth and Stripe billing"
```

**Parallel by default.** Backend and frontend run simultaneously. DevOps waits for both. Topological DAG execution with circular dependency detection.

### 17 Built-in Skills

Skills are `.md` files — human-readable, composable, installable. The SkillMatcher uses TF-IDF scoring to inject the top-3 relevant skills into every task.

<details>
<summary><strong>View all 17 skills</strong></summary>

| Skill | Domain |
|-------|--------|
| `full-stack-engineering` | Complete SaaS builds (6-milestone playbook) |
| `api-design-and-integration` | REST/GraphQL API design |
| `code-generation` | Multi-language code generation |
| `data-engineering` | Pipelines, ETL, warehousing |
| `data-processing` | Cleaning, transformation, analysis |
| `debugging-and-repair` | Bug diagnosis and fixes |
| `devops-and-deployment` | Docker, CI/CD, infrastructure |
| `document-generation` | Reports, docs, technical writing |
| `image-generation` | Image creation and processing |
| `machine-learning` | Model training and deployment |
| `refactoring-and-migration` | Code modernization |
| `research-and-analysis` | Research and analysis tasks |
| `security-hardening` | Security audits and hardening |
| `testing-and-quality` | Test suites and QA |
| `video-editing` | Video trimming, effects, subtitles |
| `web-scraping` | Web data extraction |
| `automation-and-scripting` | Task automation |

</details>

```bash
hauba skill list                    # See all skills
hauba skill show full-stack         # View skill details
hauba skill install ./my-skill.md   # Add custom skill
hauba skill create my-new-skill     # Scaffold a new one
```

### TaskLedger — Zero-Hallucination Guarantee

Every task goes through **5 verification gates** backed by a bit-vector state tracker, SHA-256 hash chain, and Write-Ahead Log:

| Gate | What It Checks |
|------|---------------|
| **Pre-execution** | Ledger exists before any work begins |
| **Dependency** | All upstream tasks verified before start |
| **Completion** | Output hashed: `SHA256(prev + task_id + artifact)` |
| **Delivery** | Full gate check passes at every level |
| **Reconciliation** | Plan count === ledger count |

If the agent says it's done, it's done. Cryptographically verified.

### Plugin System

```python
from hauba.plugins.base import BasePlugin

class MyPlugin(BasePlugin):
    name = "my-plugin"

    async def on_message(self, channel, sender, text):
        if "urgent" in text.lower():
            return "Prioritizing your task!"
        return None

    async def on_task_complete(self, task_id, output):
        ...  # Custom logic

def create_plugin():
    return MyPlugin()
```

```bash
hauba plugins install ./my_plugin.py
hauba plugins list
hauba plugins remove my-plugin
```

**7 lifecycle hooks:** `on_load` · `on_unload` · `on_message` · `on_task_complete` · `on_task_queued` · `on_startup` · `on_shutdown`

### And More

| Capability | Command |
|-----------|---------|
| Voice conversations | `hauba voice` |
| Real-time web dashboard | `hauba serve` |
| REST API (BYOK, SSE) | `hauba api` |
| Send emails | `hauba email to@co.com "Subject" "Body"` |
| Fetch any URL | `hauba web https://example.com` |
| Auto-reply (WhatsApp) | `hauba reply "Out of office"` |
| Replay agent sessions | `hauba replay <id> --speed 5` |
| Browser automation | `pip install hauba[computer-use]` |
| System diagnostics | `hauba doctor` |

<br>

---

<br>

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CHANNELS                                  │
│   WhatsApp  ·  Telegram  ·  Discord  ·  Voice  ·  Web UI        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │   Server    │  hauba.tech (Railway)
                    │  ─────────  │
                    │  Task Queue │  submit / poll / claim
                    │  Webhooks   │  WhatsApp, Telegram, Discord
                    │  Chat (LLM) │  lightweight server-side
                    └──────┬──────┘
                           │  poll every 10s
                    ┌──────▼──────┐
                    │   Daemon    │  hauba agent (your machine)
                    │  ─────────  │
                    │  Claims     │  auto-claim queued tasks
                    │  Executes   │  CopilotEngine (YOUR key)
                    │  Reports    │  progress + completion
                    │  Cost Track │  per-task cost estimates
                    └──────┬──────┘
                           │
              ┌────────────▼────────────┐
              │     CopilotEngine       │  GitHub Copilot SDK
              │  ────────────────────   │
              │  SkillMatcher (TF-IDF)  │  17 bundled skills
              │  TaskLedger (SHA-256)   │  zero-hallucination
              │  Tools:                 │
              │    bash · files · git   │
              │    web  · browser       │
              │    screen · fetch       │
              └─────────────────────────┘
```

### Source Layout

```
src/hauba/
├── cli.py                  # 20+ commands (Typer)
├── engine/copilot_engine.py  # Core engine (Copilot SDK)
├── daemon/
│   ├── agent.py            # 24/7 polling daemon
│   └── queue.py            # Task queue (TTL, retry, cancel)
├── channels/
│   ├── whatsapp_webhook.py # WhatsApp bot (12 commands)
│   ├── telegram.py         # Telegram integration
│   ├── discord.py          # Discord integration
│   └── voice.py            # Whisper STT + edge-tts
├── skills/
│   ├── loader.py           # .md skill parser
│   └── matcher.py          # TF-IDF skill matching
├── plugins/                # Plugin system (base, loader, registry)
├── ledger/
│   ├── tracker.py          # Bit-vector + SHA-256 hash chain
│   ├── wal.py              # Write-Ahead Log
│   └── gates.py            # 5 anti-hallucination gates
├── memory/store.py         # SQLite (aiosqlite) + TTL
├── services/
│   ├── email.py            # SMTP email
│   └── reply_assistant.py  # Auto-reply engine
├── tools/                  # bash, files, git, fetch, browser, screen
├── compose/                # hauba.yaml parser + DAG runner
├── core/                   # Config, constants, events
├── ui/                     # Rich terminal + FastAPI web
└── bundled_skills/         # 17 .md skill files
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.11+ · asyncio |
| AI Engine | GitHub Copilot SDK |
| CLI | Typer · Rich |
| Storage | SQLite (aiosqlite) |
| Validation | Pydantic v2 |
| HTTP | httpx (async) |
| Logging | structlog (JSON) |
| Web | FastAPI · WebSocket |
| Channels | Twilio · python-telegram-bot · discord.py |
| Voice | Whisper · edge-tts |
| Browser | Playwright |
| Linting | ruff · pyright |
| Testing | pytest · pytest-asyncio |

<br>

---

<br>

## Full CLI Reference

<details>
<summary><strong>Click to expand all 20+ commands</strong></summary>

```
CORE
  hauba init                              Setup wizard
  hauba run "task" [--no-interactive]     Execute a task
  hauba status                            Show config + last task
  hauba doctor                            System diagnostics
  hauba logs [--lines 50]                 View logs
  hauba config <key> [value]              Get/set config

DAEMON & TASKS
  hauba agent [--server URL]              Start 24/7 daemon
  hauba tasks [--server URL]              List tasks
  hauba cancel <task_id>                  Cancel a task
  hauba retry <task_id>                   Retry failed task
  hauba usage                             Cost summary

COMPOSE
  hauba compose up "task" [-f file]       Run agent team
  hauba compose validate [-f file]        Validate hauba.yaml

SKILLS
  hauba skill list                        List skills
  hauba skill show <name>                 View skill
  hauba skill install <path>              Install skill
  hauba skill create <name>               Scaffold skill

PLUGINS
  hauba plugins list                      List plugins
  hauba plugins install <path.py>         Install plugin
  hauba plugins remove <name>             Remove plugin

CHANNELS & SERVICES
  hauba setup whatsapp                    WhatsApp setup
  hauba email <to> <subj> [body]          Send email
  hauba web <url>                         Fetch URL
  hauba reply <message|off>               Auto-reply
  hauba feedback <message>                Send feedback

UI
  hauba voice                             Voice mode
  hauba serve [--port 8420]               Web dashboard
  hauba api [--port 8080]                 REST API
  hauba replay <id> [--speed 2]           Replay session
```

</details>

<br>

---

<br>

## Deployment

The server runs on [Railway](https://railway.app) at **hauba.tech**.

<details>
<summary><strong>Server environment variables</strong></summary>

```bash
# Twilio (WhatsApp)
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Server LLM (lightweight chat only — NOT for builds)
HAUBA_LLM_API_KEY=...
HAUBA_LLM_PROVIDER=anthropic
HAUBA_LLM_MODEL=claude-haiku-4-5-20251001

# Email (optional)
HAUBA_SMTP_HOST=smtp.gmail.com
HAUBA_SMTP_PORT=587
HAUBA_SMTP_USER=...
HAUBA_SMTP_PASS=...
HAUBA_EMAIL_FROM=hauba@example.com
```

</details>

The server handles webhooks, task queuing, and chat. **All build tasks execute on the user's machine.** Server owner cost: near zero.

<br>

---

<br>

## Testing

```bash
pytest tests/ -v                    # 432 tests
pytest tests/ --cov=hauba           # With coverage
pytest tests/unit/daemon/ -v        # Specific suite
```

| Matrix | Status |
|--------|--------|
| Ubuntu + macOS + Windows | All green |
| Python 3.11 · 3.12 · 3.13 | All green |
| ruff check + format | Passing |
| pyright type checking | Passing |

<br>

---

<br>

## Contributing

```bash
git clone https://github.com/NikeGunn/haubaa.git
cd haubaa
pip install -e ".[dev]"
pytest tests/ -v
ruff check src/
```

Conventional commits: `feat:` · `fix:` · `refactor:` · `test:` · `docs:`

See [CONTRIBUTING.md](CONTRIBUTING.md) for full guidelines.

<br>

---

<br>

<div align="center">

## License

MIT — see [LICENSE](LICENSE)

<br>

---

<br>

**Your key. Your machine. Your AI workstation.**

[Website](https://hauba.tech) · [PyPI](https://pypi.org/project/hauba/) · [Issues](https://github.com/NikeGunn/haubaa/issues) · [Releases](https://github.com/NikeGunn/haubaa/releases)

<br>

<sub>Built with the GitHub Copilot SDK · Verified by TaskLedger · Powered by your API key</sub>

</div>
