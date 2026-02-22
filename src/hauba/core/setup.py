"""Hauba directory structure setup."""

from __future__ import annotations

from pathlib import Path

import structlog

from hauba.core.constants import (
    AGENTS_DIR,
    BACKUPS_DIR,
    CONTEXT_DIR,
    HAUBA_HOME,
    KNOWLEDGE_DIR,
    LOGS_DIR,
    MEMORY_DIR,
    OWNER_MEMORY_DIR,
    SKILLS_DIR,
    STRATEGIES_DIR,
)

logger = structlog.get_logger()

REQUIRED_DIRS = [
    HAUBA_HOME,
    AGENTS_DIR,
    MEMORY_DIR,
    OWNER_MEMORY_DIR,
    KNOWLEDGE_DIR,
    CONTEXT_DIR,
    SKILLS_DIR,
    STRATEGIES_DIR,
    LOGS_DIR,
    BACKUPS_DIR,
]


def ensure_hauba_dirs(base: Path | None = None) -> Path:
    """Create the ~/.hauba/ directory structure. Returns the base path."""
    home = base or HAUBA_HOME
    dirs = (
        REQUIRED_DIRS
        if base is None
        else [
            home,
            home / "agents",
            home / "memory",
            home / "memory" / "owner",
            home / "memory" / "knowledge",
            home / "memory" / "context",
            home / "skills",
            home / "strategies",
            home / "logs",
            home / "backups",
        ]
    )
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    logger.info("setup.dirs_created", home=str(home))
    return home
