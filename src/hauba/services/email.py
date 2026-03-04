"""Email service — send emails on owner's behalf via SMTP."""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

logger = structlog.get_logger()


class EmailService:
    """Send emails via SMTP on owner's behalf.

    Configuration via environment variables:
        HAUBA_SMTP_HOST  — SMTP server hostname (e.g., smtp.gmail.com)
        HAUBA_SMTP_PORT  — SMTP port (default: 587)
        HAUBA_SMTP_USER  — SMTP username / email
        HAUBA_SMTP_PASS  — SMTP password / app password
        HAUBA_EMAIL_FROM — From address (defaults to SMTP_USER)

    For Gmail: use an App Password (not your real password).
    For Outlook: use smtp-mail.outlook.com:587.

    Usage:
        service = EmailService()
        if service.configure():
            await service.send("user@example.com", "Hello", "Body text")
    """

    def __init__(self) -> None:
        self._host: str = ""
        self._port: int = 587
        self._user: str = ""
        self._password: str = ""
        self._from_addr: str = ""
        self._configured: bool = False

    def configure(self) -> bool:
        """Load SMTP configuration from environment variables.

        Returns True if all required vars are present.
        """
        self._host = os.environ.get("HAUBA_SMTP_HOST", "")
        self._port = int(os.environ.get("HAUBA_SMTP_PORT", "587"))
        self._user = os.environ.get("HAUBA_SMTP_USER", "")
        self._password = os.environ.get("HAUBA_SMTP_PASS", "")
        self._from_addr = os.environ.get("HAUBA_EMAIL_FROM", self._user)

        if not self._host or not self._user or not self._password:
            logger.info(
                "email.not_configured",
                has_host=bool(self._host),
                has_user=bool(self._user),
                has_pass=bool(self._password),
            )
            self._configured = False
            return False

        self._configured = True
        logger.info("email.configured", host=self._host, user=self._user)
        return True

    @property
    def is_configured(self) -> bool:
        """Whether the email service is configured."""
        return self._configured

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

        msg = MIMEMultipart()
        msg["From"] = self._from_addr
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

        try:
            # Use sync smtplib (stdlib, always available)
            # aiosmtplib is optional enhancement
            return self._send_sync(msg, recipients)
        except Exception as exc:
            logger.error("email.send_failed", to=to, error=str(exc))
            return False

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

        msg = MIMEMultipart("alternative")
        msg["From"] = self._from_addr
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            return self._send_sync(msg, [to])
        except Exception as exc:
            logger.error("email.send_html_failed", to=to, error=str(exc))
            return False

    def _send_sync(self, msg: MIMEMultipart, recipients: list[str]) -> bool:
        """Send email via stdlib smtplib (synchronous, wrapped in async)."""
        try:
            with smtplib.SMTP(self._host, self._port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self._user, self._password)
                server.sendmail(self._from_addr, recipients, msg.as_string())

            logger.info("email.sent", to=recipients[0], subject=msg["Subject"])
            return True
        except smtplib.SMTPAuthenticationError:
            logger.error("email.auth_failed", user=self._user)
            return False
        except smtplib.SMTPException as exc:
            logger.error("email.smtp_error", error=str(exc))
            return False
