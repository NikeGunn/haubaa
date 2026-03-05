"""Tests for EmailService (Brevo API + SMTP fallback)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hauba.services.email import EmailService


class TestConfigure:
    """Test EmailService.configure()."""

    def test_missing_all_vars(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            service = EmailService()
            assert service.configure() is False
            assert service.is_configured is False
            assert service.mode == ""

    def test_brevo_configured(self) -> None:
        env = {
            "HAUBA_EMAIL_API_KEY": "xkeysib-abc123",
            "HAUBA_EMAIL_FROM": "noreply@hauba.tech",
        }
        with patch.dict("os.environ", env, clear=True):
            service = EmailService()
            assert service.configure() is True
            assert service.is_configured is True
            assert service.mode == "brevo"

    def test_brevo_with_name(self) -> None:
        env = {
            "HAUBA_EMAIL_API_KEY": "xkeysib-abc123",
            "HAUBA_EMAIL_FROM": "noreply@hauba.tech",
            "HAUBA_EMAIL_FROM_NAME": "My Agent",
        }
        with patch.dict("os.environ", env, clear=True):
            service = EmailService()
            service.configure()
            assert service._from_name == "My Agent"

    def test_brevo_missing_from(self) -> None:
        env = {"HAUBA_EMAIL_API_KEY": "xkeysib-abc123"}
        with patch.dict("os.environ", env, clear=True):
            service = EmailService()
            # Falls through to SMTP check, which also fails
            assert service.configure() is False

    def test_smtp_fallback(self) -> None:
        env = {
            "HAUBA_SMTP_HOST": "smtp.gmail.com",
            "HAUBA_SMTP_USER": "user@gmail.com",
            "HAUBA_SMTP_PASS": "app-password",
        }
        with patch.dict("os.environ", env, clear=True):
            service = EmailService()
            assert service.configure() is True
            assert service.mode == "smtp"

    def test_smtp_custom_port(self) -> None:
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
            assert service._smtp_port == 465
            assert service._from_email == "noreply@example.com"

    def test_brevo_takes_priority_over_smtp(self) -> None:
        env = {
            "HAUBA_EMAIL_API_KEY": "xkeysib-abc123",
            "HAUBA_EMAIL_FROM": "noreply@hauba.tech",
            "HAUBA_SMTP_HOST": "smtp.gmail.com",
            "HAUBA_SMTP_USER": "user@gmail.com",
            "HAUBA_SMTP_PASS": "pass",
        }
        with patch.dict("os.environ", env, clear=True):
            service = EmailService()
            service.configure()
            assert service.mode == "brevo"


class TestSendBrevo:
    """Test Brevo API email sending."""

    @pytest.mark.asyncio
    async def test_send_not_configured(self) -> None:
        service = EmailService()
        result = await service.send("to@example.com", "Subject", "Body")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_brevo_success(self) -> None:
        env = {
            "HAUBA_EMAIL_API_KEY": "xkeysib-abc123",
            "HAUBA_EMAIL_FROM": "noreply@hauba.tech",
        }
        with patch.dict("os.environ", env, clear=True):
            service = EmailService()
            service.configure()

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.text = '{"messageId": "123"}'

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("hauba.services.email.httpx.AsyncClient", return_value=mock_client):
            result = await service.send("to@test.com", "Hello", "Body text")
            assert result is True

    @pytest.mark.asyncio
    async def test_send_brevo_with_cc_bcc(self) -> None:
        env = {
            "HAUBA_EMAIL_API_KEY": "xkeysib-abc123",
            "HAUBA_EMAIL_FROM": "noreply@hauba.tech",
        }
        with patch.dict("os.environ", env, clear=True):
            service = EmailService()
            service.configure()

        mock_response = MagicMock()
        mock_response.status_code = 201

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("hauba.services.email.httpx.AsyncClient", return_value=mock_client):
            result = await service.send(
                "to@test.com",
                "Hello",
                "Body",
                cc="cc@test.com",
                bcc="bcc@test.com",
            )
            assert result is True

            # Verify payload included cc and bcc
            call_kwargs = mock_client.post.call_args
            payload = call_kwargs.kwargs.get("json", call_kwargs[1].get("json", {}))
            assert payload.get("cc") == [{"email": "cc@test.com"}]
            assert payload.get("bcc") == [{"email": "bcc@test.com"}]

    @pytest.mark.asyncio
    async def test_send_brevo_api_error(self) -> None:
        env = {
            "HAUBA_EMAIL_API_KEY": "xkeysib-bad",
            "HAUBA_EMAIL_FROM": "noreply@hauba.tech",
        }
        with patch.dict("os.environ", env, clear=True):
            service = EmailService()
            service.configure()

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("hauba.services.email.httpx.AsyncClient", return_value=mock_client):
            result = await service.send("to@test.com", "Hello", "Body")
            assert result is False

    @pytest.mark.asyncio
    async def test_send_brevo_network_error(self) -> None:
        env = {
            "HAUBA_EMAIL_API_KEY": "xkeysib-abc123",
            "HAUBA_EMAIL_FROM": "noreply@hauba.tech",
        }
        with patch.dict("os.environ", env, clear=True):
            service = EmailService()
            service.configure()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))

        with patch("hauba.services.email.httpx.AsyncClient", return_value=mock_client):
            result = await service.send("to@test.com", "Hello", "Body")
            assert result is False


class TestSendHtml:
    """Test HTML email sending."""

    @pytest.mark.asyncio
    async def test_send_html_brevo(self) -> None:
        env = {
            "HAUBA_EMAIL_API_KEY": "xkeysib-abc123",
            "HAUBA_EMAIL_FROM": "noreply@hauba.tech",
        }
        with patch.dict("os.environ", env, clear=True):
            service = EmailService()
            service.configure()

        mock_response = MagicMock()
        mock_response.status_code = 201

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("hauba.services.email.httpx.AsyncClient", return_value=mock_client):
            result = await service.send_html("to@test.com", "Subject", "<h1>Hello</h1>")
            assert result is True

            call_kwargs = mock_client.post.call_args
            payload = call_kwargs.kwargs.get("json", call_kwargs[1].get("json", {}))
            assert "htmlContent" in payload

    @pytest.mark.asyncio
    async def test_send_html_not_configured(self) -> None:
        service = EmailService()
        result = await service.send_html("to@test.com", "Subject", "<p>body</p>")
        assert result is False


class TestSmtpFallback:
    """Test SMTP fallback sending."""

    @pytest.mark.asyncio
    async def test_send_smtp(self) -> None:
        env = {
            "HAUBA_SMTP_HOST": "smtp.test.com",
            "HAUBA_SMTP_USER": "user@test.com",
            "HAUBA_SMTP_PASS": "pass",
        }
        with patch.dict("os.environ", env, clear=True):
            service = EmailService()
            service.configure()

        with patch.object(service, "_smtp_send", return_value=True):
            result = await service.send("to@test.com", "Hello", "Body text")
            assert result is True

    @pytest.mark.asyncio
    async def test_send_smtp_failure(self) -> None:
        env = {
            "HAUBA_SMTP_HOST": "smtp.test.com",
            "HAUBA_SMTP_USER": "user@test.com",
            "HAUBA_SMTP_PASS": "pass",
        }
        with patch.dict("os.environ", env, clear=True):
            service = EmailService()
            service.configure()

        with patch.object(service, "_smtp_send", return_value=False):
            result = await service.send("to@test.com", "Hello", "Body")
            assert result is False
