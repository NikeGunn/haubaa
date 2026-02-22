# Skill: Hauba Testing Strategy

## Test Structure
```
tests/
├── unit/                    # Fast, isolated, no external deps
│   ├── core/
│   │   ├── test_engine.py
│   │   ├── test_events.py
│   │   └── test_config.py
│   ├── agents/
│   │   ├── test_director.py
│   │   ├── test_worker.py
│   │   └── test_base.py
│   ├── brain/
│   │   ├── test_llm.py
│   │   ├── test_deliberation.py
│   │   └── test_planner.py
│   ├── memory/
│   │   └── test_store.py
│   ├── ledger/
│   │   ├── test_tracker.py
│   │   └── test_gates.py
│   └── skills/
│       ├── test_loader.py
│       └── test_matcher.py
├── integration/             # Tests with real SQLite, file system
│   ├── test_agent_workflow.py
│   ├── test_multi_agent.py
│   └── test_ledger_crash_recovery.py
├── e2e/                     # Full CLI tests
│   ├── test_cli_init.py
│   ├── test_cli_run.py
│   └── test_cli_status.py
├── fixtures/                # Shared test data
│   ├── recorded_llm_responses/
│   ├── sample_skills/
│   └── sample_strategies/
└── conftest.py              # Shared fixtures
```

## Mocking LLM Calls
```python
# Always mock LLM in unit tests
@pytest.fixture
def mock_llm():
    """Returns a mock LLM that returns pre-recorded responses."""
    responses = load_recorded_responses("fixtures/recorded_llm_responses/")
    return MockLLMRouter(responses)
```

## Critical Test Scenarios

### TaskLedger (Must have 100% coverage)
- Create ledger → verify all bits are 0
- Start task → verify bit becomes 1
- Complete task with hash → verify bit becomes 2
- GateCheck with all verified → passes
- GateCheck with missing tasks → HALT error
- GateCheck with hash mismatch → HALT error
- Crash recovery: write WAL → simulate crash → replay → verify state restored
- Dependency gate: try starting task with unverified deps → error

### Agent Hierarchy
- Director deliberates and creates plan
- SubAgent receives milestone and spawns workers
- Workers execute and report back
- CoWorker does single task and terminates
- Full hierarchy: Director → SubAgent → Worker → CoWorker → result bubbles up

### Event System
- Publish event → subscriber receives it
- Multiple subscribers → all receive
- Event ordering preserved within topic
- Unsubscribe → no longer receives

## Running Tests
```bash
# All tests
pytest tests/

# Unit only (fast)
pytest tests/unit/

# Integration (needs file system)
pytest tests/integration/ -m integration

# E2E (needs full CLI)
pytest tests/e2e/ -m e2e

# With coverage
pytest tests/ --cov=src/hauba --cov-report=term-missing
```
