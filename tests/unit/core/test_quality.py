"""Tests for QualityGateEngine — multi-gate quality checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from hauba.core.quality import GateResult, QualityGateEngine, QualityGateType, QualityReport


def test_quality_report_add_and_score() -> None:
    report = QualityReport()
    report.add(GateResult(QualityGateType.LINT, passed=True, score=1.0))
    report.add(GateResult(QualityGateType.TEST, passed=True, score=1.0))
    report.add(GateResult(QualityGateType.SECURITY, passed=True, score=1.0))

    assert report.overall_score > 0.9
    assert report.passed is True


def test_quality_report_fails_on_critical_gate() -> None:
    report = QualityReport()
    report.add(GateResult(QualityGateType.LINT, passed=True, score=1.0))
    report.add(GateResult(QualityGateType.TEST, passed=False, score=0.0))  # Critical
    report.add(GateResult(QualityGateType.SECURITY, passed=True, score=1.0))

    assert report.passed is False


def test_quality_report_weighted_score() -> None:
    report = QualityReport()
    # Test has highest weight (0.35)
    report.add(GateResult(QualityGateType.TEST, passed=True, score=1.0))
    # Lint has lower weight (0.15)
    report.add(GateResult(QualityGateType.LINT, passed=True, score=0.5))

    assert 0.6 < report.overall_score < 1.0


@pytest.mark.asyncio
async def test_security_scan_clean(tmp_path: Path) -> None:
    """Security scan finds no issues in clean code."""
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("def hello():\n    return 'world'\n")

    engine = QualityGateEngine(working_dir=tmp_path)
    result = await engine.check_security(files=[clean_file])

    assert result.passed is True
    assert result.score == 1.0


@pytest.mark.asyncio
async def test_security_scan_finds_eval(tmp_path: Path) -> None:
    """Security scan detects eval() usage."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("user_input = input()\nresult = eval(user_input)\n")

    engine = QualityGateEngine(working_dir=tmp_path)
    result = await engine.check_security(files=[bad_file])

    assert result.passed is False
    assert any("eval_usage" in e for e in result.errors)


@pytest.mark.asyncio
async def test_security_scan_finds_hardcoded_secret(tmp_path: Path) -> None:
    """Security scan detects hardcoded secrets."""
    bad_file = tmp_path / "secrets.py"
    bad_file.write_text('api_key = "sk-1234567890abcdef"\n')

    engine = QualityGateEngine(working_dir=tmp_path)
    result = await engine.check_security(files=[bad_file])

    assert result.passed is False
    assert any("hardcoded_secret" in e for e in result.errors)
