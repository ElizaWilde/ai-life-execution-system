from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    DailyTask,
    ProcrastinationEvent,
    ReschedulingProposalItem,
    StudySession,
)
from app.services.automation_audit_service import automation_audit_service
from app.services.estimation_calibration_service import estimation_calibration_service
from app.services.overdue_detection_service import overdue_detection_service


class ProcrastinationDetectionService:
    """Persist cautious rule-based patterns with evidence and interventions."""

    def detect(
        self,
        db: Session,
        user_id: int,
        now: datetime,
    ) -> list[ProcrastinationEvent]:
        local_date = now.date()
        overdue = overdue_detection_service.find(
            db,
            user_id,
            now,
            local_date=local_date,
        )
        candidates: list[dict] = []

        if len(overdue) >= 2:
            candidates.append(
                {
                    "detection_type": "planning_overload",
                    "severity": "high" if len(overdue) >= 4 else "medium",
                    "confidence": min(0.9, 0.55 + len(overdue) * 0.08),
                    "task_ids": [item.task.id for item in overdue],
                    "evidence": [
                        f"{len(overdue)} tasks are overdue at the same time.",
                        f"{sum(item.task.estimated_minutes or 30 for item in overdue)} estimated minutes are waiting.",
                    ],
                    "intervention": (
                        "Protect one high-priority next action and create a "
                        "capacity-aware rollover proposal for the remaining work."
                    ),
                }
            )

        high_overdue = [item for item in overdue if item.task.priority == "high"]
        if high_overdue:
            candidates.append(
                {
                    "detection_type": "deadline_avoidance",
                    "severity": "high",
                    "confidence": min(0.9, 0.6 + len(high_overdue) * 0.08),
                    "task_ids": [item.task.id for item in high_overdue],
                    "evidence": [
                        f"{len(high_overdue)} high-priority task(s) are overdue.",
                        "Important work has remained incomplete past its planned deadline.",
                    ],
                    "intervention": (
                        "Schedule the smallest concrete step during the next strong "
                        "focus period and confirm whether the deadline is still valid."
                    ),
                }
            )

        calibration = estimation_calibration_service.calculate(db, user_id)
        if calibration.sample_count >= 3 and calibration.factor >= 1.25:
            candidates.append(
                {
                    "detection_type": "unrealistic_duration",
                    "severity": "medium" if calibration.factor < 1.5 else "high",
                    "confidence": min(0.95, 0.55 + calibration.sample_count * 0.04),
                    "task_ids": [],
                    "evidence": [
                        f"{calibration.sample_count} linked task(s) were measured.",
                        f"Actual focus time averages {calibration.factor:.2f}× the original estimate.",
                    ],
                    "intervention": (
                        "Use calibrated estimates in future previews and reduce "
                        "planned task volume before moving deadlines."
                    ),
                }
            )

        repeated = db.execute(
            select(
                ReschedulingProposalItem.daily_task_id,
                func.count(ReschedulingProposalItem.id).label("proposal_count"),
            )
            .join(DailyTask, DailyTask.id == ReschedulingProposalItem.daily_task_id)
            .where(DailyTask.user_id == user_id)
            .group_by(ReschedulingProposalItem.daily_task_id)
            .having(func.count(ReschedulingProposalItem.id) >= 2)
        ).all()
        if repeated:
            task_ids = [int(row.daily_task_id) for row in repeated]
            candidates.append(
                {
                    "detection_type": "repeated_postponement",
                    "severity": "high" if any(row.proposal_count >= 4 for row in repeated) else "medium",
                    "confidence": min(0.95, 0.65 + len(task_ids) * 0.05),
                    "task_ids": task_ids,
                    "evidence": [
                        f"{len(task_ids)} task(s) appeared in multiple rollover proposals."
                    ],
                    "intervention": (
                        "Stop rolling the task forward automatically; clarify scope, "
                        "split it, or explicitly decide whether it remains relevant."
                    ),
                }
            )

        return [
            self._store_candidate(db, user_id, now, candidate)
            for candidate in candidates
        ]

    def list_for_user(
        self,
        db: Session,
        user_id: int,
        *,
        status: str | None = "active",
    ) -> list[ProcrastinationEvent]:
        query = select(ProcrastinationEvent).where(
            ProcrastinationEvent.user_id == user_id
        )
        if status:
            query = query.where(ProcrastinationEvent.status == status)
        return list(
            db.scalars(
                query.order_by(
                    ProcrastinationEvent.detected_at.desc(),
                    ProcrastinationEvent.id.desc(),
                )
            )
        )

    def _store_candidate(
        self,
        db: Session,
        user_id: int,
        now: datetime,
        candidate: dict,
    ) -> ProcrastinationEvent:
        task_key = "-".join(str(value) for value in candidate["task_ids"]) or "general"
        detection_key = (
            f"procrastination:{user_id}:{candidate['detection_type']}:{now.date()}:{task_key}"
        )[:180]
        existing = db.scalar(
            select(ProcrastinationEvent).where(
                ProcrastinationEvent.detection_key == detection_key
            )
        )
        if existing is not None:
            return existing

        audit, claimed = automation_audit_service.claim(
            db,
            user_id=user_id,
            action_key=f"audit:{detection_key}",
            trigger_source="procrastination_detector",
            automation_type=candidate["detection_type"],
            service_name="procrastination_detection_service",
            input_json={"task_ids": candidate["task_ids"]},
        )
        if not claimed and audit.execution_status == "completed":
            existing = db.scalar(
                select(ProcrastinationEvent).where(
                    ProcrastinationEvent.detection_key == detection_key
                )
            )
            if existing is not None:
                return existing

        try:
            event = ProcrastinationEvent(
                user_id=user_id,
                detection_key=detection_key,
                detection_type=candidate["detection_type"],
                severity=candidate["severity"],
                evidence_json=candidate["evidence"],
                related_task_ids_json=candidate["task_ids"],
                confidence=candidate["confidence"],
                recommended_intervention=candidate["intervention"],
                status="active",
                detected_at=now.astimezone(timezone.utc),
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            automation_audit_service.complete(
                db,
                audit,
                decision_json={
                    "severity": event.severity,
                    "confidence": event.confidence,
                },
                records_changed=[
                    {"model": "ProcrastinationEvent", "id": event.id}
                ],
            )
            return event
        except Exception as exc:
            db.rollback()
            automation_audit_service.fail(db, audit, exc)
            raise


procrastination_detection_service = ProcrastinationDetectionService()
