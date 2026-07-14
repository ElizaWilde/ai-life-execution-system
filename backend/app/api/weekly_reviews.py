from datetime import date
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models import User, WeeklyReview
from app.schemas.weekly_review import WeeklyReviewGenerateRequest, WeeklyReviewRead
from app.services.weekly_review_service import weekly_review_service


router = APIRouter()


@router.post(
    "/generate",
    response_model=WeeklyReviewRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_weekly_review(
    payload: WeeklyReviewGenerateRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> WeeklyReviewRead:
    if not settings.ollama_api_key or settings.ollama_api_key == "your_ollama_api_key":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OLLAMA_API_KEY is not configured",
        )

    try:
        return await weekly_review_service.generate_weekly_review(
            db=db,
            user_id=user.id,
            week_start=payload.week_start,
        )
    except httpx.HTTPStatusError as exc:
        try:
            upstream_detail = exc.response.json().get("error", "request rejected")
        except (ValueError, AttributeError):
            upstream_detail = "request rejected"
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ollama Cloud error ({exc.response.status_code}): {upstream_detail}",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Ollama Cloud request failed",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Ollama Cloud returned an invalid weekly review",
        ) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Weekly review generation conflicted with another request",
        ) from exc


@router.get("/current", response_model=WeeklyReviewRead)
def get_current_weekly_review(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> WeeklyReview:
    review = _get_weekly_review(
        db,
        user.id,
        weekly_review_service.current_week_start(),
    )
    if review is None:
        raise HTTPException(status_code=404, detail="Weekly review not found")
    return review


@router.get("/{week_start}", response_model=WeeklyReviewRead)
def get_weekly_review(
    week_start: date,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> WeeklyReview:
    if week_start.weekday() != 0:
        raise HTTPException(status_code=400, detail="week_start must be a Monday")
    review = _get_weekly_review(db, user.id, week_start)
    if review is None:
        raise HTTPException(status_code=404, detail="Weekly review not found")
    return review


@router.get("", response_model=list[WeeklyReviewRead])
def list_weekly_reviews(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[WeeklyReview]:
    return list(
        db.scalars(
            select(WeeklyReview)
            .where(WeeklyReview.user_id == user.id)
            .order_by(WeeklyReview.week_start.desc(), WeeklyReview.id.desc())
            .limit(limit)
        )
    )


def _get_weekly_review(
    db: Session,
    user_id: int,
    week_start: date,
) -> WeeklyReview | None:
    return db.scalar(
        select(WeeklyReview).where(
            WeeklyReview.user_id == user_id,
            WeeklyReview.week_start == week_start,
        )
    )
