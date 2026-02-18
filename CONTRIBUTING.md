# Contributing to Hauba

Thanks for your interest in contributing to Hauba! Here's how to get started.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/NikeGunn/haubaa.git
cd haubaa

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest tests/ -v
```

## Making Changes

1. **Fork** the repo and create a branch from `main`
2. **Write tests** for any new functionality
3. **Run the test suite**: `pytest tests/ -v`
4. **Run linting**: `ruff check src/ && ruff format --check src/`
5. **Submit a PR** with a clear description

## Coding Standards

- **Python 3.11+** with type hints on all functions
- **Async/await** for all I/O operations
- **structlog** for logging (structured JSON output)
- **pytest + pytest-asyncio** for testing
- **ruff** for formatting and linting

## Commit Messages

Use conventional commits:

```
feat: add new browser retry logic
fix: handle timeout in LLM router
refactor: simplify event emitter
test: add TaskLedger gate tests
docs: update README quickstart
```

## Project Structure

```
src/hauba/
├── cli.py           # CLI entry point
├── core/            # Engine, events, config
├── agents/          # Director, SubAgent, Worker
├── brain/           # LLM router, deliberation, planner
├── memory/          # SQLite store
├── skills/          # Skill loader and matcher
├── tools/           # Bash, files, git, browser, web
├── ledger/          # TaskLedger (zero-hallucination)
├── channels/        # Voice, Telegram, Discord
├── compose/         # hauba.yaml team orchestration
└── ui/              # Terminal (Rich) + Web (FastAPI)
```

## Reporting Issues

- Use the issue templates for bugs and feature requests
- Include your Python version, OS, and hauba version
- For bugs, include steps to reproduce and `hauba doctor` output

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
