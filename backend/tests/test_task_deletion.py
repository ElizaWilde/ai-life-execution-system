from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import DailyTask, ReschedulingProposal, ReschedulingProposalItem, StudySession, User
from conftest import TestingSessionLocal


@pytest.mark.parametrize("session_status", ["running", "completed"])
def test_delete_task_removes_only_its_proposal_items_and_preserves_sessions(
    client, user_headers, session_status
):
    now = datetime.now(timezone.utc)
    today = date.today()
    with TestingSessionLocal() as db:
        task = DailyTask(user_id=1, title="Delete me", task_date=today)
        other = DailyTask(user_id=1, title="Keep me", task_date=today)
        db.add_all([task, other])
        db.flush()
        task_id, other_id = task.id, other.id
        proposal_ids = []
        for status in ["pending", "approved", "applied", "rejected", "expired"]:
            proposal = ReschedulingProposal(
                user_id=1,
                status=status,
                reason="Regression test",
                expected_minutes=60,
                deduplication_key=f"delete-task-{status}",
                expires_at=now + timedelta(days=1),
            )
            db.add(proposal)
            db.flush()
            proposal_ids.append(proposal.id)
            for linked_task in [task, other]:
                db.add(ReschedulingProposalItem(
                    proposal_id=proposal.id,
                    daily_task_id=linked_task.id,
                    original_date=today,
                    proposed_date=today + timedelta(days=1),
                    estimated_minutes=30,
                    reason="Move task",
                ))
        study_session = StudySession(
            user_id=1,
            daily_task_id=task_id,
            subject="Preserve this history",
            started_at=now - timedelta(minutes=30),
            ended_at=now if session_status == "completed" else None,
            duration_minutes=30 if session_status == "completed" else None,
            status=session_status,
        )
        db.add(study_session)
        db.commit()
        session_id = study_session.id

    response = client.delete(f"/daily-tasks/{task_id}", headers=user_headers)

    assert response.status_code == 204
    with TestingSessionLocal() as db:
        assert db.get(DailyTask, task_id) is None
        assert db.get(DailyTask, other_id) is not None
        remaining_items = db.scalars(select(ReschedulingProposalItem)).all()
        assert len(remaining_items) == len(proposal_ids)
        assert {item.daily_task_id for item in remaining_items} == {other_id}
        assert {item.proposal_id for item in remaining_items} == set(proposal_ids)
        assert all(db.get(ReschedulingProposal, pid) is not None for pid in proposal_ids)
        preserved_session = db.get(StudySession, session_id)
        assert preserved_session is not None
        assert preserved_session.daily_task_id is None
        assert preserved_session.subject == "Preserve this history"
        assert preserved_session.status == session_status
        assert preserved_session.duration_minutes == (30 if session_status == "completed" else None)

    assert client.delete(f"/daily-tasks/{task_id}", headers=user_headers).status_code == 404


def test_delete_task_does_not_delete_another_users_task(client, user_headers):
    with TestingSessionLocal() as db:
        owner = User(email="other@example.com", password_hash="unused", display_name="Other")
        db.add(owner)
        db.flush()
        task = DailyTask(user_id=owner.id, title="Private task", task_date=date.today())
        db.add(task)
        db.commit()
        task_id = task.id

    assert client.delete(f"/daily-tasks/{task_id}", headers=user_headers).status_code == 404
    with TestingSessionLocal() as db:
        assert db.get(DailyTask, task_id) is not None
