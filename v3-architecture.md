# Hauba V3 Architecture — OpenAI Agents SDK + Playwright MCP

> **"One command. The best autonomous AI agent in the world."**

## Why V3?

V2 used GitHub Copilot SDK — a black box with limited tool control, no MCP support,
and no way to add custom agents or handoffs. V3 replaces it with the **OpenAI Agents SDK**,
which gives us:

- **Multi-agent orchestration** with handoffs (Director → Coder → Browser → Reviewer)
- **MCP server integration** — Playwright MCP for browser, filesystem MCP for files
- **Any LLM provider** via LiteLLM (Anthropic, OpenAI, Ollama, DeepSeek)
- **Function tools** — clean Python decorators, type-safe
- **ShellTool + ApplyPatchTool** — built-in code editing (like Claude Code)
- **Streaming** — real-time events for terminal UI
- **Sessions** — automatic conversation persistence
- **Guardrails** — input/output validation

## Architecture Overview

```
User → CLI (Typer) → AgentOrchestrator
                          │
                    ┌──────┼──────────┐
                    │      │          │
              DirectorAgent  ←handoffs→  BrowserAgent
                    │                     │
              ┌─────┴─────┐         Playwright MCP
              │           │         (@playwright/mcp)
         CoderAgent   ReviewerAgent
              │
        ShellTool + ApplyPatchTool + FileSystem MCP
```

### Agent Hierarchy

| Agent | Role | Tools |
|-------|------|-------|
| **DirectorAgent** | CEO — plans, delegates, coordinates | web_search, web_fetch, handoffs to all |
| **CoderAgent** | Writes code, runs commands | ShellTool, ApplyPatchTool, FileSystem MCP |
| **BrowserAgent** | Web automation, scraping, testing | Playwright MCP (full browser) |
| **ReviewerAgent** | Code review, testing, quality | ShellTool (read-only), function tools |

### Communication

Agents communicate via **handoffs** (built into OpenAI Agents SDK).
The DirectorAgent decides which specialist to delegate to.
Each specialist returns results back to the Director.

## Core Components

### 1. Engine: `AgentEngine` (replaces CopilotEngine)

```python
from agents import Agent, Runner, MCPServerStdio, ShellTool, function_tool

class AgentEngine:
    """The single execution brain. Powered by OpenAI Agents SDK."""

    async def execute(self, task: str) -> EngineResult:
        # 1. Start MCP servers (Playwright, Filesystem)
        # 2. Create agent team with tools + handoffs
        # 3. Run via Runner.run_streamed()
        # 4. Stream events to UI
        # 5. Return result
```

### 2. MCP Servers

**Playwright MCP** — Full browser automation:
```python
playwright_mcp = MCPServerStdio(
    name="playwright",
    params={
        "command": "npx",
        "args": ["@playwright/mcp@latest", "--headless"],
    },
)
```

**Filesystem MCP** (optional, for sandboxed file access):
```python
filesystem_mcp = MCPServerStdio(
    name="filesystem",
    params={
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", workspace_dir],
    },
)
```

### 3. Custom Function Tools

```python
@function_tool
async def web_search(query: str, num_results: int = 5) -> str:
    """Search the web using DuckDuckGo."""
    ...

@function_tool
async def web_fetch(url: str) -> str:
    """Fetch and extract text from any URL."""
    ...

@function_tool
async def send_email(to: str, subject: str, body: str) -> str:
    """Send email via Brevo API."""
    ...
```

### 4. LLM Provider Support

```python
# Any provider via LiteLLM prefix:
Agent(model="litellm/anthropic/claude-sonnet-4-5-20250514")
Agent(model="litellm/ollama_chat/llama3.1")
Agent(model="litellm/deepseek/deepseek-chat")
Agent(model="gpt-4o")  # OpenAI native
```

### 5. CLI (Simplified)

The CLI becomes thin — just wires up the engine and streams output:

```
hauba run "build a dashboard"     → DirectorAgent plans + delegates
hauba init                        → Setup wizard (unchanged)
hauba config                      → Manage settings
hauba agent                       → Daemon mode (unchanged)
hauba doctor                      → Health check
```

No more 800-line interactive UI. The agent SDK handles conversation flow.
Rich terminal output for streaming events.

## Data Flow

```
1. User: "hauba run 'build a todo app with auth'"

2. CLI creates AgentEngine with config (provider, model, API key)

3. AgentEngine starts MCP servers:
   - Playwright MCP (browser)
   - Filesystem MCP (optional)

4. AgentEngine creates agent team:
   DirectorAgent
     ├── tools: [web_search, web_fetch, send_email]
     ├── handoffs: [CoderAgent, BrowserAgent, ReviewerAgent]
     └── instructions: "You are the CEO of an AI engineering team..."

   CoderAgent
     ├── tools: [ShellTool, ApplyPatchTool]
     ├── mcp_servers: [filesystem_mcp]
     └── instructions: "You are a senior software engineer..."

   BrowserAgent
     ├── mcp_servers: [playwright_mcp]
     └── instructions: "You are a browser automation specialist..."

   ReviewerAgent
     ├── tools: [ShellTool(read-only)]
     └── instructions: "You are a code reviewer..."

5. Runner.run_streamed(DirectorAgent, task)
   → Director plans → handoff to Coder
   → Coder writes code via Shell/Patch tools
   → Coder hands back to Director
   → Director hands to Reviewer
   → Reviewer checks, suggests fixes
   → Director hands to Coder for fixes
   → Director delivers final result

6. CLI streams events in real-time (Rich panels)

7. Result returned to user
```

## File Structure (V3)

```
src/hauba/
├── cli.py                    # Simplified CLI (Typer)
├── engine/
│   ├── __init__.py
│   ├── agent_engine.py       # NEW: OpenAI Agents SDK engine
│   ├── agents.py             # NEW: Agent definitions (Director, Coder, Browser, Reviewer)
│   ├── tools.py              # NEW: Function tools (web_search, web_fetch, email)
│   ├── mcp_servers.py        # NEW: MCP server management
│   ├── prompts.py            # NEW: Agent system prompts
│   └── types.py              # Engine types (EngineConfig, EngineResult, etc.)
├── channels/                 # Unchanged (WhatsApp, Telegram, Discord)
├── daemon/                   # Unchanged (queue, agent, autostart)
├── services/                 # Unchanged (email, reply_assistant)
├── memory/                   # Unchanged (store)
├── skills/                   # Unchanged (loader, matcher, cli)
├── tools/                    # KEEP: web.py, fetch.py, browser.py (used by function tools)
├── core/                     # Unchanged (config, constants, types)
├── ui/                       # Simplified (terminal streaming only)
└── ...
```

## What Changes

| Component | V2 (Copilot SDK) | V3 (OpenAI Agents SDK) |
|-----------|-------------------|------------------------|
| Engine | CopilotEngine (black box) | AgentEngine (transparent, extensible) |
| Tools | 4 custom tools injected | Function tools + MCP servers |
| Browser | Custom BrowserTool (playwright wrapper) | Playwright MCP server (official) |
| Multi-agent | None (single agent) | Director → Coder/Browser/Reviewer |
| LLM support | Copilot SDK providers | Any via LiteLLM |
| CLI | 800+ lines, custom interactive UI | Thin wrapper, agent handles conversation |
| Code editing | bash tool only | ShellTool + ApplyPatchTool (like Claude Code) |
| Streaming | Custom event system | Built-in Runner.run_streamed() |
| Sessions | Custom session persistence | Built-in SQLiteSession |
| MCP | Not supported | Native MCP server integration |

## What Stays

- WhatsApp/Telegram/Discord channels
- Daemon (queue + poll architecture)
- Email service (Brevo)
- Reply assistant
- Skills system (.md files)
- Memory store
- Config system
- CLI commands: init, config, agent, doctor, serve

## Dependencies

```toml
# REMOVE:
# github-copilot-sdk>=0.1.0

# ADD:
openai-agents = ">=0.1.0"
openai-agents[litellm]  # For non-OpenAI providers
```

## Migration Path

1. Create new engine (`agent_engine.py`, `agents.py`, `tools.py`, `mcp_servers.py`, `prompts.py`)
2. Simplify CLI to use new engine
3. Update WhatsApp webhook to use new engine
4. Update daemon to use new engine
5. Remove CopilotEngine (old)
6. Update pyproject.toml dependencies
7. Update tests

## Security

- API keys handled via BYOK (same as V2)
- MCP servers run as local subprocesses (sandboxed)
- Playwright MCP runs headless by default
- ShellTool can be configured with custom executor for sandboxing
- No API keys in system prompts
