"""Tests for MemoryStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from hauba.memory.store import MemoryStore


@pytest.fixture
async def store(tmp_path: Path) -> MemoryStore:
    s = MemoryStore(db_path=tmp_path / "test.db")
    await s.init()
    return s


@pytest.mark.asyncio
async def test_set_and_get(store: MemoryStore) -> None:
    await store.set("test", "key1", "value1")
    val = await store.get("test", "key1")
    assert val == "value1"


@pytest.mark.asyncio
async def test_get_missing(store: MemoryStore) -> None:
    val = await store.get("test", "missing")
    assert val is None


@pytest.mark.asyncio
async def test_overwrite(store: MemoryStore) -> None:
    await store.set("ns", "k", "v1")
    await store.set("ns", "k", "v2")
    val = await store.get("ns", "k")
    assert val == "v2"


@pytest.mark.asyncio
async def test_list_keys(store: MemoryStore) -> None:
    await store.set("ns", "a", "1")
    await store.set("ns", "b", "2")
    keys = await store.list_keys("ns")
    assert keys == ["a", "b"]


@pytest.mark.asyncio
async def test_task_history(store: MemoryStore) -> None:
    await store.save_task("t1", "build an app")
    await store.update_task("t1", "completed", "done")
    tasks = await store.get_recent_tasks()
    assert len(tasks) == 1
    assert tasks[0]["status"] == "completed"
