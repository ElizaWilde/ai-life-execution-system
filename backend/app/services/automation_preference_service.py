from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AutomationPreference
from app.schemas.automation_preference import AutomationPreferenceUpdate


class AutomationPreferenceService:
    def get_or_create(self, db: Session, user_id: int) -> AutomationPreference:
        preference = db.scalar(
            select(AutomationPreference).where(AutomationPreference.user_id == user_id)
        )
        if preference is None:
            preference = AutomationPreference(user_id=user_id)
            db.add(preference)
            db.commit()
            db.refresh(preference)
        return preference

    def update(
        self,
        db: Session,
        user_id: int,
        payload: AutomationPreferenceUpdate,
    ) -> AutomationPreference:
        preference = self.get_or_create(db, user_id)
        data = payload.model_dump(exclude_unset=True)
        if "working_days" in data:
            data["working_days_json"] = data.pop("working_days")
        if "preferred_study_periods" in data:
            data["preferred_study_periods_json"] = [
                period.model_dump(mode="json")
                for period in (payload.preferred_study_periods or [])
            ]
            data.pop("preferred_study_periods")
        for field, value in data.items():
            setattr(preference, field, value)
        db.commit()
        db.refresh(preference)
        return preference


automation_preference_service = AutomationPreferenceService()
