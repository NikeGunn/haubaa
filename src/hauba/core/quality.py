"""Quality Gate Engine — Multi-gate quality checks for agent outputs.

Gates: lint, type check, test runner, security scan, self-review.
Each gate produces a score (0.0-1.0). Overall score is the weighted average.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import structlog

from hauba.core.constants import EVENT_QUALITY_FAILED, EVENT_QUALITY_PASSED
from hauba.core.events import EventEmitter
from hauba.tools.bash import BashTool

logger = structlog.get_logger()


class QualityGateType(str, Enum):
    """Types of quality gates."""

    LINT = "lint"
    TYPE_CHECK = "type_check"
    TEST = "test"
    SECURITY = "security"
    SELF_REVIEW = "self_review"


@dataclass
class GateResult:
    """Result from a single quality gate."""

    gate: QualityGateType
    passed: bool
    score: float  # 0.0 - 1.0
    details: str = ""
    errors: list[str] = field(default_factory=list)


@dataclass
class QualityReport:
    """Combined quality report from all gates."""

    gates: list[GateResult] = field(default_factory=list)
    overall_score: float = 0.0
    passed: bool = False

    def add(self, result: GateResult) -> None:
        self.gates.append(result)
        self._recalculate()

    def _recalculate(self) -> None:
        if not self.gates:
            return
        weights = {
            QualityGateType.LINT: 0.15,
            QualityGateType.TYPE_CHECK: 0.15,
            QualityGateType.TEST: 0.35,
            QualityGateType.SECURITY: 0.20,
            QualityGateType.SELF_REVIEW: 0.15,
        }
        total_weight = sum(weights.get(g.gate, 0.1) for g in self.gates)
        weighted_sum = sum(g.score * weights.get(g.gate, 0.1) for g in self.gates)
        self.overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        self.passed = self.overall_score >= 0.6 and all(
            g.passed
            for g in self.gates
            if g.gate in (QualityGateType.SECURITY, QualityGateType.TEST)
        )


# Security patterns to scan for
SECURITY_PATTERNS = [
    ("hardcoded_secret", r"(?i)(api[_-]?key|secret|password|token)\s*=\s*['\"][^'\"]{8,}['\"]"),
    ("sql_injection", r"(?i)f['\"].*(?:SELECT|INSERT|UPDATE|DELETE|DROP).*\{"),
    ("command_injection", r"(?i)os\.system\s*\(.*\{"),
    ("eval_usage", r"\beval\s*\("),
    ("exec_usage", r"\bexec\s*\("),
    ("pickle_load", r"pickle\.loads?\s*\("),
]


class QualityGateEngine:
    """Runs quality checks on agent outputs.

    Supports: lint (ruff), type check (pyright), tests (pytest),
    security scan (pattern matching), self-review (LLM).
    """

    def __init__(
        self,
        events: EventEmitter | None = None,
        working_dir: Path | None = None,
    ) -> None:
        self._events = events
        self._working_dir = working_dir or Path.cwd()
        self._bash = BashTool()

    async def run_all(self, files: list[Path] | None = None) -> QualityReport:
        """Run all quality gates and return a combined report."""
        report = QualityReport()

        # Run independent gates in parallel
        results = await asyncio.gather(
            self.check_lint(files),
            self.check_types(files),
            self.check_tests(),
            self.check_security(files),
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, GateResult):
                report.add(result)
            elif isinstance(result, Exception):
                logger.warning("quality.gate_error", error=str(result))

        if self._events:
            event_type = EVENT_QUALITY_PASSED if report.passed else EVENT_QUALITY_FAILED
            await self._events.emit(
                event_type,
                {
                    "overall_score": report.overall_score,
                    "passed": report.passed,
                    "gates": len(report.gates),
                },
            )

        return report

    async def check_lint(self, files: list[Path] | None = None) -> GateResult:
        """Run ruff linter."""
        target = " ".join(str(f) for f in files) if files else str(self._working_dir)
        result = await self._bash.execute(command=f"ruff check {target} --output-format=text 2>&1")

        if result.success and ("All checks passed" in result.output or not result.output.strip()):
            return GateResult(
                QualityGateType.LINT, passed=True, score=1.0, details="No lint issues"
            )

        # Count errors
        error_lines = [line for line in result.output.split("\n") if line.strip() and ":" in line]
        error_count = len(error_lines)
        score = max(0.0, 1.0 - (error_count * 0.05))  # -5% per issue

        return GateResult(
            QualityGateType.LINT,
            passed=error_count == 0,
            score=score,
            details=f"{error_count} lint issues found",
            errors=error_lines[:10],
        )

    async def check_types(self, files: list[Path] | None = None) -> GateResult:
        """Run type checker (pyright or mypy)."""
        target = " ".join(str(f) for f in files) if files else str(self._working_dir)
        result = await self._bash.execute(command=f"pyright {target} 2>&1")

        if result.success:
            return GateResult(
                QualityGateType.TYPE_CHECK, passed=True, score=1.0, details="No type errors"
            )

        # Fall back to mypy
        result = await self._bash.execute(command=f"mypy {target} --ignore-missing-imports 2>&1")
        if result.success:
            return GateResult(
                QualityGateType.TYPE_CHECK, passed=True, score=1.0, details="No type errors (mypy)"
            )

        error_lines = [line for line in result.output.split("\n") if "error:" in line.lower()]
        score = max(0.0, 1.0 - (len(error_lines) * 0.1))

        return GateResult(
            QualityGateType.TYPE_CHECK,
            passed=len(error_lines) == 0,
            score=score,
            details=f"{len(error_lines)} type errors",
            errors=error_lines[:10],
        )

    async def check_tests(self) -> GateResult:
        """Run pytest."""
        result = await self._bash.execute(
            command=f"python -m pytest {self._working_dir} -q --tb=short 2>&1",
        )

        if result.success:
            # Parse pass count
            for line in result.output.split("\n"):
                if "passed" in line:
                    return GateResult(
                        QualityGateType.TEST,
                        passed=True,
                        score=1.0,
                        details=line.strip(),
                    )
            return GateResult(QualityGateType.TEST, passed=True, score=1.0, details="Tests passed")

        # Parse failures
        for line in result.output.split("\n"):
            if "failed" in line.lower():
                return GateResult(
                    QualityGateType.TEST,
                    passed=False,
                    score=0.0,
                    details=line.strip(),
                    errors=[result.output[-500:]],
                )

        return GateResult(QualityGateType.TEST, passed=False, score=0.0, details="Tests failed")

    async def check_security(self, files: list[Path] | None = None) -> GateResult:
        """Basic security pattern scan."""
        import re

        findings: list[str] = []
        scan_files = files or list(self._working_dir.rglob("*.py"))

        for filepath in scan_files:
            if not filepath.exists() or not filepath.is_file():
                continue
            try:
                content = filepath.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            for pattern_name, pattern in SECURITY_PATTERNS:
                matches = re.findall(pattern, content)
                if matches:
                    findings.append(f"{filepath.name}: {pattern_name} ({len(matches)} match(es))")

        if not findings:
            return GateResult(
                QualityGateType.SECURITY, passed=True, score=1.0, details="No security issues"
            )

        score = max(0.0, 1.0 - (len(findings) * 0.2))
        return GateResult(
            QualityGateType.SECURITY,
            passed=False,
            score=score,
            details=f"{len(findings)} security findings",
            errors=findings,
        )

    async def check_self_review(self, code: str, **kwargs: Any) -> GateResult:
        """Self-review gate (placeholder — Copilot SDK handles quality internally)."""
        return GateResult(
            QualityGateType.SELF_REVIEW,
            passed=True,
            score=0.7,
            details="Skipped (Copilot SDK handles quality internally)",
        )
