from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AutomationAudit


class AutomationAuditService:
    """Reusable database-backed action identity and execution audit."""

    def claim(
        self,
        db: Session,
        *,
        user_id: int,
        action_key: str,
        trigger_source: str,
        automation_type: str,
        service_name: str,
        input_json: dict | None = None,
        confirmation_status: str = "not_required",
    ) -> tuple[AutomationAudit, bool]:
        action_key = action_key[:180]
        existing = db.scalar(
            select(AutomationAudit).where(
                AutomationAudit.action_key == action_key,
                AutomationAudit.user_id == user_id,
            )
        )
        if existing is not None:
            return existing, False

        audit = AutomationAudit(
            user_id=user_id,
            action_key=action_key,
            trigger_source=trigger_source,
            automation_type=automation_type,
            service_name=service_name,
            input_json=input_json or {},
            decision_json={},
            records_changed_json=[],
            confirmation_status=confirmation_status,
            execution_status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(audit)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(
                select(AutomationAudit).where(
                    AutomationAudit.action_key == action_key,
                    AutomationAudit.user_id == user_id,
                )
            )
            if existing is None:
                raise
            return existing, False
        db.refresh(audit)
        return audit, True

    @staticmethod
    def complete(
        db: Session,
        audit: AutomationAudit,
        *,
        decision_json: dict | None = None,
        records_changed: list | None = None,
        confirmation_status: str | None = None,
    ) -> AutomationAudit:
        audit.execution_status = "completed"
        audit.decision_json = decision_json or {}
        audit.records_changed_json = records_changed or []
        if confirmation_status is not None:
            audit.confirmation_status = confirmation_status
        audit.failure_reason = None
        audit.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(audit)
        return audit

    @staticmethod
    def fail(
        db: Session,
        audit: AutomationAudit,
        exc: Exception,
    ) -> AutomationAudit:
        audit.execution_status = "failed"
        audit.failure_reason = str(exc)[:2000]
        audit.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(audit)
        return audit

    @staticmethod
    def cancel(
        db: Session,
        audit: AutomationAudit,
        *,
        confirmation_status: str = "rejected",
    ) -> AutomationAudit:
        audit.execution_status = "cancelled"
        audit.confirmation_status = confirmation_status
        audit.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(audit)
        return audit


automation_audit_service = AutomationAuditService()
