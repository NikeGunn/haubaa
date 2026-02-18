"""Replay recorder — subscribes to all events and writes JSON Lines."""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from hauba.core.constants import AGENTS_DIR
from hauba.core.events import EventEmitter
from hauba.core.types import Event, ReplayEntry

logger = structlog.get_logger()


class ReplayRecorder:
    """Records all events to a .hauba-replay JSON Lines file.

    Subscribe to ``*`` (wildcard) on an EventEmitter to capture every event.
    Each line is a JSON-serialized ReplayEntry.
    """

    def __init__(self, task_id: str, output_dir: Path | None = None) -> None:
        self.task_id = task_id
        self._dir = output_dir or (AGENTS_DIR / task_id)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / ".hauba-replay"
        self._file = open(self._path, "a", encoding="utf-8")
        self._entry_count = 0

    @property
    def path(self) -> Path:
        return self._path

    @property
    def entry_count(self) -> int:
        return self._entry_count

    async def handle_event(self, event: Event) -> None:
        """Event handler — write event as JSON line."""
        entry = ReplayEntry(
            timestamp=event.timestamp,
            topic=event.topic,
            data=event.data,
            source=event.source,
            task_id=event.task_id,
        )
        line = entry.model_dump_json()
        self._file.write(line + "\n")
        self._file.flush()
        self._entry_count += 1

    def subscribe(self, events: EventEmitter) -> None:
        """Subscribe to all events on the emitter."""
        events.on("*", self.handle_event)

    def close(self) -> None:
        """Close the replay file."""
        if self._file and not self._file.closed:
            self._file.close()
            logger.info(
                "replay.closed",
                path=str(self._path),
                entries=self._entry_count,
            )

    @staticmethod
    def load(path: Path) -> list[ReplayEntry]:
        """Load replay entries from a .hauba-replay file."""
        entries: list[ReplayEntry] = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                entries.append(ReplayEntry.model_validate(data))
        return entries
