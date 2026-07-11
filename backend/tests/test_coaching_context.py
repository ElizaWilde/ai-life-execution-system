from datetime import date, datetime, timedelta, timezone

from app.models import DailyCheckIn, DailyTask, StudySession
from app.services.coaching_context_service import coaching_context_service
from conftest import TestingSessionLocal


def test_build_daily_context_collects_check_in_tasks_and_recent_behavior():
    target_date = date.today()
    started_at = datetime.combine(
        target_date,
        datetime.min.time(),
        tzinfo=timezone.utc,
    ) + timedelta(hours=9)

    with TestingSessionLocal() as db:
        db.add(
            DailyCheckIn(
                user_id=1,
                check_in_date=target_date,
                energy_level="steady",
                mood_level="neutral",
                sleep_hours=7.5,
                stress_level=2,
                notes="Need a calmer plan today.",
            )
        )
        db.add_all(
            [
                DailyTask(
                    user_id=1,
                    title="Ship coaching context",
                    task_date=target_date,
                    priority="high",
                    status="pending",
                    source="manual",
                ),
                DailyTask(
                    user_id=1,
                    title="Review existing stats",
                    task_date=target_date,
                    priority="medium",
                    status="completed",
                    source="manual",
                ),
                DailyTask(
                    user_id=1,
                    title="Old completed task",
                    task_date=target_date - timedelta(days=2),
                    priority="medium",
                    status="completed",
                    source="manual",
                ),
            ]
        )
        db.add(
            StudySession(
                user_id=1,
                subject="Coaching context",
                started_at=started_at,
                ended_at=started_at + timedelta(minutes=45),
                duration_minutes=45,
                status="completed",
            )
        )
        db.commit()

        context = coaching_context_service.build_daily_context(
            db=db,
            user_id=1,
            target_date=target_date,
            available_minutes=120,
        )

    assert context.target_date == target_date
    assert context.energy_level == "steady"
    assert context.mood_level == "neutral"
    assert context.sleep_hours == 7.5
    assert context.stress_level == 2
    assert context.planned_tasks == 2
    assert context.completed_tasks == 1
    assert context.unfinished_tasks == 1
    assert context.recent_focus_minutes == 45
    assert context.recent_completion_rate == 2 / 3
    assert context.available_minutes == 120
    assert context.high_priority_tasks == ["Ship coaching context"]
    assert context.user_notes == "Need a calmer plan today."


def test_build_daily_context_allows_missing_check_in():
    target_date = date.today()

    with TestingSessionLocal() as db:
        context = coaching_context_service.build_daily_context(
            db=db,
            user_id=1,
            target_date=target_date,
        )

    assert context.energy_level is None
    assert context.mood_level is None
    assert context.sleep_hours is None
    assert context.stress_level is None
    assert context.planned_tasks == 0
    assert context.recent_completion_rate == 0.0
    assert context.high_priority_tasks == []
    assert context.user_notes is None
