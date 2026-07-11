from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models import DailyCheckIn, User
from app.schemas.daily_check_in import (
    DailyCheckInCreate,
    DailyCheckInRead,
    DailyCheckInUpdate,
)
from app.services.check_in_service import DuplicateCheckInError, check_in_service


router = APIRouter()


@router.post("", response_model=DailyCheckInRead, status_code=status.HTTP_201_CREATED)
def create_check_in(
    payload: DailyCheckInCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> DailyCheckIn:
    try:
        return check_in_service.create_check_in(db, user.id, payload)
    except DuplicateCheckInError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Daily check-in already exists",
        ) from exc


@router.get("", response_model=list[DailyCheckInRead])
def list_check_ins(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    start_date: Annotated[date, Query(description="First check-in date to include.")],
    end_date: Annotated[date, Query(description="Last check-in date to include.")],
) -> list[DailyCheckIn]:
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be on or after start_date",
        )
    return check_in_service.list_check_ins(db, user.id, start_date, end_date)


@router.get("/today", response_model=DailyCheckInRead)
def get_today_check_in(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> DailyCheckIn:
    check_in = check_in_service.get_check_in(db, user.id, date.today())
    if check_in is None:
        raise HTTPException(status_code=404, detail="Daily check-in not found")
    return check_in


@router.get("/{check_in_date}", response_model=DailyCheckInRead)
def get_check_in(
    check_in_date: date,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> DailyCheckIn:
    check_in = check_in_service.get_check_in(db, user.id, check_in_date)
    if check_in is None:
        raise HTTPException(status_code=404, detail="Daily check-in not found")
    return check_in


@router.patch("/{check_in_date}", response_model=DailyCheckInRead)
def update_check_in(
    check_in_date: date,
    payload: DailyCheckInUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> DailyCheckIn:
    check_in = check_in_service.update_check_in(db, user.id, check_in_date, payload)
    if check_in is None:
        raise HTTPException(status_code=404, detail="Daily check-in not found")
    return check_in
