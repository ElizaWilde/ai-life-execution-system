from datetime import date
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models import CoachingRecommendation, User
from app.schemas.coaching import (
    CoachingRecommendationGenerateRequest,
    CoachingRecommendationRead,
    CoachingRecommendationResponse,
)
from app.services.coaching_service import coaching_service


router = APIRouter()


@router.post(
    "/daily/generate",
    response_model=CoachingRecommendationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_daily_recommendation(
    payload: CoachingRecommendationGenerateRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> CoachingRecommendationResponse:
    if not settings.ollama_api_key or settings.ollama_api_key == "your_ollama_api_key":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OLLAMA_API_KEY is not configured",
        )

    if _get_recommendation(db, user.id, payload.target_date) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Coaching recommendation already exists",
        )

    try:
        recommendation = await coaching_service.generate_daily_recommendation(
            db=db,
            user_id=user.id,
            target_date=payload.target_date,
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
            detail="Ollama Cloud returned an invalid coaching recommendation",
        ) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Coaching recommendation already exists",
        ) from exc

    return CoachingRecommendationResponse.from_recommendation(recommendation)


@router.get("/daily", response_model=CoachingRecommendationResponse)
def get_daily_recommendation(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    recommendation_date: Annotated[
        date | None,
        Query(alias="date", description="Recommendation date. Defaults to today."),
    ] = None,
) -> CoachingRecommendationResponse:
    recommendation = _get_recommendation(
        db,
        user.id,
        recommendation_date or date.today(),
    )
    if recommendation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coaching recommendation not found",
        )
    return _to_response(recommendation)


@router.get("/history", response_model=list[CoachingRecommendationResponse])
def get_recommendation_history(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[CoachingRecommendationResponse]:
    recommendations = db.scalars(
        select(CoachingRecommendation)
        .where(CoachingRecommendation.user_id == user.id)
        .order_by(
            CoachingRecommendation.recommendation_date.desc(),
            CoachingRecommendation.id.desc(),
        )
        .limit(limit)
    )
    return [_to_response(item) for item in recommendations]


def _get_recommendation(
    db: Session,
    user_id: int,
    recommendation_date: date,
) -> CoachingRecommendation | None:
    return db.scalar(
        select(CoachingRecommendation).where(
            CoachingRecommendation.user_id == user_id,
            CoachingRecommendation.recommendation_date == recommendation_date,
        )
    )


def _to_response(
    recommendation: CoachingRecommendation,
) -> CoachingRecommendationResponse:
    read_model = CoachingRecommendationRead.model_validate(recommendation)
    return CoachingRecommendationResponse.from_recommendation(read_model)
