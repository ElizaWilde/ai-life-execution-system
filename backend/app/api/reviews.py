from datetime import date
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models import DailyReview, User
from app.schemas.review import (
    DailyReviewCreate,
    DailyReviewGenerateRequest,
    DailyReviewRead,
)
from app.services.review_service import review_service


router = APIRouter()


@router.post("", response_model=DailyReviewRead, status_code=status.HTTP_201_CREATED)
def create_daily_review(
    payload: DailyReviewCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> DailyReview:
    existing_review = _get_review(db, user.id, payload.review_date)
    if existing_review is not None:
        raise HTTPException(status_code=409, detail="Daily review already exists")

    review = DailyReview(
        user_id=user.id,
        review_date=payload.review_date,
        summary=payload.summary,
        tomorrow_adjustment=payload.tomorrow_adjustment,
        source=payload.source,
        planned_tasks=0,
        completed_tasks=0,
        focus_minutes=0,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@router.post(
    "/generate",
    response_model=DailyReviewRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_daily_review(
    payload: DailyReviewGenerateRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> DailyReviewRead:
    if not settings.ollama_api_key or settings.ollama_api_key == "your_ollama_api_key":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OLLAMA_API_KEY is not configured",
        )

    try:
        return await review_service.generate_daily_review(
            db=db,
            user_id=user.id,
            review_date=payload.review_date,
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
    except (httpx.RequestError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Ollama Cloud request failed",
        ) from exc


@router.get("/daily", response_model=DailyReviewRead)
def get_daily_review(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    review_date: Annotated[
        date | None,
        Query(
            alias="date",
            description="Review date. Defaults to today.",
        ),
    ] = None,
) -> DailyReview:
    target_date = review_date or date.today()
    review = _get_review(db, user.id, target_date)
    if review is None:
        raise HTTPException(status_code=404, detail="Daily review not found")
    return review


def _get_review(db: Session, user_id: int, review_date: date) -> DailyReview | None:
    return db.scalar(
        select(DailyReview).where(
            DailyReview.user_id == user_id,
            DailyReview.review_date == review_date,
        )
    )
