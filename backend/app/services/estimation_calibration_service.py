from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DailyTask, StudySession


@dataclass(frozen=True)
class EstimationCalibration:
    factor: float
    sample_count: int
    planned_minutes: int
    actual_minutes: int

    @property
    def confidence(self) -> str:
        if self.sample_count == 0:
            return "none"
        if self.sample_count < 3:
            return "low"
        if self.sample_count < 8:
            return "medium"
        return "high"

    def as_dict(self) -> dict:
        return {
            "factor": self.factor,
            "sample_count": self.sample_count,
            "planned_minutes": self.planned_minutes,
            "actual_minutes": self.actual_minutes,
            "confidence": self.confidence,
        }


class EstimationCalibrationService:
    """Learn a conservative estimate multiplier from linked completed sessions."""

    def calculate(self, db: Session, user_id: int) -> EstimationCalibration:
        rows = db.execute(
            select(
                DailyTask.id,
                DailyTask.estimated_minutes,
                func.sum(StudySession.duration_minutes).label("actual_minutes"),
            )
            .join(StudySession, StudySession.daily_task_id == DailyTask.id)
            .where(
                DailyTask.user_id == user_id,
                DailyTask.estimated_minutes.is_not(None),
                DailyTask.estimated_minutes > 0,
                StudySession.user_id == user_id,
                StudySession.status == "completed",
                StudySession.duration_minutes.is_not(None),
            )
            .group_by(DailyTask.id, DailyTask.estimated_minutes)
            .order_by(DailyTask.id.desc())
            .limit(30)
        ).all()

        if not rows:
            return EstimationCalibration(1.0, 0, 0, 0)

        planned = sum(int(row.estimated_minutes or 0) for row in rows)
        actual = sum(int(row.actual_minutes or 0) for row in rows)
        ratios = [
            max(0.5, min(2.0, int(row.actual_minutes or 0) / row.estimated_minutes))
            for row in rows
            if row.estimated_minutes
        ]
        # Four virtual on-target samples stop one unusual session from dominating.
        factor = (sum(ratios) + 4.0) / (len(ratios) + 4)
        return EstimationCalibration(
            factor=round(max(0.6, min(1.8, factor)), 2),
            sample_count=len(ratios),
            planned_minutes=planned,
            actual_minutes=actual,
        )

    @staticmethod
    def apply(minutes: int | None, factor: float) -> int:
        if not minutes:
            return 0
        calibrated = max(5, round((minutes * factor) / 5) * 5)
        return int(calibrated)


estimation_calibration_service = EstimationCalibrationService()
