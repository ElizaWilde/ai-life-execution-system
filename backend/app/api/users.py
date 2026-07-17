from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models import User
from app.schemas.user import UserRead, UserUpdate
from app.services.user_service import DuplicateUserEmailError, user_service


router = APIRouter()


@router.get("/me", response_model=UserRead)
def get_my_profile(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    return user


@router.patch("/me", response_model=UserRead)
def update_my_profile(
    payload: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    try:
        return user_service.update(db, user, payload)
    except DuplicateUserEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
