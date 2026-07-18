from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models import User, UserAppSetting
from app.schemas.user_app_setting import UserAppSettingRead, UserAppSettingUpdate
from app.services.user_app_setting_service import user_app_setting_service


router = APIRouter()


def _to_read(setting: UserAppSetting) -> UserAppSettingRead:
    return UserAppSettingRead(
        id=setting.id,
        user_id=setting.user_id,
        week_start=setting.week_start,
        focus_minutes=setting.focus_minutes,
        short_break_minutes=setting.short_break_minutes,
        long_break_minutes=setting.long_break_minutes,
        cycle_count=setting.cycle_count,
        workload=setting.workload,
        theme=setting.theme,
        tone=setting.tone,
        strictness=setting.strictness,
        adjustment=setting.adjustment,
        proactive=setting.proactive,
        focus_matters=setting.focus_matters,
        protect_deep_work=setting.protect_deep_work,
        learn_from_feedback=setting.learn_from_feedback,
        integrations=setting.integrations_json,
        avatar_data_url=setting.avatar_data_url,
        created_at=setting.created_at,
        updated_at=setting.updated_at,
    )


@router.get("/me", response_model=UserAppSettingRead)
def get_my_app_settings(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> UserAppSettingRead:
    return _to_read(user_app_setting_service.get_or_create(db, user.id))


@router.put("/me", response_model=UserAppSettingRead)
def update_my_app_settings(
    payload: UserAppSettingUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> UserAppSettingRead:
    return _to_read(user_app_setting_service.update(db, user.id, payload))
