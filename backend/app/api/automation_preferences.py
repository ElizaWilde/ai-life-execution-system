from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models import AutomationPreference, User
from app.schemas.automation_preference import (
    AutomationPreferenceRead,
    AutomationPreferenceUpdate,
)
from app.services.automation_preference_service import automation_preference_service


router = APIRouter()


def _to_read(preference: AutomationPreference) -> AutomationPreferenceRead:
    return AutomationPreferenceRead(
        id=preference.id,
        user_id=preference.user_id,
        timezone=preference.timezone,
        morning_reminder_time=preference.morning_reminder_time,
        evening_review_time=preference.evening_review_time,
        notification_channel=preference.notification_channel,
        automatic_rescheduling_enabled=preference.automatic_rescheduling_enabled,
        confirmation_required=preference.confirmation_required,
        max_reminders_per_day=preference.max_reminders_per_day,
        quiet_hours_start=preference.quiet_hours_start,
        quiet_hours_end=preference.quiet_hours_end,
        working_days=preference.working_days_json,
        preferred_study_periods=preference.preferred_study_periods_json,
        created_at=preference.created_at,
        updated_at=preference.updated_at,
    )


@router.get("", response_model=AutomationPreferenceRead)
def get_automation_preferences(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AutomationPreferenceRead:
    return _to_read(automation_preference_service.get_or_create(db, user.id))


@router.patch("", response_model=AutomationPreferenceRead)
def update_automation_preferences(
    payload: AutomationPreferenceUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AutomationPreferenceRead:
    return _to_read(automation_preference_service.update(db, user.id, payload))
