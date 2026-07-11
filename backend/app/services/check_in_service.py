from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyCheckIn
from app.schemas.daily_check_in import DailyCheckInCreate, DailyCheckInUpdate


class DuplicateCheckInError(ValueError):
    """Raised when a user already has a check-in for the target date."""


class CheckInService:
    def create_check_in(
        self,
        db: Session,
        user_id: int,
        payload: DailyCheckInCreate,
    ) -> DailyCheckIn:
        check_in_date = payload.check_in_date or date.today()
        existing = self.get_check_in(db, user_id, check_in_date)
        if existing is not None:
            raise DuplicateCheckInError("Daily check-in already exists")

        data = payload.model_dump(exclude={"check_in_date"})
        check_in = DailyCheckIn(
            user_id=user_id,
            check_in_date=check_in_date,
            **data,
        )
        db.add(check_in)
        db.commit()
        db.refresh(check_in)
        return check_in

    def get_check_in(
        self,
        db: Session,
        user_id: int,
        check_in_date: date,
    ) -> DailyCheckIn | None:
        return db.scalar(
            select(DailyCheckIn).where(
                DailyCheckIn.user_id == user_id,
                DailyCheckIn.check_in_date == check_in_date,
            )
        )

    def list_check_ins(
        self,
        db: Session,
        user_id: int,
        start_date: date,
        end_date: date,
    ) -> list[DailyCheckIn]:
        return list(
            db.scalars(
                select(DailyCheckIn)
                .where(
                    DailyCheckIn.user_id == user_id,
                    DailyCheckIn.check_in_date >= start_date,
                    DailyCheckIn.check_in_date <= end_date,
                )
                .order_by(DailyCheckIn.check_in_date.desc(), DailyCheckIn.id.desc())
            )
        )

    def update_check_in(
        self,
        db: Session,
        user_id: int,
        check_in_date: date,
        payload: DailyCheckInUpdate,
    ) -> DailyCheckIn | None:
        check_in = self.get_check_in(db, user_id, check_in_date)
        if check_in is None:
            return None

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(check_in, field, value)

        db.commit()
        db.refresh(check_in)
        return check_in


check_in_service = CheckInService()
