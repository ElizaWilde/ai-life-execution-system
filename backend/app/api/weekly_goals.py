from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models import User, WeeklyGoal
from app.schemas.weekly_goal import (
    WeeklyGoalCreate,
    WeeklyGoalRead,
    WeeklyGoalUpdate,
)


router = APIRouter()


@router.get("", response_model=list[WeeklyGoalRead])
def get_weekly_goals(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    target_date: Annotated[
        date | None,
        Query(alias="date", description="Any date in the week to load."),
    ] = None,
) -> list[WeeklyGoal]:
    selected = target_date or date.today()
    week_start = selected - timedelta(days=selected.weekday())
    week_end = week_start + timedelta(days=6)
    return list(
        db.scalars(
            select(WeeklyGoal)
            .where(
                WeeklyGoal.user_id == user.id,
                WeeklyGoal.week_start <= week_end,
                WeeklyGoal.week_end >= week_start,
                WeeklyGoal.status != "cancelled",
            )
            .order_by(WeeklyGoal.priority.desc(), WeeklyGoal.id)
        )
    )


@router.post("", response_model=WeeklyGoalRead, status_code=status.HTTP_201_CREATED)
def create_weekly_goal(
    payload: WeeklyGoalCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> WeeklyGoal:
    goal = WeeklyGoal(user_id=user.id, **payload.model_dump())
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.get("/current", response_model=list[WeeklyGoalRead])
def get_current_weekly_goals(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[WeeklyGoal]:
    today = date.today()
    return list(
        db.scalars(
            select(WeeklyGoal)
            .where(
                WeeklyGoal.user_id == user.id,
                WeeklyGoal.week_start <= today,
                WeeklyGoal.week_end >= today,
                WeeklyGoal.status == "active",
            )
            .order_by(WeeklyGoal.priority.desc(), WeeklyGoal.id)
        )
    )


@router.patch("/{goal_id}", response_model=WeeklyGoalRead)
def update_weekly_goal(
    goal_id: int,
    payload: WeeklyGoalUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> WeeklyGoal:
    goal = db.scalar(
        select(WeeklyGoal).where(
            WeeklyGoal.id == goal_id,
            WeeklyGoal.user_id == user.id,
        )
    )
    if goal is None:
        raise HTTPException(status_code=404, detail="Weekly goal not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    db.commit()
    db.refresh(goal)
    return goal
