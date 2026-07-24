from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.dependencies import get_current_user, get_db
from app.models import Milestone, Phase, User
from app.schemas.phase import (
    MilestoneCreate,
    MilestoneRead,
    MilestoneUpdate,
    PhaseCreate,
    PhaseRead,
    PhaseUpdate,
)


router = APIRouter()


def get_owned_phase(db: Session, user_id: int, phase_id: int) -> Phase:
    phase = db.scalar(
        select(Phase)
        .options(selectinload(Phase.milestones))
        .where(Phase.id == phase_id, Phase.user_id == user_id)
    )
    if phase is None:
        raise HTTPException(status_code=404, detail="Phase not found")
    return phase


def get_owned_milestone(
    db: Session,
    user_id: int,
    phase_id: int,
    milestone_id: int,
) -> Milestone:
    milestone = db.scalar(
        select(Milestone)
        .join(Phase)
        .where(
            Milestone.id == milestone_id,
            Milestone.phase_id == phase_id,
            Phase.user_id == user_id,
        )
    )
    if milestone is None:
        raise HTTPException(status_code=404, detail="Milestone not found")
    return milestone


@router.get("", response_model=list[PhaseRead])
def list_phases(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    include_archived: bool = Query(default=True),
) -> list[Phase]:
    query = (
        select(Phase)
        .options(selectinload(Phase.milestones))
        .where(Phase.user_id == user.id)
        .order_by(Phase.start_date, Phase.id)
    )
    if not include_archived:
        query = query.where(Phase.status != "archived")
    return list(db.scalars(query))


@router.post("", response_model=PhaseRead, status_code=status.HTTP_201_CREATED)
def create_phase(
    payload: PhaseCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Phase:
    phase = Phase(user_id=user.id, **payload.model_dump())
    db.add(phase)
    db.commit()
    return get_owned_phase(db, user.id, phase.id)


@router.patch("/{phase_id}", response_model=PhaseRead)
def update_phase(
    phase_id: int,
    payload: PhaseUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Phase:
    phase = get_owned_phase(db, user.id, phase_id)
    changes = payload.model_dump(exclude_unset=True)
    start_date = changes.get("start_date", phase.start_date)
    end_date = changes.get("end_date", phase.end_date)
    if end_date < start_date:
        raise HTTPException(
            status_code=422,
            detail="end_date must be on or after start_date",
        )
    for field, value in changes.items():
        setattr(phase, field, value)
    db.commit()
    return get_owned_phase(db, user.id, phase_id)


@router.delete("/{phase_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_phase(
    phase_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    phase = get_owned_phase(db, user.id, phase_id)
    db.delete(phase)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{phase_id}/milestones",
    response_model=MilestoneRead,
    status_code=status.HTTP_201_CREATED,
)
def create_milestone(
    phase_id: int,
    payload: MilestoneCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Milestone:
    get_owned_phase(db, user.id, phase_id)
    data = payload.model_dump()
    if data["position"] == 0:
        data["position"] = (
            db.scalar(
                select(func.coalesce(func.max(Milestone.position), -1)).where(
                    Milestone.phase_id == phase_id
                )
            )
            + 1
        )
    milestone = Milestone(phase_id=phase_id, **data)
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return milestone


@router.patch(
    "/{phase_id}/milestones/{milestone_id}",
    response_model=MilestoneRead,
)
def update_milestone(
    phase_id: int,
    milestone_id: int,
    payload: MilestoneUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Milestone:
    milestone = get_owned_milestone(
        db,
        user.id,
        phase_id,
        milestone_id,
    )
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(milestone, field, value)
    if "status" in changes and "progress" not in changes:
        if changes["status"] == "completed":
            milestone.progress = 100
        elif changes["status"] == "not_started":
            milestone.progress = 0
    db.commit()
    db.refresh(milestone)
    return milestone


@router.delete(
    "/{phase_id}/milestones/{milestone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_milestone(
    phase_id: int,
    milestone_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    milestone = get_owned_milestone(
        db,
        user.id,
        phase_id,
        milestone_id,
    )
    db.delete(milestone)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
