"""Hauba Doctor — diagnose setup issues and check system health."""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import structlog

from hauba.core.constants import DB_FILE, HAUBA_HOME, SETTINGS_FILE

logger = structlog.get_logger()


@dataclass
class CheckResult:
    """Result of a single diagnostic check."""

    name: str
    passed: bool
    message: str
    suggestion: str = ""


class Doctor:
    """Runs diagnostic checks for Hauba setup."""

    async def run_all(self) -> list[CheckResult]:
        """Run all diagnostic checks and return results."""
        results: list[CheckResult] = []
        results.append(self._check_python_version())
        results.append(self._check_hauba_init())
        results.append(self._check_api_key())
        results.append(self._check_sqlite())
        results.append(self._check_disk_space())
        results.append(self._check_playwright())
        results.append(self._check_copilot_sdk())
        return results

    def _check_python_version(self) -> CheckResult:
        ver = sys.version_info
        if ver >= (3, 11):
            return CheckResult(
                name="Python Version",
                passed=True,
                message=f"Python {ver.major}.{ver.minor}.{ver.micro}",
            )
        return CheckResult(
            name="Python Version",
            passed=False,
            message=f"Python {ver.major}.{ver.minor}.{ver.micro} (requires 3.11+)",
            suggestion="Upgrade Python: https://python.org/downloads/",
        )

    def _check_hauba_init(self) -> CheckResult:
        if SETTINGS_FILE.exists():
            return CheckResult(
                name="Hauba Init",
                passed=True,
                message=f"Initialized at {HAUBA_HOME}",
            )
        return CheckResult(
            name="Hauba Init",
            passed=False,
            message="Not initialized",
            suggestion="Run: hauba init",
        )

    def _check_api_key(self) -> CheckResult:
        if not SETTINGS_FILE.exists():
            return CheckResult(
                name="API Key",
                passed=False,
                message="No settings file found",
                suggestion="Run: hauba init",
            )
        try:
            from hauba.core.config import ConfigManager

            config = ConfigManager()
            key = config.settings.llm.api_key
            provider = config.settings.llm.provider
            if provider == "ollama":
                return CheckResult(name="API Key", passed=True, message="Ollama (no key needed)")
            if key and len(key) > 10:
                masked = key[:4] + "..." + key[-4:]
                return CheckResult(name="API Key", passed=True, message=f"{provider}: {masked}")
            return CheckResult(
                name="API Key",
                passed=False,
                message="API key missing or too short",
                suggestion=f"Run: hauba config llm.api_key <your-{provider}-key>",
            )
        except Exception as exc:
            return CheckResult(
                name="API Key",
                passed=False,
                message=f"Error reading config: {exc}",
                suggestion="Run: hauba init",
            )

    def _check_sqlite(self) -> CheckResult:
        try:
            import sqlite3

            if DB_FILE.exists():
                conn = sqlite3.connect(str(DB_FILE))
                conn.execute("SELECT 1")
                conn.close()
                size_mb = DB_FILE.stat().st_size / (1024 * 1024)
                return CheckResult(
                    name="SQLite Database",
                    passed=True,
                    message=f"OK ({size_mb:.1f} MB)",
                )
            return CheckResult(
                name="SQLite Database",
                passed=True,
                message="Not yet created (will be created on first run)",
            )
        except Exception as exc:
            return CheckResult(
                name="SQLite Database",
                passed=False,
                message=f"Database error: {exc}",
                suggestion="Delete ~/.hauba/hauba.db and re-run",
            )

    def _check_disk_space(self) -> CheckResult:
        try:
            usage = shutil.disk_usage(HAUBA_HOME.parent if HAUBA_HOME.exists() else Path.home())
            free_gb = usage.free / (1024**3)
            if free_gb >= 1.0:
                return CheckResult(
                    name="Disk Space",
                    passed=True,
                    message=f"{free_gb:.1f} GB free",
                )
            return CheckResult(
                name="Disk Space",
                passed=False,
                message=f"Only {free_gb:.2f} GB free",
                suggestion="Free up disk space (Hauba needs at least 1 GB)",
            )
        except Exception as exc:
            return CheckResult(
                name="Disk Space",
                passed=False,
                message=f"Could not check: {exc}",
            )

    def _check_playwright(self) -> CheckResult:
        try:
            import playwright  # noqa: F401

            # Check if browsers are installed
            pw_path = Path(sys.prefix) / "Scripts" / "playwright.cmd"
            if not pw_path.exists():
                pw_path = shutil.which("playwright")  # type: ignore[assignment]
            return CheckResult(
                name="Playwright (Browser)",
                passed=True,
                message="Installed",
            )
        except ImportError:
            return CheckResult(
                name="Playwright (Browser)",
                passed=False,
                message="Not installed (optional — needed for browser automation)",
                suggestion="Run: pip install hauba[computer-use] && playwright install chromium",
            )

    def _check_copilot_sdk(self) -> CheckResult:
        try:
            import copilot

            version = getattr(copilot, "__version__", "installed")
            return CheckResult(
                name="Copilot SDK",
                passed=True,
                message=f"Version {version}",
            )
        except ImportError:
            return CheckResult(
                name="Copilot SDK",
                passed=False,
                message="Not installed",
                suggestion="Run: pip install github-copilot-sdk",
            )
