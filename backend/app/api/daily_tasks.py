from datetime import date, datetime, timezone
# Annotated attaches extra information to a type hint.
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
# select() creates a database SELECT statement.SQLAlchemy uses select() to construct queries that can then be executed through a Session.
from sqlalchemy import select
#Session is SQLAlchemy’s database-working object.A SQLAlchemy Session manages ORM objects and provides the interface for querying and modifying database data
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models import DailyTask, User, WeeklyGoal
from app.schemas.daily_task import DailyTaskCreate, DailyTaskRead, DailyTaskUpdate


# This creates a router object。Later, every decorator using this object adds another route.e.g.@router.post(...)
'''
    Think of it as an initially empty routing table:
        daily_tasks router
            └── currently no routes

    After FastAPI processes your decorators, it becomes:
        daily_tasks router
            ├── POST  ""     /daily-tasks
            ├── GET   "/today"  /daily-tasks/today
            └── PATCH "/{task_id}"  /daily-tasks/{task_id}

    The router is not the whole application. It is only one part of the application.
'''
router = APIRouter()


def _verify_weekly_goal(
    weekly_goal_id: int | None, user_id: int, db: Session
) -> None:
    if weekly_goal_id is None:
        return
    # db.scalar(...)executes the query and returns one scalar(标量) value.
    # So, exists does not contain a complete WeeklyGoal object. It contains only the selected ID.
    exists = db.scalar(
        select(WeeklyGoal.id).where(
            WeeklyGoal.id == weekly_goal_id,
            WeeklyGoal.user_id == user_id,
        )
    )
    if exists is None:
        raise HTTPException(status_code=404, detail="Weekly goal not found")
'''
    This decorator registers a route.
    response_model=DailyTaskRead: Before sending the result to the client, validate and serialize it using DailyTaskRead.
    A response model controls response validation, serialization, filtering and API documentation. It can be one Pydantic model or a collection such as list[DailyTaskRead]
    status_code=status.HTTP_201_CREATED: FastAPI uses the configured status code both in the actual response and in generated API documentation.
'''
@router.post("", response_model=DailyTaskRead, status_code=status.HTTP_201_CREATED)
def create_daily_task(
    
    #    FastAPI treats each parameter differently.
    #        FastAPI treats payload as the JSON request body.Because DailyTaskCreate is a Pydantic model.
    #        FastAPI treats db(must be a Session) as a dependency injection parameter. It will call(not manually) get_db() to get the value for db.   
    #        FastAPI treats user(must be a User) as a dependency injection parameter. It will call get_current_user() to get the value for user.        
    payload: DailyTaskCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> DailyTask:
    _verify_weekly_goal(payload.weekly_goal_id, user.id, db)
    # creates a SQLAlchemy DailyTask object.
    task = DailyTask(user_id=user.id, **payload.model_dump())
    # Adds the new object to the current SQLAlchemy session.
    db.add(task)
    # Commits the database transaction.Without commit(), the new data would not normally be permanently committed.
    db.commit()
    # Reloads the database row into the task object.
    db.refresh(task)
    return task


@router.get("/today", response_model=list[DailyTaskRead])
def get_today_tasks(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[DailyTask]:
    return list(
        db.scalars(
            select(DailyTask)
            .where(
                DailyTask.user_id == user.id,
                DailyTask.task_date == date.today(),
            )
            .order_by(DailyTask.status, DailyTask.priority.desc(), DailyTask.id)
        )
    )


@router.patch("/{task_id}", response_model=DailyTaskRead)
def update_daily_task(
    task_id: int,
    payload: DailyTaskUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> DailyTask:
    task = db.scalar(
        select(DailyTask).where(
            DailyTask.id == task_id,
            DailyTask.user_id == user.id,
        )
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Daily task not found")

    changes = payload.model_dump(exclude_unset=True)
    _verify_weekly_goal(changes.get("weekly_goal_id"), user.id, db)
    # Update each provided field
    for field, value in changes.items():
        setattr(task, field, value)
    # checks whether the client explicitly updated the status    
    if "status" in changes:
        task.completed_at = (
            # the differece is that *if changes["status"]* would raise an error when "status" is absent.
            datetime.now(timezone.utc) if changes["status"] == "completed" else None
        )
    db.commit()
    db.refresh(task)
    return task
