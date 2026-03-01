"""Tests for the Hauba daemon agent."""

from __future__ import annotations

import pytest

from hauba.daemon.agent import DEFAULT_POLL_INTERVAL, DEFAULT_SERVER_URL, HaubaDaemon


class TestHaubaDaemon:
    """Tests for the HaubaDaemon class."""

    def test_init_defaults(self) -> None:
        daemon = HaubaDaemon(owner_id="test-owner")
        assert daemon.owner_id == "test-owner"
        assert daemon._server_url == DEFAULT_SERVER_URL
        assert daemon._poll_interval == DEFAULT_POLL_INTERVAL
        assert daemon.is_running is False

    def test_init_custom_params(self) -> None:
        daemon = HaubaDaemon(
            owner_id="whatsapp:+1234",
            server_url="http://localhost:8080",
            poll_interval=30.0,
            workspace="/tmp/test-workspace",
        )
        assert daemon.owner_id == "whatsapp:+1234"
        assert daemon._server_url == "http://localhost:8080"
        assert daemon._poll_interval == 30.0
        assert daemon._workspace == "/tmp/test-workspace"

    def test_server_url_trailing_slash_stripped(self) -> None:
        daemon = HaubaDaemon(
            owner_id="test",
            server_url="https://hauba.tech/",
        )
        assert daemon._server_url == "https://hauba.tech"

    def test_not_running_by_default(self) -> None:
        daemon = HaubaDaemon(owner_id="test")
        assert daemon.is_running is False

    @pytest.mark.asyncio
    async def test_stop_when_not_started(self) -> None:
        daemon = HaubaDaemon(owner_id="test")
        # Should not raise
        await daemon.stop()
        assert daemon.is_running is False

    @pytest.mark.asyncio
    async def test_stop_clears_state(self) -> None:
        daemon = HaubaDaemon(owner_id="test")
        daemon._running = True  # Simulate started
        await daemon.stop()
        assert daemon.is_running is False
        assert daemon._http is None
