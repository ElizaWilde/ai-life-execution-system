from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AutomationPreference, Notification, User
from app.schemas.notification import NotificationSend
from app.services.notification_provider import (
    EmailNotificationProvider,
    NotificationProvider,
    NotificationProviderError,
    TelegramNotificationProvider,
)


class NotificationNotFoundError(LookupError):
    pass


class NotificationNotRetryableError(ValueError):
    pass


class NotificationService:
    def __init__(
        self,
        provider: NotificationProvider,
        telegram_provider: NotificationProvider,
    ) -> None:
        self.provider = provider
        self.telegram_provider = telegram_provider

    def create(
        self,
        db: Session,
        user: User,
        payload: NotificationSend,
        *,
        deduplication_key: str | None = None,
    ) -> Notification:
        if deduplication_key is not None:
            existing = db.scalar(
                select(Notification).where(
                    Notification.deduplication_key == deduplication_key
                )
            )
            if existing is not None:
                return existing
        preference = db.scalar(
            select(AutomationPreference).where(
                AutomationPreference.user_id == user.id
            )
        )
        channel = payload.channel or (
            preference.notification_channel if preference is not None else "email"
        )
        if channel not in {"email", "telegram"}:
            channel = "email"
        recipient = (
            user.email
            if channel == "email"
            else (preference.telegram_chat_id if preference is not None else None) or ""
        )
        notification = Notification(
            user_id=user.id,
            notification_type=payload.notification_type,
            channel=channel,
            recipient=recipient,
            subject=payload.subject or self._default_subject(payload.notification_type),
            message=payload.message,
            scheduled_at=payload.scheduled_at or datetime.now(timezone.utc),
            status="pending",
            deduplication_key=deduplication_key,
        )
        db.add(notification)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if deduplication_key is None:
                raise
            existing = db.scalar(
                select(Notification).where(
                    Notification.deduplication_key == deduplication_key
                )
            )
            if existing is None:
                raise
            return existing
        db.refresh(notification)

        if payload.scheduled_at is None or payload.scheduled_at <= datetime.now(timezone.utc):
            return self.deliver(db, notification)
        return notification

    def deliver(self, db: Session, notification: Notification) -> Notification:
        if notification.status == "delivered":
            return notification
        if notification.attempt_count >= notification.max_attempts:
            raise NotificationNotRetryableError("Maximum delivery attempts reached")

        notification.status = "sending"
        notification.attempt_count += 1
        notification.last_attempt_at = datetime.now(timezone.utc)
        notification.failure_reason = None
        db.commit()

        try:
            provider = self._provider_for(notification.channel)
            provider.send(
                recipient=notification.recipient,
                subject=notification.subject,
                message=notification.message,
            )
        except NotificationProviderError as exc:
            notification.status = "failed"
            notification.failure_reason = str(exc)[:2000]
            db.commit()
            db.refresh(notification)
            return notification

        notification.status = "delivered"
        notification.delivered_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
        return notification

    def list_for_user(
        self,
        db: Session,
        user_id: int,
        status: str | None = None,
    ) -> list[Notification]:
        query = select(Notification).where(Notification.user_id == user_id)
        if status is not None:
            query = query.where(Notification.status == status)
        return list(db.scalars(query.order_by(Notification.created_at.desc(), Notification.id.desc())))

    def retry(self, db: Session, user_id: int, notification_id: int) -> Notification:
        notification = db.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
        if notification is None:
            raise NotificationNotFoundError("Notification not found")
        if notification.status != "failed":
            raise NotificationNotRetryableError("Only failed notifications can be retried")
        return self.deliver(db, notification)

    def _provider_for(self, channel: str) -> NotificationProvider:
        if channel == "telegram":
            return self.telegram_provider
        return self.provider

    @staticmethod
    def _default_subject(notification_type: str) -> str:
        return notification_type.replace("_", " ").title()


notification_service = NotificationService(
    EmailNotificationProvider(),
    TelegramNotificationProvider(),
)
