from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import UserAppSetting
from app.schemas.user_app_setting import UserAppSettingUpdate


class UserAppSettingService:
    def get_or_create(self, db: Session, user_id: int) -> UserAppSetting:
        setting = db.scalar(
            select(UserAppSetting).where(UserAppSetting.user_id == user_id)
        )
        if setting is None:
            setting = UserAppSetting(user_id=user_id)
            db.add(setting)
            db.commit()
            db.refresh(setting)
        return setting

    def update(
        self,
        db: Session,
        user_id: int,
        payload: UserAppSettingUpdate,
    ) -> UserAppSetting:
        setting = self.get_or_create(db, user_id)
        data = payload.model_dump()
        data["integrations_json"] = data.pop("integrations")
        for field, value in data.items():
            setattr(setting, field, value)
        db.commit()
        db.refresh(setting)
        return setting


user_app_setting_service = UserAppSettingService()
