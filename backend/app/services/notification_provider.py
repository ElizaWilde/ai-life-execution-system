from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Protocol

import httpx

from app.config import settings


class NotificationProviderError(RuntimeError):
    """Raised when a provider cannot deliver a notification."""


class NotificationProvider(Protocol):
    channel: str

    def send(self, *, recipient: str, subject: str, message: str) -> None: ...


class EmailNotificationProvider:
    channel = "email"

    def send(self, *, recipient: str, subject: str, message: str) -> None:
        if not settings.smtp_host or not settings.smtp_from_email:
            raise NotificationProviderError(
                "Email delivery is not configured: SMTP_HOST and SMTP_FROM_EMAIL are required"
            )

        email = EmailMessage()
        email["From"] = settings.smtp_from_email
        email["To"] = recipient
        email["Subject"] = subject
        email.set_content(message)

        smtp_class = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
        try:
            with smtp_class(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            ) as client:
                if settings.smtp_use_tls and not settings.smtp_use_ssl:
                    client.starttls()
                if settings.smtp_username:
                    client.login(settings.smtp_username, settings.smtp_password or "")
                client.send_message(email)
        except (OSError, smtplib.SMTPException) as exc:
            raise NotificationProviderError(f"Email delivery failed: {exc}") from exc


class TelegramNotificationProvider:
    channel = "telegram"

    def send(self, *, recipient: str, subject: str, message: str) -> None:
        if not settings.telegram_bot_token:
            raise NotificationProviderError(
                "Telegram delivery is not configured: TELEGRAM_BOT_TOKEN is required"
            )
        if not recipient:
            raise NotificationProviderError(
                "Telegram delivery is not configured: save a Telegram chat ID first"
            )

        url = (
            "https://api.telegram.org/bot"
            f"{settings.telegram_bot_token}/sendMessage"
        )
        try:
            response = httpx.post(
                url,
                json={
                    "chat_id": recipient,
                    "text": f"{subject}\n\n{message}",
                },
                timeout=settings.telegram_timeout_seconds,
            )
        except httpx.RequestError as exc:
            raise NotificationProviderError(
                "Telegram delivery failed: Telegram API request failed"
            ) from exc

        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.is_error or not body.get("ok", False):
            description = body.get("description", "Telegram rejected the message")
            raise NotificationProviderError(
                f"Telegram delivery failed ({response.status_code}): {description}"
            )
