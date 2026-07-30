from datetime import date, timedelta
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models import PlanPreview, User
from app.schemas.planning_automation import (
    DailyPlanPreviewCreate,
    DailyPlanPreviewRead,
    EstimationCalibrationRead,
    WeeklyPlanPreviewCreate,
    WeeklyPlanPreviewRead,
)
from app.services.estimation_calibration_service import estimation_calibration_service
from app.services.plan_preview_service import (
    InvalidPlanPreviewStateError,
    PlanPreviewNotFoundError,
    plan_preview_service,
)
from app.services.planning_service import MissingActiveWeeklyGoalError


router = APIRouter()


def _daily_response(preview: PlanPreview) -> DailyPlanPreviewRead:
    payload = preview.payload_json
    return DailyPlanPreviewRead(
        id=preview.id,
        status=preview.status,
        target_date=preview.target_date,
        input_minutes=preview.input_minutes,
        recommended_minutes=preview.recommended_minutes,
        calibration=payload["calibration"],
        workload_level=payload["workload_level"],
        readiness_score=payload["readiness_score"],
        tasks=payload["tasks"],
        expires_at=preview.expires_at,
        confirmed_at=preview.confirmed_at,
        created_at=preview.created_at,
    )


def _weekly_response(preview: PlanPreview) -> WeeklyPlanPreviewRead:
    payload = preview.payload_json
    return WeeklyPlanPreviewRead(
        id=preview.id,
        status=preview.status,
        week_start=preview.target_date,
        week_end=payload["week_end"],
        intended_minutes=preview.input_minutes,
        recommended_minutes=preview.recommended_minutes,
        historical_weekly_focus_minutes=payload[
            "historical_weekly_focus_minutes"
        ],
        historical_completion_rate=payload["historical_completion_rate"],
        calibration=payload["calibration"],
        rationale=payload["rationale"],
        goal_allocations=payload["goal_allocations"],
        daily_allocations=payload["daily_allocations"],
        expires_at=preview.expires_at,
        confirmed_at=preview.confirmed_at,
        created_at=preview.created_at,
    )


@router.get("/calibration", response_model=EstimationCalibrationRead)
def get_estimation_calibration(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return estimation_calibration_service.calculate(db, user.id).as_dict()


@router.post(
    "/daily-previews",
    response_model=DailyPlanPreviewRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_daily_preview(
    payload: DailyPlanPreviewCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> DailyPlanPreviewRead:
    if not settings.ollama_api_key or settings.ollama_api_key == "your_ollama_api_key":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OLLAMA_API_KEY is not configured",
        )
    try:
        preview = await plan_preview_service.create_daily(
            db,
            user.id,
            payload.target_date,
            payload.available_minutes,
            payload.user_instruction,
            payload.base_preview_id,
        )
    except MissingActiveWeeklyGoalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PlanPreviewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidPlanPreviewStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama Cloud error ({exc.response.status_code})",
        ) from exc
    except (httpx.RequestError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Ollama Cloud request failed") from exc
    return _daily_response(preview)


@router.get("/daily-previews/latest", response_model=DailyPlanPreviewRead | None)
def get_latest_daily_preview(
    target_date: Annotated[date, Query()],
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> DailyPlanPreviewRead | None:
    preview = plan_preview_service.latest(db, user.id, "daily", target_date)
    return _daily_response(preview) if preview is not None else None


@router.post(
    "/daily-previews/{preview_id}/confirm",
    response_model=DailyPlanPreviewRead,
)
def confirm_daily_preview(
    preview_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> DailyPlanPreviewRead:
    try:
        preview = plan_preview_service.get(db, user.id, preview_id)
        if preview.preview_type != "daily":
            raise InvalidPlanPreviewStateError("This is not a daily plan preview.")
        return _daily_response(
            plan_preview_service.confirm(db, user.id, preview_id)
        )
    except PlanPreviewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidPlanPreviewStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/weekly-previews",
    response_model=WeeklyPlanPreviewRead,
    status_code=status.HTTP_201_CREATED,
)
def create_weekly_preview(
    payload: WeeklyPlanPreviewCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> WeeklyPlanPreviewRead:
    try:
        return _weekly_response(
            plan_preview_service.create_weekly(
                db,
                user.id,
                payload.week_start,
                payload.intended_minutes,
            )
        )
    except MissingActiveWeeklyGoalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/weekly-previews/latest", response_model=WeeklyPlanPreviewRead | None)
def get_latest_weekly_preview(
    week_start: Annotated[date, Query()],
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> WeeklyPlanPreviewRead | None:
    normalized = week_start - timedelta(days=week_start.weekday())
    preview = plan_preview_service.latest(db, user.id, "weekly", normalized)
    return _weekly_response(preview) if preview is not None else None


@router.post(
    "/weekly-previews/{preview_id}/confirm",
    response_model=WeeklyPlanPreviewRead,
)
def confirm_weekly_preview(
    preview_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> WeeklyPlanPreviewRead:
    try:
        preview = plan_preview_service.get(db, user.id, preview_id)
        if preview.preview_type != "weekly":
            raise InvalidPlanPreviewStateError("This is not a weekly plan preview.")
        return _weekly_response(
            plan_preview_service.confirm(db, user.id, preview_id)
        )
    except PlanPreviewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidPlanPreviewStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
