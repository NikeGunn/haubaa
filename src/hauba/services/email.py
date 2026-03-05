"""Email service — send emails via Brevo API (free, no credit card required).

Brevo (formerly Sendinblue) offers 300 emails/day for free with no credit card.
This replaces the SMTP-based approach so the Hauba owner pays nothing.

Configuration via environment variables:
    HAUBA_EMAIL_API_KEY  — Brevo API key (get free at brevo.com)
    HAUBA_EMAIL_FROM     — Sender email address (must be verified in Brevo)
    HAUBA_EMAIL_FROM_NAME — Sender display name (default: "Hauba AI")

Fallback: If HAUBA_SMTP_* vars are set, uses SMTP (Gmail, Outlook, etc.)
"""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

# Brevo API endpoint
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


class EmailService:
    """Send emails via Brevo API (free tier) or SMTP fallback.

    Priority:
    1. Brevo API (HAUBA_EMAIL_API_KEY) — free, 300/day, no credit card
    2. SMTP fallback (HAUBA_SMTP_*) — Gmail/Outlook app passwords

    Usage:
        service = EmailService()
        if service.configure():
            await service.send("user@example.com", "Hello", "Body text")
    """

    def __init__(self) -> None:
        # Brevo API config
        self._brevo_api_key: str = ""
        self._from_email: str = ""
        self._from_name: str = "Hauba AI"

        # SMTP fallback config
        self._smtp_host: str = ""
        self._smtp_port: int = 587
        self._smtp_user: str = ""
        self._smtp_password: str = ""

        self._configured: bool = False
        self._mode: str = ""  # "brevo" or "smtp"

    def configure(self) -> bool:
        """Load configuration from environment variables.

        Tries Brevo API first, then SMTP fallback.
        Returns True if any email method is configured.
        """
        # Try Brevo API first (free, preferred)
        self._brevo_api_key = os.environ.get("HAUBA_EMAIL_API_KEY", "")
        self._from_email = os.environ.get("HAUBA_EMAIL_FROM", "")
        self._from_name = os.environ.get("HAUBA_EMAIL_FROM_NAME", "Hauba AI")

        if self._brevo_api_key and self._from_email:
            self._configured = True
            self._mode = "brevo"
            logger.info(
                "email.configured",
                mode="brevo",
                from_email=self._from_email,
            )
            return True

        # Fallback: SMTP
        self._smtp_host = os.environ.get("HAUBA_SMTP_HOST", "")
        self._smtp_port = int(os.environ.get("HAUBA_SMTP_PORT", "587"))
        self._smtp_user = os.environ.get("HAUBA_SMTP_USER", "")
        self._smtp_password = os.environ.get("HAUBA_SMTP_PASS", "")

        if not self._from_email:
            self._from_email = self._smtp_user

        if self._smtp_host and self._smtp_user and self._smtp_password:
            self._configured = True
            self._mode = "smtp"
            logger.info(
                "email.configured",
                mode="smtp",
                host=self._smtp_host,
            )
            return True

        logger.info(
            "email.not_configured",
            has_brevo_key=bool(self._brevo_api_key),
            has_from=bool(self._from_email),
            has_smtp=bool(self._smtp_host),
        )
        self._configured = False
        return False

    @property
    def is_configured(self) -> bool:
        """Whether the email service is configured."""
        return self._configured

    @property
    def mode(self) -> str:
        """Current email delivery mode: 'brevo', 'smtp', or ''."""
        return self._mode

    async def send(
        self,
        to: str,
        subject: str,
        body: str,
        *,
        cc: str = "",
        bcc: str = "",
        reply_to: str = "",
    ) -> bool:
        """Send a plain text email.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            body: Plain text email body.
            cc: CC address (optional).
            bcc: BCC address (optional).
            reply_to: Reply-to address (optional).

        Returns True if sent successfully.
        """
        if not self._configured:
            logger.warning("email.not_configured")
            return False

        if self._mode == "brevo":
            return await self._send_brevo(
                to=to,
                subject=subject,
                body=body,
                html_body=None,
                cc=cc,
                bcc=bcc,
                reply_to=reply_to,
            )
        else:
            return self._send_smtp(
                to=to,
                subject=subject,
                body=body,
                cc=cc,
                bcc=bcc,
                reply_to=reply_to,
            )

    async def send_html(
        self,
        to: str,
        subject: str,
        html_body: str,
    ) -> bool:
        """Send an HTML email.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            html_body: HTML email body.

        Returns True if sent successfully.
        """
        if not self._configured:
            return False

        if self._mode == "brevo":
            return await self._send_brevo(
                to=to,
                subject=subject,
                body=None,
                html_body=html_body,
            )
        else:
            return self._send_smtp_html(to=to, subject=subject, html_body=html_body)

    async def _send_brevo(
        self,
        to: str,
        subject: str,
        body: str | None = None,
        html_body: str | None = None,
        cc: str = "",
        bcc: str = "",
        reply_to: str = "",
    ) -> bool:
        """Send email via Brevo API (free tier: 300/day)."""
        payload: dict[str, Any] = {
            "sender": {
                "name": self._from_name,
                "email": self._from_email,
            },
            "to": [{"email": to}],
            "subject": subject,
        }

        if html_body:
            payload["htmlContent"] = html_body
        elif body:
            payload["textContent"] = body
        else:
            payload["textContent"] = ""

        if cc:
            payload["cc"] = [{"email": cc}]
        if bcc:
            payload["bcc"] = [{"email": bcc}]
        if reply_to:
            payload["replyTo"] = {"email": reply_to}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    BREVO_API_URL,
                    json=payload,
                    headers={
                        "api-key": self._brevo_api_key,
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                )

            if resp.status_code in (200, 201):
                logger.info("email.sent", to=to, subject=subject, mode="brevo")
                return True

            logger.error(
                "email.brevo_error",
                status=resp.status_code,
                body=resp.text[:300],
            )
            return False

        except Exception as exc:
            logger.error("email.send_failed", to=to, error=str(exc), mode="brevo")
            return False

    def _send_smtp(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str = "",
        bcc: str = "",
        reply_to: str = "",
    ) -> bool:
        """Send plain text email via SMTP (fallback)."""
        msg = MIMEMultipart()
        msg["From"] = self._from_email or self._smtp_user
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        if reply_to:
            msg["Reply-To"] = reply_to

        msg.attach(MIMEText(body, "plain", "utf-8"))

        recipients = [to]
        if cc:
            recipients.append(cc)
        if bcc:
            recipients.append(bcc)

        return self._smtp_send(msg, recipients)

    def _send_smtp_html(
        self,
        to: str,
        subject: str,
        html_body: str,
    ) -> bool:
        """Send HTML email via SMTP (fallback)."""
        msg = MIMEMultipart("alternative")
        msg["From"] = self._from_email or self._smtp_user
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        return self._smtp_send(msg, [to])

    def _smtp_send(self, msg: MIMEMultipart, recipients: list[str]) -> bool:
        """Send email via stdlib smtplib."""
        try:
            with smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self._smtp_user, self._smtp_password)
                server.sendmail(
                    self._from_email or self._smtp_user,
                    recipients,
                    msg.as_string(),
                )

            logger.info("email.sent", to=recipients[0], subject=msg["Subject"], mode="smtp")
            return True
        except smtplib.SMTPAuthenticationError:
            logger.error("email.auth_failed", user=self._smtp_user)
            return False
        except smtplib.SMTPException as exc:
            logger.error("email.smtp_error", error=str(exc))
            return False
        except Exception as exc:
            logger.error("email.send_failed", error=str(exc), mode="smtp")
            return False
