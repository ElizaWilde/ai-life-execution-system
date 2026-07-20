from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models import ParkedThought, User
from app.schemas.parked_thought import (
    ParkedThoughtCreate,
    ParkedThoughtRead,
    ParkedThoughtUpdate,
)


router = APIRouter()


@router.get("", response_model=list[ParkedThoughtRead])
def list_parked_thoughts(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[ParkedThought]:
    return list(
        db.scalars(
            select(ParkedThought)
            .where(ParkedThought.user_id == user.id)
            .order_by(
                ParkedThought.completed,
                ParkedThought.created_at.desc(),
                ParkedThought.id.desc(),
            )
            .limit(100)
        )
    )


@router.post("", response_model=ParkedThoughtRead, status_code=status.HTTP_201_CREATED)
def create_parked_thought(
    payload: ParkedThoughtCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ParkedThought:
    thought = ParkedThought(user_id=user.id, content=payload.content)
    db.add(thought)
    db.commit()
    db.refresh(thought)
    return thought


@router.patch("/{thought_id}", response_model=ParkedThoughtRead)
def update_parked_thought(
    thought_id: int,
    payload: ParkedThoughtUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ParkedThought:
    thought = db.scalar(
        select(ParkedThought).where(
            ParkedThought.id == thought_id,
            ParkedThought.user_id == user.id,
        )
    )
    if thought is None:
        raise HTTPException(status_code=404, detail="Parked thought not found")

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(thought, field, value)
    if "completed" in changes:
        thought.completed_at = (
            datetime.now(timezone.utc) if changes["completed"] else None
        )
    db.commit()
    db.refresh(thought)
    return thought


@router.delete("/{thought_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_parked_thought(
    thought_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    thought = db.scalar(
        select(ParkedThought).where(
            ParkedThought.id == thought_id,
            ParkedThought.user_id == user.id,
        )
    )
    if thought is None:
        raise HTTPException(status_code=404, detail="Parked thought not found")
    db.delete(thought)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
