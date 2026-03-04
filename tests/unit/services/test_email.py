"""Tests for EmailService."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from hauba.services.email import EmailService


class TestConfigure:
    """Test EmailService.configure()."""

    def test_missing_all_vars(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            service = EmailService()
            assert service.configure() is False
            assert service.is_configured is False

    def test_missing_host(self) -> None:
        env = {
            "HAUBA_SMTP_USER": "user@example.com",
            "HAUBA_SMTP_PASS": "password123",
        }
        with patch.dict("os.environ", env, clear=True):
            service = EmailService()
            assert service.configure() is False

    def test_all_vars_present(self) -> None:
        env = {
            "HAUBA_SMTP_HOST": "smtp.gmail.com",
            "HAUBA_SMTP_USER": "user@gmail.com",
            "HAUBA_SMTP_PASS": "app-password",
        }
        with patch.dict("os.environ", env, clear=True):
            service = EmailService()
            assert service.configure() is True
            assert service.is_configured is True

    def test_custom_port_and_from(self) -> None:
        env = {
            "HAUBA_SMTP_HOST": "smtp.example.com",
            "HAUBA_SMTP_PORT": "465",
            "HAUBA_SMTP_USER": "user@example.com",
            "HAUBA_SMTP_PASS": "pass",
            "HAUBA_EMAIL_FROM": "noreply@example.com",
        }
        with patch.dict("os.environ", env, clear=True):
            service = EmailService()
            service.configure()
            assert service._port == 465
            assert service._from_addr == "noreply@example.com"


class TestSend:
    """Test EmailService.send()."""

    @pytest.mark.asyncio
    async def test_send_not_configured(self) -> None:
        service = EmailService()
        result = await service.send("to@example.com", "Subject", "Body")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_success(self) -> None:
        env = {
            "HAUBA_SMTP_HOST": "smtp.test.com",
            "HAUBA_SMTP_USER": "user@test.com",
            "HAUBA_SMTP_PASS": "pass",
        }
        with patch.dict("os.environ", env, clear=True):
            service = EmailService()
            service.configure()

        with patch.object(service, "_send_sync", return_value=True):
            result = await service.send("to@test.com", "Hello", "Body text")
            assert result is True

    @pytest.mark.asyncio
    async def test_send_with_cc_bcc(self) -> None:
        env = {
            "HAUBA_SMTP_HOST": "smtp.test.com",
            "HAUBA_SMTP_USER": "user@test.com",
            "HAUBA_SMTP_PASS": "pass",
        }
        with patch.dict("os.environ", env, clear=True):
            service = EmailService()
            service.configure()

        with patch.object(service, "_send_sync", return_value=True):
            result = await service.send(
                "to@test.com", "Hello", "Body", cc="cc@test.com", bcc="bcc@test.com"
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_send_failure(self) -> None:
        env = {
            "HAUBA_SMTP_HOST": "smtp.test.com",
            "HAUBA_SMTP_USER": "user@test.com",
            "HAUBA_SMTP_PASS": "pass",
        }
        with patch.dict("os.environ", env, clear=True):
            service = EmailService()
            service.configure()

        with patch.object(service, "_send_sync", side_effect=Exception("SMTP error")):
            result = await service.send("to@test.com", "Hello", "Body")
            assert result is False
