# Hauba V3 — Build Phases

> **From agent framework to AI workstation.**
> **Single engine. Seventeen skills. Ship v0.3.0.**

---

## Build Order Summary

| Phase | What Ships | Outcome |
|-------|-----------|---------|
| **Phase 1** | Architecture docs | V3 design documented |
| **Phase 2** | Legacy deletion | agents/, brain/, strategies/, DAG removed |
| **Phase 3** | Import cleanup | All remaining files compile clean |
| **Phase 4** | Skill expansion | 17 skills (10 enhanced + 7 new) |
| **Phase 5** | Engine enhancement | CopilotEngine as single brain |
| **Phase 6** | CLI simplification | Clean CopilotEngine-only CLI |
| **Phase 7** | Dependencies | pyproject.toml + install scripts updated |
| **Phase 8** | Tests | All tests pass with new architecture |
| **Phase 9** | Documentation | CLAUDE.md, README.md, MEMORY.md updated |

---

## Phase 1: Architecture Documentation

- [x] ARCHITECTURE_V3.md — Single-engine design
- [x] BUILD_PHASES_V3.md — This file
- [x] PROGRESS.md — Updated for v0.3.0

## Phase 2: Surgical Deletion

DELETE entire directories:
- [ ] `src/hauba/agents/` — Director, SubAgent, Worker, CoWorker, base, computer_use, registry
- [ ] `src/hauba/brain/` — LLMRouter, deliberation, intent, planner
- [ ] `src/hauba/bundled_strategies/` — 6 YAML strategy files
- [ ] `strategies/` — Root-level user strategies

DELETE specific files:
- [ ] `src/hauba/core/dag.py` — DAG executor
- [ ] `src/hauba/skills/strategy.py` — Strategy engine

DELETE legacy tests:
- [ ] `tests/unit/agents/` — All agent tests
- [ ] `tests/unit/brain/` — All brain tests
- [ ] `tests/unit/core/test_dag.py` — DAG tests
- [ ] `tests/unit/skills/test_strategy.py` — Strategy tests
- [ ] `tests/integration/test_e2e_pipeline.py` — Legacy E2E
- [ ] `tests/integration/test_phase2_pipeline.py` — Multi-agent pipeline
- [ ] `tests/integration/test_phase3_pipeline.py` — Computer use pipeline

## Phase 3: Import Cleanup

Fix files that imported from deleted modules:
- [ ] `src/hauba/core/constants.py` — Remove strategy/agent constants
- [ ] `src/hauba/core/types.py` — Remove AgentRole, AgentState, LLM types, Plan
- [ ] `src/hauba/core/setup.py` — Remove STRATEGIES_DIR
- [ ] `src/hauba/exceptions.py` — Remove AgentError, DeliberationError, StrategyNotFoundError
- [ ] `src/hauba/skills/__init__.py` — Remove strategy references

## Phase 4: Skill Expansion

Merge strategy content into existing skills:
- [ ] `full-stack-engineering.md` ← saas-building.yaml
- [ ] `debugging-and-repair.md` ← bug-fixing.yaml
- [ ] `data-engineering.md` ← data-pipeline.yaml
- [ ] `api-design-and-integration.md` ← api-development.yaml
- [ ] `refactoring-and-migration.md` ← code-review-and-refactor.yaml
- [ ] `research-and-analysis.md` ← research-and-prototype.yaml

Create new skills:
- [ ] `video-editing.md`
- [ ] `image-generation.md`
- [ ] `data-processing.md`
- [ ] `web-scraping.md`
- [ ] `automation-and-scripting.md`
- [ ] `document-generation.md`
- [ ] `machine-learning.md`

Update skill loader:
- [ ] Parse `## Tools Required` section
- [ ] Parse `## Playbook` sections

## Phase 5: Engine Enhancement

- [ ] New AI Workstation system prompt (full-domain coverage)
- [ ] Session persistence (`~/.hauba/last_session.json`)
- [ ] Light TaskLedger integration (hash outputs for audit)
- [ ] EngineConfig updates (session_persist, auto_install_deps)

## Phase 6: CLI Simplification

- [ ] Remove `--legacy` flag from `hauba run`
- [ ] Add `--continue` flag for session resumption
- [ ] Remove `hauba engine-run` command
- [ ] Rewrite `hauba voice` for CopilotEngine
- [ ] Rewrite `hauba init` API test (CopilotEngine ping)
- [ ] Simplify `hauba compose up` (serial CopilotEngine calls)
- [ ] Rename `_build_skill_strategy_context()` → `_build_skill_context()`

## Phase 7: Dependencies & Install

- [ ] Remove `litellm` from pyproject.toml
- [ ] Make `github-copilot-sdk` a core dependency
- [ ] Remove `[engine]` optional extra
- [ ] Bump version to 0.3.0
- [ ] Update install.ps1 banner + verification
- [ ] Update install.sh banner + verification

## Phase 8: Test Rewrite

- [ ] Enhance `tests/unit/engine/test_copilot_engine.py`
- [ ] Rewrite `tests/unit/compose/test_runner.py`
- [ ] Create `tests/unit/engine/test_system_prompt.py`
- [ ] Create `tests/unit/engine/test_skill_injection.py`
- [ ] Create `tests/unit/skills/test_new_skills.py`
- [ ] Create `tests/integration/test_engine_pipeline.py`
- [ ] Verify all surviving tests still pass

## Phase 9: Documentation

- [ ] Update CLAUDE.md (remove agent hierarchy, litellm refs)
- [ ] Update README.md (new tagline, 17 skills, simplified arch)
- [ ] Update MEMORY.md (v3 architecture)

---

## Verification Checklist

- [ ] `ruff check src/` — Zero lint errors
- [ ] `pytest tests/ -x -v` — All tests pass
- [ ] `pip install -e .` — Clean install with copilot-sdk
- [ ] No imports from deleted modules (agents, brain, strategy, dag, litellm)
