from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models import Notification, User
from app.schemas.notification import (
    NotificationRead,
    NotificationSend,
    NotificationStatus,
)
from app.services.notification_service import (
    NotificationNotFoundError,
    NotificationNotRetryableError,
    notification_service,
)


router = APIRouter()


@router.post("", response_model=NotificationRead, status_code=status.HTTP_201_CREATED)
def create_notification(
    payload: NotificationSend,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Notification:
    return notification_service.create(db, user, payload)


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    delivery_status: Annotated[NotificationStatus | None, Query(alias="status")] = None,
) -> list[Notification]:
    return notification_service.list_for_user(db, user.id, delivery_status)


@router.post("/{notification_id}/retry", response_model=NotificationRead)
def retry_notification(
    notification_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Notification:
    try:
        return notification_service.retry(db, user.id, notification_id)
    except NotificationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NotificationNotRetryableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
