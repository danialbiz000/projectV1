"""Pluggable outbound email (M6).

No real mailbox/SMTP credentials are available in this development
environment — the same limitation documented for the data adapters in
docs/INTEGRATIONS.md. By default every message goes through the console
adapter (logged, not delivered); setting REMIP_SMTP_HOST switches to real
SMTP delivery once credentials exist. Callers never need to know which
adapter is active.
"""
from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage

from app.core.config import Settings, get_settings

logger = logging.getLogger("remip.email")


@dataclass
class EmailMessage:
    to: str
    subject: str
    body: str


def send_email(message: EmailMessage) -> None:
    settings = get_settings()
    if settings.smtp_host:
        _send_smtp(message, settings)
        return
    logger.info(
        "EMAIL (console adapter — no SMTP configured, see REMIP_SMTP_HOST) "
        "to=%s subject=%r\n%s",
        message.to,
        message.subject,
        message.body,
    )


def _send_smtp(message: EmailMessage, settings: Settings) -> None:
    assert settings.smtp_host  # narrows for mypy; caller already checked truthiness
    mime = MimeMessage()
    mime["From"] = settings.smtp_from
    mime["To"] = message.to
    mime["Subject"] = message.subject
    mime.set_content(message.body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
        if settings.smtp_user:
            client.starttls()
            client.login(settings.smtp_user, settings.smtp_password or "")
        client.send_message(mime)
