"""Tests for EventEmitter."""

from __future__ import annotations

import pytest

from hauba.core.events import EventEmitter
from hauba.core.types import Event


@pytest.mark.asyncio
async def test_emit_and_receive() -> None:
    emitter = EventEmitter()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    emitter.on("test.topic", handler)
    await emitter.emit("test.topic", {"key": "value"})

    assert len(received) == 1
    assert received[0].topic == "test.topic"
    assert received[0].data["key"] == "value"


@pytest.mark.asyncio
async def test_wildcard_handler() -> None:
    emitter = EventEmitter()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    emitter.on("*", handler)
    await emitter.emit("any.topic", {"x": 1})
    await emitter.emit("other.topic", {"x": 2})

    assert len(received) == 2


@pytest.mark.asyncio
async def test_unsubscribe() -> None:
    emitter = EventEmitter()
    count = 0

    async def handler(event: Event) -> None:
        nonlocal count
        count += 1

    emitter.on("test", handler)
    await emitter.emit("test")
    emitter.off("test", handler)
    await emitter.emit("test")

    assert count == 1


@pytest.mark.asyncio
async def test_history() -> None:
    emitter = EventEmitter()
    await emitter.emit("a", {"n": 1})
    await emitter.emit("b", {"n": 2})
    await emitter.emit("a", {"n": 3})

    all_events = emitter.get_history()
    assert len(all_events) == 3

    a_events = emitter.get_history(topic="a")
    assert len(a_events) == 2


@pytest.mark.asyncio
async def test_handler_error_doesnt_break_others() -> None:
    emitter = EventEmitter()
    results: list[str] = []

    async def bad_handler(event: Event) -> None:
        raise ValueError("boom")

    async def good_handler(event: Event) -> None:
        results.append("ok")

    emitter.on("test", bad_handler)
    emitter.on("test", good_handler)
    await emitter.emit("test")

    assert results == ["ok"]
