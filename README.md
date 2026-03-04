<div align="center">

<br>

# `hauba`

<br>

### Stop hiring engineers. Start shipping products.

An AI engineering company in your terminal. Not a chatbot.

<br>

[![CI](https://github.com/NikeGunn/haubaa/actions/workflows/ci.yml/badge.svg)](https://github.com/NikeGunn/haubaa/actions)
[![PyPI](https://img.shields.io/pypi/v/hauba.svg?color=6C5CE7&style=flat-square)](https://pypi.org/project/hauba/)
[![Python](https://img.shields.io/pypi/pyversions/hauba.svg?style=flat-square)](https://pypi.org/project/hauba/)
[![License](https://img.shields.io/github/license/NikeGunn/haubaa.svg?style=flat-square)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-432%20passed-4caf50?style=flat-square)]()
[![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macos%20%7C%20windows-6C5CE7?style=flat-square)]()

<br>

**Your competitors are hiring for 6 months. You ship today.**

<br>

```
pip install hauba
```

<br>

[See It Work](#-see-it-work) &nbsp;&nbsp; [Get Started](#-get-started) &nbsp;&nbsp; [Why Hauba](#-why-hauba) &nbsp;&nbsp; [Features](#-core-capabilities) &nbsp;&nbsp; [Architecture](#-architecture)

<br>

</div>

---

<br>

One command deploys an AI engineering team that plans, codes, tests, debugs, and delivers — while you sleep. Powered by the same Copilot SDK backbone used by GitHub. Not a wrapper. The real thing.

Your API key. Your machine. Zero platform cost. **We call this BYOK.**

```bash
hauba init                                    # 30-second setup
hauba run "build a SaaS with auth and billing"  # ship it
```

<br>

---

<br>

<div align="center">

## See It Work

</div>

<br>

<table>
<tr>
<td width="50%" align="center">
<br>

**Ship a product**

<img src="assets/hauba-run.gif" alt="hauba run" width="100%">

```
hauba run "build a REST API with auth"
```

<sub>Think &rarr; Plan &rarr; Execute &rarr; Verify &rarr; Deliver</sub>
<br><br>
</td>
<td width="50%" align="center">
<br>

**30-second setup**

<img src="assets/hauba-init.gif" alt="hauba init" width="100%">

```
hauba init
```

<sub>Pick provider &rarr; Paste key &rarr; Ship</sub>
<br><br>
</td>
</tr>
<tr>
<td width="50%" align="center">
<br>

**24/7 autonomous agent**

<img src="assets/hauba-agent.gif" alt="hauba agent" width="100%">

```
hauba agent --server https://hauba.tech
```

<sub>Polls &rarr; Claims &rarr; Builds &rarr; Notifies you on phone</sub>
<br><br>
</td>
<td width="50%" align="center">
<br>

**Command from WhatsApp**

<img src="assets/hauba-whatsapp.gif" alt="whatsapp" width="100%">

<sub>Text your bot &rarr; Task queued &rarr; Built on your machine &rarr; Done</sub>
<br><br>
</td>
</tr>
<tr>
<td width="50%" align="center">
<br>

**Compose AI teams**

<img src="assets/hauba-compose.gif" alt="hauba compose" width="100%">

```
hauba compose up "build a SaaS"
```

<sub>Architect &rarr; Backend &#8741; Frontend &rarr; DevOps</sub>
<br><br>
</td>
<td width="50%" align="center">
<br>

**Queue + Poll architecture**

<img src="assets/hauba-architecture.gif" alt="architecture" width="100%">

<sub>Your machine &harr; Server relay &harr; Any channel</sub>
<br><br>
</td>
</tr>
</table>

<br>

---

<br>

<div align="center">

## Get Started

**One command. No Docker, Redis, or Kubernetes.**

</div>

<br>

```bash
pip install hauba
```

<details>
<summary>&nbsp;&nbsp;<strong>macOS / Linux one-liner</strong></summary>

```bash
curl -fsSL https://hauba.tech/install.sh | sh
```

</details>

<details>
<summary>&nbsp;&nbsp;<strong>Windows PowerShell</strong></summary>

```powershell
irm hauba.tech/install.ps1 | iex
```

</details>

<details>
<summary>&nbsp;&nbsp;<strong>From source</strong></summary>

```bash
git clone https://github.com/NikeGunn/haubaa.git && cd haubaa
pip install -e ".[dev]"
```

</details>

<details>
<summary>&nbsp;&nbsp;<strong>Optional extras</strong></summary>

```bash
pip install hauba[all]            # Everything
pip install hauba[computer-use]   # Browser + screen automation
pip install hauba[voice]          # Voice mode (Whisper + TTS)
pip install hauba[web]            # Web dashboard (FastAPI)
pip install hauba[channels]       # WhatsApp, Telegram, Discord
pip install hauba[services]       # Email (SMTP)
```

</details>

**Requirements:** Python 3.11+ — that's it.

<br>

### Three commands to production

```bash
hauba init                          # pick your LLM, paste your key
hauba run "your task in plain English"   # agent plans, you approve, it ships
hauba doctor                        # verify everything works
```

The engine **thinks before it acts.** Plans the approach. Shows you for approval. Builds with real tools — bash, files, git, web, browser. Runs your tests. Verifies output on disk. Then delivers.

Session stays open. Keep going:

```
> "add rate limiting and CORS"
> "write a Dockerfile"
> "deploy to Railway"
```

<br>

---

<br>

<div align="center">

## Why Hauba

</div>

<br>

<table>
<tr>
<td width="33%" align="center">
<br>
<h3>Enterprise-Grade Engine</h3>
<p>The same GitHub Copilot SDK production runtime. Not a wrapper around ChatGPT. The real agentic backbone — battle-tested, production-hardened.</p>
<br>
</td>
<td width="33%" align="center">
<br>
<h3>BYOK — Zero Platform Cost</h3>
<p>Bring Claude, GPT-4, or run Ollama locally for free. Your key never leaves your machine. Server owner pays nothing. You control every dollar.</p>
<br>
</td>
<td width="33%" align="center">
<br>
<h3>Air-Gap Ready</h3>
<p>100% offline with Ollama. No telemetry. No phone-home. Run it in a classified environment, on a submarine, in a bunker. It doesn't care.</p>
<br>
</td>
</tr>
<tr>
<td width="33%" align="center">
<br>
<h3>17 Domain Skills</h3>
<p>Full-stack, ML, video editing, DevOps, security hardening, data engineering — matched to your task via TF-IDF scoring. Not generic. Specialized.</p>
<br>
</td>
<td width="33%" align="center">
<br>
<h3>Multi-Channel</h3>
<p>WhatsApp. Telegram. Discord. Voice. Web dashboard. REST API. Command your AI team from your phone at 2am. It builds while you sleep.</p>
<br>
</td>
<td width="33%" align="center">
<br>
<h3>Zero-Hallucination Ledger</h3>
<p>SHA-256 hash chain + bit-vector + WAL. Five verification gates. If the agent says it's done, it's cryptographically proven. No trust required.</p>
<br>
</td>
</tr>
</table>

<br>

---

<br>

<div align="center">

## Core Capabilities

</div>

<br>

### `hauba agent` — The 24/7 Daemon

Your personal AI engineer that never sleeps, never takes PTO, never asks for a raise.

```bash
hauba agent --server https://hauba.tech
```

| What It Does | How |
|-------------|-----|
| Polls for tasks | Every 10 seconds from WhatsApp/Telegram/Discord |
| Claims and builds | Locally, with your API key |
| Reports progress | Every 15s — live updates on your phone |
| Tracks cost | Alerts when spend exceeds threshold ($5 default) |
| Auto-retries | Up to 3 attempts on failure |
| Remote cancel | Kill a task from WhatsApp mid-execution |

<br>

### Multi-Channel Access

Message your Hauba bot from anywhere. Build requests get queued. Chat gets instant responses. Zero false positives.

| Command | Effect |
|---------|--------|
| *"build me a dashboard"* | Queued for your daemon |
| `/tasks` | List all tasks with live status |
| `/cancel <id>` | Kill a running task |
| `/retry <id>` | Retry a failed task |
| `/web <url>` | Fetch + summarize any URL |
| `/email <to> <subj> \| <body>` | Send an email |
| `/reply <msg\|off>` | Auto-reply mode |
| `/usage` | Cost and usage stats |
| `/status` | Quick health check |
| `/plugins` | Active plugins |
| `/feedback <msg>` | Feedback |
| `/new` | Fresh session |

```bash
hauba setup whatsapp   # interactive Twilio wizard
```

<br>

### `hauba compose` — Declarative AI Teams

Like `docker-compose`, but every container is an AI engineer.

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

Backend and frontend run **in parallel**. DevOps waits for both. DAG execution. Circular dependency detection.

<br>

### 17 Built-in Skills

Human-readable `.md` files. Composable. Installable. TF-IDF matched to every task.

<details>
<summary>&nbsp;&nbsp;<strong>View all 17</strong></summary>

| Skill | What It Knows |
|-------|--------------|
| `full-stack-engineering` | Complete SaaS builds — 6-milestone playbook |
| `api-design-and-integration` | REST, GraphQL, webhooks |
| `code-generation` | Multi-language, any framework |
| `data-engineering` | Pipelines, ETL, warehousing |
| `data-processing` | Cleaning, transformation, analysis |
| `debugging-and-repair` | Root cause analysis, fixes |
| `devops-and-deployment` | Docker, CI/CD, cloud infra |
| `document-generation` | Reports, docs, technical writing |
| `image-generation` | Image creation + processing |
| `machine-learning` | Training, evaluation, deployment |
| `refactoring-and-migration` | Code modernization |
| `research-and-analysis` | Deep research, synthesis |
| `security-hardening` | Audits, OWASP, hardening |
| `testing-and-quality` | Test suites, QA, coverage |
| `video-editing` | Trim, effects, subtitles |
| `web-scraping` | Data extraction at scale |
| `automation-and-scripting` | Workflow automation |

</details>

```bash
hauba skill list                    # see all
hauba skill show full-stack         # inspect one
hauba skill install ./custom.md     # add yours
hauba skill create my-skill         # scaffold
```

<br>

### TaskLedger — Zero Trust, Full Verification

Every task passes **5 cryptographic gates** before it's marked complete:

```
Gate 1  PRE-EXECUTION     Ledger must exist before any work
Gate 2  DEPENDENCY         All upstream tasks VERIFIED
Gate 3  COMPLETION         SHA256(prev_hash + task_id + artifact_hash)
Gate 4  DELIVERY           Full gate check at every level
Gate 5  RECONCILIATION     plan_count === ledger_count
```

Backed by bit-vector state tracking, SHA-256 hash chain, and Write-Ahead Log. Crash-safe. Tamper-evident. If the agent says it shipped, it shipped.

<br>

### Plugin System

Seven lifecycle hooks. Full async. First-class citizens.

```python
from hauba.plugins.base import BasePlugin

class MyPlugin(BasePlugin):
    name = "my-plugin"

    async def on_message(self, channel, sender, text):
        if "urgent" in text.lower():
            return "Prioritizing your task!"
        return None

    async def on_task_complete(self, task_id, output):
        ...

def create_plugin():
    return MyPlugin()
```

```bash
hauba plugins install ./my_plugin.py
hauba plugins list
hauba plugins remove my-plugin
```

`on_load` · `on_unload` · `on_message` · `on_task_complete` · `on_task_queued` · `on_startup` · `on_shutdown`

<br>

### Everything Else

| | |
|---|---|
| `hauba voice` | Talk to your AI team |
| `hauba serve` | Real-time web dashboard |
| `hauba api` | REST API with SSE streaming |
| `hauba email` | Send emails |
| `hauba web <url>` | Fetch and summarize any URL |
| `hauba reply` | WhatsApp auto-reply |
| `hauba replay <id>` | Replay any agent session |
| `hauba doctor` | Full system diagnostics |

<br>

---

<br>

<div align="center">

## Supported Models

**Bring any model. We don't lock you in.**

</div>

<br>

| Provider | Models | Cost | Offline |
|----------|--------|------|---------|
| **Anthropic** | Claude Opus 4.6 · Sonnet 4.5 · Haiku 4.5 | Your key | — |
| **OpenAI** | GPT-4o · o3 | Your key | — |
| **Azure** | Any Azure OpenAI deployment | Your key | — |
| **Ollama** | Qwen 2.5 Coder · Llama 3 · any model | **Free** | **Yes** |

```bash
hauba config llm.provider anthropic
hauba config llm.model claude-sonnet-4-5-20250929
```

<br>

---

<br>

<div align="center">

## Architecture

</div>

<br>

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CHANNELS                                    │
│     WhatsApp  ·  Telegram  ·  Discord  ·  Voice  ·  Web  ·  API     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                        ┌──────▼──────┐
                        │   SERVER    │    hauba.tech
                        │             │
                        │  Task Queue │    submit / poll / claim
                        │  Webhooks   │    channel integrations
                        │  Chat LLM   │    lightweight responses
                        └──────┬──────┘
                               │ poll every 10s
                        ┌──────▼──────┐
                        │   DAEMON    │    your machine
                        │             │
                        │  Auto-claim │    picks up tasks
                        │  Execute    │    CopilotEngine (YOUR key)
                        │  Progress   │    live updates
                        │  Cost track │    per-task estimates
                        └──────┬──────┘
                               │
                  ┌────────────▼────────────┐
                  │     COPILOT ENGINE      │
                  │                         │
                  │  SkillMatcher  (TF-IDF) │    17 domain skills
                  │  TaskLedger (SHA-256)   │    zero hallucination
                  │  Tools: bash · files    │
                  │    git · web · browser  │
                  │    screen · fetch       │
                  └─────────────────────────┘
```

<br>

<details>
<summary>&nbsp;&nbsp;<strong>Source layout</strong></summary>

```
src/hauba/
├── cli.py                     # 20+ commands (Typer + Rich)
├── engine/copilot_engine.py   # Core — GitHub Copilot SDK
├── daemon/
│   ├── agent.py               # 24/7 polling daemon
│   └── queue.py               # Task queue (TTL, retry, cancel)
├── channels/
│   ├── whatsapp_webhook.py    # WhatsApp bot (12 commands)
│   ├── telegram.py            # Telegram
│   ├── discord.py             # Discord
│   └── voice.py               # Whisper STT + edge-tts
├── skills/
│   ├── loader.py              # .md skill parser
│   └── matcher.py             # TF-IDF matching
├── plugins/                   # base, loader, registry
├── ledger/
│   ├── tracker.py             # Bit-vector + SHA-256 hash chain
│   ├── wal.py                 # Write-Ahead Log
│   └── gates.py               # 5 verification gates
├── memory/store.py            # SQLite + TTL + compaction
├── services/
│   ├── email.py               # SMTP
│   └── reply_assistant.py     # Auto-reply engine
├── tools/                     # bash, files, git, fetch, browser, screen
├── compose/                   # hauba.yaml parser + DAG runner
├── core/                      # config, constants, events
├── ui/                        # Rich terminal + FastAPI web
└── bundled_skills/            # 17 .md files
```

</details>

<details>
<summary>&nbsp;&nbsp;<strong>Tech stack</strong></summary>

| Layer | Choice |
|-------|--------|
| Runtime | Python 3.11+ · asyncio |
| AI Engine | GitHub Copilot SDK |
| CLI | Typer · Rich |
| Storage | SQLite (aiosqlite) |
| Validation | Pydantic v2 |
| HTTP | httpx |
| Logging | structlog |
| Web | FastAPI · WebSocket |
| Channels | Twilio · python-telegram-bot · discord.py |
| Voice | Whisper · edge-tts |
| Browser | Playwright |
| Quality | ruff · pyright · pytest |

</details>

<details>
<summary>&nbsp;&nbsp;<strong>Full CLI reference (20+ commands)</strong></summary>

```
CORE
  hauba init                              Setup wizard
  hauba run "task" [--no-interactive]     Execute a task
  hauba status                            Config + last task
  hauba doctor                            System diagnostics
  hauba logs [--lines 50]                 View logs
  hauba config <key> [value]              Get/set config

DAEMON & TASKS
  hauba agent [--server URL]              24/7 daemon
  hauba tasks [--server URL]              List tasks
  hauba cancel <task_id>                  Cancel task
  hauba retry <task_id>                   Retry task
  hauba usage                             Cost summary

COMPOSE
  hauba compose up "task" [-f file]       Run agent team
  hauba compose validate [-f file]        Validate YAML

SKILLS
  hauba skill list                        List skills
  hauba skill show <name>                 Inspect skill
  hauba skill install <path>              Add skill
  hauba skill create <name>               Scaffold skill

PLUGINS
  hauba plugins list                      List plugins
  hauba plugins install <path.py>         Add plugin
  hauba plugins remove <name>             Remove plugin

CHANNELS
  hauba setup whatsapp                    WhatsApp wizard
  hauba email <to> <subj> [body]          Send email
  hauba web <url>                         Fetch URL
  hauba reply <message|off>               Auto-reply
  hauba feedback <message>                Feedback

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

<div align="center">

## Deployment

</div>

<br>

Server runs on [Railway](https://railway.app) at **[hauba.tech](https://hauba.tech)**.

It handles webhooks, task queuing, and lightweight chat. **All builds execute on your machine.** Server cost: near zero.

<details>
<summary>&nbsp;&nbsp;<strong>Environment variables</strong></summary>

```bash
TWILIO_ACCOUNT_SID=...                    # WhatsApp
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+1...
HAUBA_LLM_API_KEY=...                     # Server chat only
HAUBA_SMTP_HOST=smtp.gmail.com            # Email (optional)
```

</details>

<br>

---

<br>

<div align="center">

## Testing

**432 tests. Zero failures. Three OS. Three Python versions.**

</div>

<br>

```bash
pytest tests/ -v
```

| | Status |
|---|---|
| Ubuntu · macOS · Windows | Passing |
| Python 3.11 · 3.12 · 3.13 | Passing |
| ruff lint + format | Passing |
| pyright type check | Passing |

<br>

---

<br>

## Contributing

```bash
git clone https://github.com/NikeGunn/haubaa.git && cd haubaa
pip install -e ".[dev]"
pytest tests/ -v && ruff check src/
```

Conventional commits: `feat:` · `fix:` · `refactor:` · `test:` · `docs:`

See [CONTRIBUTING.md](CONTRIBUTING.md).

<br>

---

<br>

<div align="center">

MIT License — [LICENSE](LICENSE)

<br><br>

**Stop hiring. Start shipping.**

[hauba.tech](https://hauba.tech) &nbsp;&nbsp; [PyPI](https://pypi.org/project/hauba/) &nbsp;&nbsp; [Issues](https://github.com/NikeGunn/haubaa/issues) &nbsp;&nbsp; [Releases](https://github.com/NikeGunn/haubaa/releases)

<br>

<sub>Powered by GitHub Copilot SDK &nbsp;·&nbsp; Verified by TaskLedger &nbsp;·&nbsp; Your key, your machine, your company</sub>

</div>
