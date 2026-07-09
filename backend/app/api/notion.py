from datetime import date
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models import User
from app.schemas.weekly_goal import WeeklyGoalRead
from app.services.notion_service import (
    DailyReviewNotFoundError,
    NotionConfigurationError,
    notion_service,
)


router = APIRouter()


class ExportDailyReviewRequest(BaseModel):
    review_date: date | None = None


class ImportedWeeklyGoalsResponse(BaseModel):
    imported_count: int
    goals: list[WeeklyGoalRead]


class ExportDailyReviewResponse(BaseModel):
    notion_page_id: str


def _notion_http_error(exc: httpx.HTTPStatusError) -> HTTPException:
    try:
        body = exc.response.json()
        code = body.get("code", "unknown_error")
        message = body.get("message", "Request rejected")
    except (ValueError, AttributeError):
        code = "unknown_error"
        message = "Request rejected"
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=(
            f"Notion error ({exc.response.status_code}, {code}): {message}"
        ),
    )


@router.post(
    "/import-weekly-goals",
    response_model=ImportedWeeklyGoalsResponse,
)
async def import_weekly_goals(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ImportedWeeklyGoalsResponse:
    try:
        goals = await notion_service.import_weekly_goals(db, user.id)
        return ImportedWeeklyGoalsResponse(
            imported_count=len(goals),
            goals=[WeeklyGoalRead.model_validate(goal) for goal in goals],
        )
    except NotionConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        db.rollback()
        raise _notion_http_error(exc) from exc
    except (httpx.RequestError, KeyError, ValueError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Notion request failed",
        ) from exc


@router.post(
    "/export-daily-review",
    response_model=ExportDailyReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def export_daily_review(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    payload: ExportDailyReviewRequest | None = None,
) -> ExportDailyReviewResponse:
    try:
        page_id = await notion_service.export_daily_review(
            db, user.id, payload.review_date if payload else None
        )
        return ExportDailyReviewResponse(notion_page_id=page_id)
    except DailyReviewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NotionConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise _notion_http_error(exc) from exc
    except (httpx.RequestError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Notion request failed",
        ) from exc
