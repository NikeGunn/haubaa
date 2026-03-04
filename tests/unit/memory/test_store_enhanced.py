"""Tests for enhanced MemoryStore (V4.0 — TTL, compaction, stats)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hauba.memory.store import MemoryStore


@pytest.fixture
async def store(tmp_path: Path) -> MemoryStore:
    db_path = tmp_path / "test.db"
    s = MemoryStore(db_path=db_path)
    await s.init()
    return s


class TestSetWithTTL:
    """Test MemoryStore.set_with_ttl()."""

    @pytest.mark.asyncio
    async def test_set_and_get(self, store: MemoryStore) -> None:
        await store.set_with_ttl("cache", "key1", "value1", ttl_seconds=3600)
        result = await store.get("cache", "key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_expired_entry_cleaned(self, store: MemoryStore) -> None:
        # Set with TTL of 0 seconds (already expired)
        await store.set_with_ttl("cache", "old_key", "old_value", ttl_seconds=0)
        # Cleanup should remove it
        import asyncio

        await asyncio.sleep(0.1)
        removed = await store._cleanup_expired()
        assert removed >= 1


class TestGetOrDefault:
    """Test MemoryStore.get_or_default()."""

    @pytest.mark.asyncio
    async def test_returns_value_when_exists(self, store: MemoryStore) -> None:
        await store.set("ns", "k", "v")
        result = await store.get_or_default("ns", "k", "default")
        assert result == "v"

    @pytest.mark.asyncio
    async def test_returns_default_when_missing(self, store: MemoryStore) -> None:
        result = await store.get_or_default("ns", "missing", "fallback")
        assert result == "fallback"


class TestListValues:
    """Test MemoryStore.list_values()."""

    @pytest.mark.asyncio
    async def test_list_values(self, store: MemoryStore) -> None:
        await store.set("ns", "a", "1")
        await store.set("ns", "b", "2")
        values = await store.list_values("ns")
        assert len(values) == 2
        keys = {v["key"] for v in values}
        assert keys == {"a", "b"}

    @pytest.mark.asyncio
    async def test_list_values_empty(self, store: MemoryStore) -> None:
        values = await store.list_values("empty")
        assert values == []


class TestDelete:
    """Test MemoryStore.delete()."""

    @pytest.mark.asyncio
    async def test_delete_existing(self, store: MemoryStore) -> None:
        await store.set("ns", "k", "v")
        await store.delete("ns", "k")
        result = await store.get("ns", "k")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, store: MemoryStore) -> None:
        # Should not raise
        await store.delete("ns", "nonexistent")


class TestCompact:
    """Test MemoryStore.compact()."""

    @pytest.mark.asyncio
    async def test_compact_removes_oldest(self, store: MemoryStore) -> None:
        for i in range(20):
            await store.set("compact-ns", f"key-{i}", f"val-{i}")

        removed = await store.compact("compact-ns", max_entries=10)
        assert removed == 10

        # Verify we kept the 10 most recent
        values = await store.list_values("compact-ns")
        assert len(values) == 10

    @pytest.mark.asyncio
    async def test_compact_no_op_when_under_limit(self, store: MemoryStore) -> None:
        await store.set("ns", "k1", "v1")
        removed = await store.compact("ns", max_entries=100)
        assert removed == 0


class TestGetStats:
    """Test MemoryStore.get_stats()."""

    @pytest.mark.asyncio
    async def test_stats_by_namespace(self, store: MemoryStore) -> None:
        await store.set("ns1", "a", "1")
        await store.set("ns1", "b", "2")
        await store.set("ns2", "x", "3")

        stats = await store.get_stats()
        assert stats.get("ns1") == 2
        assert stats.get("ns2") == 1
