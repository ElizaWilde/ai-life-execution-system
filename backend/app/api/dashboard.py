from datetime import date
from typing import Annotated

'''
    Query is a FastAPI function used to declare and configure URL query parameters.
'''
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models import User
from app.schemas.dashboard import TodayDashboardResponse, WeekDashboardResponse
from app.services.stats_service import stats_service


router = APIRouter()


@router.get("/today", response_model=TodayDashboardResponse)
def get_today_dashboard(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    target_date: Annotated[
        date | None,
        # Query(...)tells FastAPI that this value must be read from the URL query string. It can also contain validation rules and documentation metadata.
        Query(
            # alias means the URL parameter is called date, even though the Python variable is called target_date
            alias="date",
            # adds an explanation to FastAPI’s generated Swagger documentation at /docs
            description="Dashboard date. Defaults to today.",
        ),
    ] = None,
) -> TodayDashboardResponse:
    return stats_service.get_today_dashboard(
        db=db,
        user_id=user.id,
        target_date=target_date,
    )


@router.get("/week", response_model=WeekDashboardResponse)
def get_week_dashboard(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    target_date: Annotated[
        date | None,
        Query(
            alias="date",
            description="Any date in the week to summarize. Defaults to today.",
        ),
    ] = None,
) -> WeekDashboardResponse:
    return stats_service.get_week_dashboard(
        db=db,
        user_id=user.id,
        target_date=target_date,
    )
