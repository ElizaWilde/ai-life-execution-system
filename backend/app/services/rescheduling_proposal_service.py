from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from math import ceil
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AutomationPreference,
    DailyTask,
    ReschedulingProposal,
    ReschedulingProposalItem,
    StudySession,
    UserAppSetting,
    WeeklyGoal,
)
from app.services.automation_policy_service import (
    AutomationAction,
    automation_policy_service,
)
from app.services.overdue_detection_service import (
    OverdueTaskFinding,
    overdue_detection_service,
)
from app.services.task_deadline_service import task_deadline_service


class ReschedulingProposalNotFoundError(LookupError):
    pass


class InvalidProposalStateError(ValueError):
    pass


class StaleProposalError(ValueError):
    pass


PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


class ReschedulingProposalService:
    """Create and safely apply capacity-aware rollover proposals."""

    def create_for_user(
        self,
        db: Session,
        user_id: int,
        now: datetime,
        *,
        horizon_days: int = 14,
    ) -> ReschedulingProposal | None:
        now = self._as_utc(now)
        local_now = now.astimezone(self._user_timezone(db, user_id))
        findings = overdue_detection_service.find(
            db,
            user_id,
            now,
            local_date=local_now.date(),
        )
        return self.create_from_findings(
            db,
            user_id,
            local_now,
            findings,
            horizon_days=horizon_days,
        )

    def create_from_findings(
        self,
        db: Session,
        user_id: int,
        local_now: datetime,
        findings: list[OverdueTaskFinding],
        *,
        horizon_days: int = 14,
    ) -> ReschedulingProposal | None:
        if not findings:
            return None

        deduplication_key = (
            f"rollover:{user_id}:{local_now.date().isoformat()}:"
            + "-".join(str(item.task.id) for item in findings)
        )[:180]
        existing = db.scalar(
            select(ReschedulingProposal)
            .options(selectinload(ReschedulingProposal.items))
            .where(
                ReschedulingProposal.deduplication_key == deduplication_key
            )
        )
        if existing is not None:
            return existing

        working_days = self._working_weekdays(db, user_id)
        daily_capacity = self._daily_capacity_minutes(
            db,
            user_id,
            local_now.date(),
            working_days,
        )
        candidates = self._candidate_dates(
            local_now.date(),
            working_days,
            horizon_days,
        )
        used_minutes = self._scheduled_minutes(
            db,
            user_id,
            candidates[0],
            candidates[-1],
        )

        proposal = ReschedulingProposal(
            user_id=user_id,
            proposal_type="rollover",
            status="pending",
            reason=(
                f"Move {len(findings)} overdue task(s) into available future "
                f"capacity of about {daily_capacity} minutes per working day."
            ),
            expected_minutes=sum(item.task.estimated_minutes or 30 for item in findings),
            deduplication_key=deduplication_key,
            expires_at=self._as_utc(local_now) + timedelta(hours=48),
        )
        db.add(proposal)

        ordered = sorted(
            findings,
            key=lambda item: (
                SEVERITY_RANK[item.severity],
                PRIORITY_RANK.get(item.task.priority, 1),
                item.task.due_at or datetime.min.replace(tzinfo=timezone.utc),
                item.task.id,
            ),
        )
        for finding in ordered:
            minutes = finding.task.estimated_minutes or 30
            proposed_date = self._select_date(
                candidates,
                used_minutes,
                daily_capacity,
                minutes,
            )
            used_minutes[proposed_date] += minutes
            proposal.items.append(
                ReschedulingProposalItem(
                    daily_task_id=finding.task.id,
                    original_date=finding.task.task_date,
                    proposed_date=proposed_date,
                    estimated_minutes=minutes,
                    reason=(
                        f"{finding.severity.title()} overdue risk; earliest working "
                        "day with suitable remaining capacity."
                    ),
                )
            )

        db.commit()
        return self.get(db, user_id, proposal.id)

    def list_for_user(
        self,
        db: Session,
        user_id: int,
        status: str | None = None,
    ) -> list[ReschedulingProposal]:
        self.expire_stale(db, user_id)
        query = (
            select(ReschedulingProposal)
            .options(selectinload(ReschedulingProposal.items))
            .where(ReschedulingProposal.user_id == user_id)
        )
        if status is not None:
            query = query.where(ReschedulingProposal.status == status)
        return list(
            db.scalars(
                query.order_by(
                    ReschedulingProposal.created_at.desc(),
                    ReschedulingProposal.id.desc(),
                )
            )
        )

    def get(
        self,
        db: Session,
        user_id: int,
        proposal_id: int,
    ) -> ReschedulingProposal:
        proposal = db.scalar(
            select(ReschedulingProposal)
            .options(selectinload(ReschedulingProposal.items))
            .where(
                ReschedulingProposal.id == proposal_id,
                ReschedulingProposal.user_id == user_id,
            )
        )
        if proposal is None:
            raise ReschedulingProposalNotFoundError("Rescheduling proposal not found")
        return proposal

    def approve(
        self,
        db: Session,
        user_id: int,
        proposal_id: int,
        now: datetime | None = None,
    ) -> ReschedulingProposal:
        proposal = self.get(db, user_id, proposal_id)
        now = self._as_utc(now or datetime.now(timezone.utc))
        self._ensure_not_expired(db, proposal, now)
        if proposal.status == "approved":
            return proposal
        if proposal.status != "pending":
            raise InvalidProposalStateError(
                f"Only pending proposals can be approved; current status is {proposal.status}"
            )
        proposal.status = "approved"
        proposal.approved_at = now
        db.commit()
        return self.get(db, user_id, proposal_id)

    def reject(
        self,
        db: Session,
        user_id: int,
        proposal_id: int,
        now: datetime | None = None,
    ) -> ReschedulingProposal:
        proposal = self.get(db, user_id, proposal_id)
        now = self._as_utc(now or datetime.now(timezone.utc))
        self._ensure_not_expired(db, proposal, now)
        if proposal.status == "rejected":
            return proposal
        if proposal.status not in {"pending", "approved"}:
            raise InvalidProposalStateError(
                f"Proposal cannot be rejected from status {proposal.status}"
            )
        proposal.status = "rejected"
        proposal.rejected_at = now
        db.commit()
        return self.get(db, user_id, proposal_id)

    def apply(
        self,
        db: Session,
        user_id: int,
        proposal_id: int,
        now: datetime | None = None,
    ) -> ReschedulingProposal:
        proposal = self.get(db, user_id, proposal_id)
        now = self._as_utc(now or datetime.now(timezone.utc))
        self._ensure_not_expired(db, proposal, now)
        if proposal.status == "applied":
            return proposal
        if proposal.status != "approved":
            raise InvalidProposalStateError(
                "Proposal must be approved before it can be applied"
            )

        decision = automation_policy_service.evaluate(
            AutomationAction.MOVE_TASK_TO_ANOTHER_DAY,
            confirmed=True,
        )
        if not decision.allowed:
            raise InvalidProposalStateError(decision.reason)

        task_ids = [item.daily_task_id for item in proposal.items]
        tasks = {
            task.id: task
            for task in db.scalars(
                select(DailyTask).where(
                    DailyTask.user_id == user_id,
                    DailyTask.id.in_(task_ids),
                )
            )
        }
        for item in proposal.items:
            task = tasks.get(item.daily_task_id)
            if (
                task is None
                or task.status not in {"pending", "in_progress"}
                or task.task_date != item.original_date
            ):
                proposal.status = "expired"
                db.commit()
                raise StaleProposalError(
                    "Proposal is stale because one or more tasks changed"
                )

        for item in proposal.items:
            task = tasks[item.daily_task_id]
            task.task_date = item.proposed_date
            task.due_at = task_deadline_service.calculate(
                db,
                user_id,
                item.proposed_date,
                task.planning_scope,
            )

        proposal.status = "applied"
        proposal.applied_at = now
        db.commit()
        return self.get(db, user_id, proposal_id)

    def confirm(
        self,
        db: Session,
        user_id: int,
        proposal_id: int,
        now: datetime | None = None,
    ) -> ReschedulingProposal:
        """Approve and apply a rollover after one explicit user confirmation."""
        proposal = self.get(db, user_id, proposal_id)
        if proposal.status == "applied":
            return proposal
        if proposal.status == "pending":
            self.approve(db, user_id, proposal_id, now)
        return self.apply(db, user_id, proposal_id, now)

    def expire_stale(self, db: Session, user_id: int) -> int:
        now = datetime.now(timezone.utc)
        proposals = list(
            db.scalars(
                select(ReschedulingProposal).where(
                    ReschedulingProposal.user_id == user_id,
                    ReschedulingProposal.status.in_(("pending", "approved")),
                    ReschedulingProposal.expires_at <= now,
                )
            )
        )
        for proposal in proposals:
            proposal.status = "expired"
        if proposals:
            db.commit()
        return len(proposals)

    def _ensure_not_expired(
        self,
        db: Session,
        proposal: ReschedulingProposal,
        now: datetime,
    ) -> None:
        expires_at = self._as_utc(proposal.expires_at)
        if proposal.status in {"pending", "approved"} and expires_at <= now:
            proposal.status = "expired"
            db.commit()
            raise InvalidProposalStateError("Rescheduling proposal has expired")

    def _daily_capacity_minutes(
        self,
        db: Session,
        user_id: int,
        target_date: date,
        working_days: set[int],
    ) -> int:
        goals = list(
            db.scalars(
                select(WeeklyGoal).where(
                    WeeklyGoal.user_id == user_id,
                    WeeklyGoal.status == "active",
                    WeeklyGoal.week_start <= target_date,
                    WeeklyGoal.week_end >= target_date,
                )
            )
        )
        intended_total = sum(goal.target_minutes or 0 for goal in goals)
        intended_daily = (
            ceil(intended_total / max(1, len(working_days))) if intended_total else 0
        )

        history_start = datetime.combine(
            target_date - timedelta(days=28),
            datetime.min.time(),
            tzinfo=timezone.utc,
        )
        historical_total = int(
            db.scalar(
                select(func.coalesce(func.sum(StudySession.duration_minutes), 0)).where(
                    StudySession.user_id == user_id,
                    StudySession.status == "completed",
                    StudySession.started_at >= history_start,
                )
            )
            or 0
        )
        historical_daily = ceil(historical_total / max(1, len(working_days) * 4))

        if intended_daily and historical_daily:
            capacity = min(intended_daily, max(60, round(historical_daily * 1.25)))
        else:
            capacity = intended_daily or historical_daily or 120
        return max(30, min(capacity, 480))

    @staticmethod
    def _candidate_dates(
        start_date: date,
        working_days: set[int],
        horizon_days: int,
    ) -> list[date]:
        candidates = [
            start_date + timedelta(days=offset)
            for offset in range(horizon_days + 1)
            if (start_date + timedelta(days=offset)).weekday() in working_days
        ]
        if not candidates:
            candidates = [start_date]
        return candidates

    @staticmethod
    def _select_date(
        candidates: list[date],
        used_minutes: dict[date, int],
        capacity: int,
        task_minutes: int,
    ) -> date:
        for candidate in candidates:
            if used_minutes[candidate] + task_minutes <= capacity:
                return candidate
        return min(candidates, key=lambda item: (used_minutes[item], item))

    @staticmethod
    def _scheduled_minutes(
        db: Session,
        user_id: int,
        start_date: date,
        end_date: date,
    ) -> dict[date, int]:
        used: dict[date, int] = defaultdict(int)
        tasks = db.scalars(
            select(DailyTask).where(
                DailyTask.user_id == user_id,
                DailyTask.task_date >= start_date,
                DailyTask.task_date <= end_date,
                DailyTask.status.in_(("pending", "in_progress")),
            )
        )
        for task in tasks:
            used[task.task_date] += task.estimated_minutes or 30
        return used

    @staticmethod
    def _working_weekdays(db: Session, user_id: int) -> set[int]:
        preference = db.scalar(
            select(AutomationPreference).where(
                AutomationPreference.user_id == user_id
            )
        )
        names = (
            preference.working_days_json
            if preference is not None and preference.working_days_json
            else ["monday", "tuesday", "wednesday", "thursday", "friday"]
        )
        mapping = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        return {mapping[name] for name in names if name in mapping} or set(range(5))

    @staticmethod
    def _user_timezone(db: Session, user_id: int) -> ZoneInfo:
        name = (
            db.scalar(
                select(AutomationPreference.timezone).where(
                    AutomationPreference.user_id == user_id
                )
            )
            or "Asia/Singapore"
        )
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


rescheduling_proposal_service = ReschedulingProposalService()
