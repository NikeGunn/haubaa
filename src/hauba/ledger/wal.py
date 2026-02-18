"""Write-Ahead Log (WAL) for crash-safe ledger state persistence.

Append-only log that records every state change. On crash recovery,
replay the WAL to reconstruct the exact ledger state.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


class WALEntry:
    """A single entry in the write-ahead log."""

    __slots__ = ("data", "operation", "sequence", "task_id", "timestamp")

    def __init__(
        self,
        sequence: int,
        operation: str,
        task_id: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.sequence = sequence
        self.timestamp = time.time()
        self.operation = operation
        self.task_id = task_id
        self.data = data or {}

    def to_json(self) -> str:
        return json.dumps({
            "seq": self.sequence,
            "ts": self.timestamp,
            "op": self.operation,
            "task_id": self.task_id,
            "data": self.data,
        })

    @classmethod
    def from_json(cls, line: str) -> WALEntry:
        d = json.loads(line)
        entry = cls(
            sequence=d["seq"],
            operation=d["op"],
            task_id=d["task_id"],
            data=d.get("data", {}),
        )
        entry.timestamp = d["ts"]
        return entry


# WAL operations
WAL_OP_ADD_TASK = "add_task"
WAL_OP_START_TASK = "start_task"
WAL_OP_COMPLETE_TASK = "complete_task"
WAL_OP_CHECKPOINT = "checkpoint"


class WriteAheadLog:
    """Append-only write-ahead log for crash recovery.

    Every ledger mutation is recorded here BEFORE being applied.
    On recovery, replay from last checkpoint.
    """

    def __init__(self, wal_path: Path) -> None:
        self._path = wal_path
        self._sequence: int = 0
        self._checkpoint_seq: int = 0
        self._entries: list[WALEntry] = []

        # Load existing WAL if present
        if self._path.exists():
            self._load()

    def append(self, operation: str, task_id: str, data: dict[str, Any] | None = None) -> WALEntry:
        """Append a new entry to the WAL. Flushes to disk immediately."""
        self._sequence += 1
        entry = WALEntry(self._sequence, operation, task_id, data)
        self._entries.append(entry)
        self._flush_entry(entry)
        return entry

    def checkpoint(self) -> None:
        """Create a checkpoint. Entries before this can be compacted."""
        self._sequence += 1
        entry = WALEntry(self._sequence, WAL_OP_CHECKPOINT, "", {"checkpoint_at": time.time()})
        self._entries.append(entry)
        self._flush_entry(entry)
        self._checkpoint_seq = self._sequence
        logger.info("wal.checkpoint", sequence=self._sequence, path=str(self._path))

    def replay_from_checkpoint(self) -> list[WALEntry]:
        """Get all entries since the last checkpoint for replay."""
        entries = []
        past_checkpoint = self._checkpoint_seq == 0  # No checkpoint = replay all

        for entry in self._entries:
            if entry.operation == WAL_OP_CHECKPOINT:
                past_checkpoint = True
                continue
            if past_checkpoint:
                entries.append(entry)

        return entries

    def replay_all(self) -> list[WALEntry]:
        """Get all non-checkpoint entries for full replay."""
        return [e for e in self._entries if e.operation != WAL_OP_CHECKPOINT]

    def compact(self) -> None:
        """Remove entries before the last checkpoint and rewrite the WAL file."""
        if self._checkpoint_seq == 0:
            return

        # Keep only entries after last checkpoint
        new_entries = []
        past_checkpoint = False
        for entry in self._entries:
            if entry.operation == WAL_OP_CHECKPOINT:
                past_checkpoint = True
                continue
            if past_checkpoint:
                new_entries.append(entry)

        self._entries = new_entries
        self._rewrite()
        logger.info("wal.compacted", remaining=len(self._entries))

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def sequence(self) -> int:
        return self._sequence

    # ── Internal ───────────────────────────────────────────────────────

    def _flush_entry(self, entry: WALEntry) -> None:
        """Append a single entry to the WAL file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(entry.to_json() + "\n")

    def _rewrite(self) -> None:
        """Rewrite the entire WAL file (after compaction)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            for entry in self._entries:
                f.write(entry.to_json() + "\n")

    def _load(self) -> None:
        """Load existing WAL entries from disk."""
        try:
            with open(self._path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = WALEntry.from_json(line)
                    self._entries.append(entry)
                    self._sequence = max(self._sequence, entry.sequence)
                    if entry.operation == WAL_OP_CHECKPOINT:
                        self._checkpoint_seq = entry.sequence
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("wal.load_error", error=str(exc), path=str(self._path))

    def __repr__(self) -> str:
        return f"<WAL entries={self.entry_count} seq={self._sequence}>"
