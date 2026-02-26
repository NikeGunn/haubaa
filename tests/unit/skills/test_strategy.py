"""Tests for Strategy Engine — .yaml strategy parsing and matching."""

from __future__ import annotations

from pathlib import Path

import pytest

from hauba.skills.strategy import MINIMUM_STRATEGY_MATCH_SCORE, StrategyEngine


@pytest.fixture
def strategy_dir(tmp_path: Path) -> Path:
    """Create a temp directory with a sample strategy YAML file."""
    strategy = tmp_path / "saas-building.yaml"
    strategy.write_text(
        "name: saas-building\n"
        "description: Build SaaS applications\n"
        "domain: saas\n"
        "quality_gates:\n"
        "  - All tests passing\n"
        "  - No security vulnerabilities\n"
        "milestones:\n"
        "  - id: design\n"
        "    description: Design the architecture\n"
        "  - id: backend\n"
        "    description: Build the backend API\n"
        "    dependencies:\n"
        "      - design\n"
        "  - id: frontend\n"
        "    description: Build the frontend UI\n"
        "    dependencies:\n"
        "      - design\n"
    )
    return tmp_path


def test_load_strategy(strategy_dir: Path) -> None:
    engine = StrategyEngine(strategy_dirs=[strategy_dir])
    strategies = engine.load_all()

    assert "saas-building" in strategies
    s = strategies["saas-building"]
    assert s.domain == "saas"


def test_match_domain(strategy_dir: Path) -> None:
    engine = StrategyEngine(strategy_dirs=[strategy_dir])
    match = engine.match_domain("build a SaaS web application")
    assert match is not None
    assert match.name == "saas-building"


def test_no_match(strategy_dir: Path) -> None:
    engine = StrategyEngine(strategy_dirs=[strategy_dir])
    match = engine.match_domain("quantum physics simulation")
    assert match is None


def test_list_strategies(strategy_dir: Path) -> None:
    engine = StrategyEngine(strategy_dirs=[strategy_dir])
    names = engine.list_strategies()
    assert "saas-building" in names


def test_strategy_to_milestones(strategy_dir: Path) -> None:
    engine = StrategyEngine(strategy_dirs=[strategy_dir])
    s = engine.get("saas-building")
    assert s is not None
    milestones = s.to_milestone_objects()
    assert len(milestones) >= 2


def test_strategy_create_ledger(strategy_dir: Path) -> None:
    engine = StrategyEngine(strategy_dirs=[strategy_dir])
    s = engine.get("saas-building")
    assert s is not None
    ledger = s.create_ledger()
    assert ledger.task_count >= 2


def test_empty_dir(tmp_path: Path) -> None:
    engine = StrategyEngine(strategy_dirs=[tmp_path])
    strategies = engine.load_all()
    assert len(strategies) == 0


def test_low_score_returns_none(tmp_path: Path) -> None:
    """Strategies with score below MINIMUM_STRATEGY_MATCH_SCORE return None."""
    strategy = tmp_path / "review.yaml"
    strategy.write_text(
        "name: code-review-and-refactor\n"
        "description: Code quality improvement\n"
        "domain: refactor\n"
        "milestones:\n"
        "  - id: audit\n"
        "    description: Code quality audit\n"
    )
    engine = StrategyEngine(strategy_dirs=[tmp_path])
    # "Build me a todo list app" should NOT match code-review-and-refactor
    match = engine.match_domain("Build me a todo list app with beautiful landing page")
    assert match is None


def test_minimum_score_threshold_value() -> None:
    """Ensure the threshold constant is sane."""
    assert MINIMUM_STRATEGY_MATCH_SCORE >= 3
    assert MINIMUM_STRATEGY_MATCH_SCORE <= 10
