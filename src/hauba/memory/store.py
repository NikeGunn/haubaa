"""SQLite-based persistent memory store."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite
import structlog

from hauba.core.constants import DB_FILE

logger = structlog.get_logger()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    namespace TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(namespace, key)
);

CREATE TABLE IF NOT EXISTS task_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL UNIQUE,
    instruction TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    result TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    completed_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    source TEXT DEFAULT '',
    task_id TEXT DEFAULT '',
    timestamp TEXT NOT NULL
);
"""


class MemoryStore:
    """Async SQLite memory store for Hauba."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DB_FILE
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        """Initialize the database and create tables."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        await self._db.executescript(_SCHEMA)
        await self._db.commit()
        logger.info("memory.initialized", path=str(self._db_path))

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    async def _ensure_db(self) -> aiosqlite.Connection:
        if self._db is None:
            await self.init()
        assert self._db is not None
        return self._db

    # --- Key-Value Memory ---

    async def set(self, namespace: str, key: str, value: str) -> None:
        """Set a memory value."""
        db = await self._ensure_db()
        now = datetime.now(UTC).isoformat()
        await db.execute(
            "INSERT INTO memory (namespace, key, value, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(namespace, key) DO UPDATE SET value=?, updated_at=?",
            (namespace, key, value, now, now, value, now),
        )
        await db.commit()

    async def get(self, namespace: str, key: str) -> str | None:
        """Get a memory value."""
        db = await self._ensure_db()
        async with db.execute(
            "SELECT value FROM memory WHERE namespace=? AND key=?",
            (namespace, key),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def list_keys(self, namespace: str) -> list[str]:
        """List all keys in a namespace."""
        db = await self._ensure_db()
        async with db.execute(
            "SELECT key FROM memory WHERE namespace=? ORDER BY key",
            (namespace,),
        ) as cursor:
            return [row[0] async for row in cursor]

    # --- Task History ---

    async def save_task(self, task_id: str, instruction: str, status: str = "pending") -> None:
        """Save a task to history."""
        db = await self._ensure_db()
        now = datetime.now(UTC).isoformat()
        await db.execute(
            "INSERT OR REPLACE INTO task_history (task_id, instruction, status, created_at) "
            "VALUES (?, ?, ?, ?)",
            (task_id, instruction, status, now),
        )
        await db.commit()

    async def update_task(self, task_id: str, status: str, result: str = "") -> None:
        """Update task status and result."""
        db = await self._ensure_db()
        now = datetime.now(UTC).isoformat()
        await db.execute(
            "UPDATE task_history SET status=?, result=?, completed_at=? WHERE task_id=?",
            (status, result, now, task_id),
        )
        await db.commit()

    async def get_recent_tasks(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent tasks."""
        db = await self._ensure_db()
        async with db.execute(
            "SELECT task_id, instruction, status, result, created_at, completed_at "
            "FROM task_history ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "task_id": r[0],
                    "instruction": r[1],
                    "status": r[2],
                    "result": r[3],
                    "created_at": r[4],
                    "completed_at": r[5],
                }
                for r in rows
            ]
