from datetime import datetime, time, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models import DailyTask, StudySession, User
from app.schemas.study_session import (
    StudySessionFinish,
    StudySessionRead,
    StudySessionStart,
)
from app.services.study_session_duration import counted_focus_session_clause


router = APIRouter()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.post(
    "/start",
    response_model=StudySessionRead,
    status_code=status.HTTP_201_CREATED,
)
def start_study_session(
    payload: StudySessionStart,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> StudySession:
    running_session = db.scalar(
        select(StudySession).where(
            StudySession.user_id == user.id,
            StudySession.status == "running",
        )
    )

    if payload.daily_task_id is not None:
        task_id = db.scalar(
            select(DailyTask.id).where(
                DailyTask.id == payload.daily_task_id,
                DailyTask.user_id == user.id,
            )
        )
        if task_id is None:
            raise HTTPException(status_code=404, detail="Daily task not found")

    started_at = payload.started_at or datetime.now(timezone.utc)
    if running_session is not None:
        # A browser refresh, cleared local storage, or an older abandoned timer can
        # leave a server-side session running even though the UI is idle. Reclaim
        # that incomplete record so Start remains recoverable and no empty session
        # is added to focus history.
        running_session.daily_task_id = payload.daily_task_id
        running_session.subject = payload.subject
        running_session.started_at = started_at
        running_session.ended_at = None
        running_session.duration_minutes = None
        running_session.duration_seconds = None
        running_session.notes = None
        db.commit()
        db.refresh(running_session)
        return running_session

    values = payload.model_dump(exclude={"started_at"})
    session = StudySession(
        user_id=user.id,
        started_at=started_at,
        **values,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.post("/finish", response_model=StudySessionRead)
def finish_study_session(
    payload: StudySessionFinish,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> StudySession:
    session = db.scalar(
        select(StudySession).where(
            StudySession.id == payload.session_id,
            StudySession.user_id == user.id,
        )
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Study session not found")
    if session.status != "running":
        raise HTTPException(status_code=409, detail="Study session is not running")

    ended_at = payload.ended_at or datetime.now(timezone.utc)
    elapsed_seconds = (_as_utc(ended_at) - _as_utc(session.started_at)).total_seconds()
    if elapsed_seconds < 0:
        raise HTTPException(status_code=422, detail="ended_at precedes started_at")

    focused_seconds = (
        payload.duration_seconds
        if payload.duration_seconds is not None
        else int(elapsed_seconds)
    )
    session.ended_at = ended_at
    session.duration_seconds = focused_seconds
    session.duration_minutes = focused_seconds // 60
    session.status = "completed"
    session.notes = payload.notes
    db.flush()

    if session.daily_task_id is not None:
        task = db.scalar(
            select(DailyTask).where(
                DailyTask.id == session.daily_task_id,
                DailyTask.user_id == user.id,
            )
        )
        if task is not None and task.estimated_minutes is not None and task.estimated_minutes > 0:
            focused_seconds = db.scalar(
                select(
                    func.coalesce(
                        func.sum(
                            func.coalesce(
                                StudySession.duration_seconds,
                                StudySession.duration_minutes * 60,
                            )
                        ),
                        0,
                    )
                ).where(
                    StudySession.daily_task_id == task.id,
                    StudySession.user_id == user.id,
                    StudySession.status == "completed",
                    counted_focus_session_clause(),
                )
            )
            if focused_seconds >= task.estimated_minutes * 60:
                task.status = "completed"
                task.completed_at = ended_at

    db.commit()
    db.refresh(session)
    return session


@router.get("/today", response_model=list[StudySessionRead])
def get_today_sessions(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[StudySession]:
    today_start = datetime.combine(
        datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc
    )
    tomorrow_start = today_start + timedelta(days=1)
    return list(
        db.scalars(
            select(StudySession)
            .where(
                StudySession.user_id == user.id,
                StudySession.started_at >= today_start,
                StudySession.started_at < tomorrow_start,
                or_(
                    StudySession.status == "running",
                    counted_focus_session_clause(),
                ),
            )
            .order_by(StudySession.started_at)
        )
    )
