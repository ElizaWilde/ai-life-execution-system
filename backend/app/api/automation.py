from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models import AutomationAudit, ReschedulingProposal, User
from app.schemas.intelligence import (
    AutomationAuditRead,
    ForecastHistoryRead,
    ProcrastinationEventRead,
)
from app.schemas.rescheduling_proposal import (
    ProposalStatus,
    ReschedulingProposalGenerateRequest,
    ReschedulingProposalRead,
)
from app.services.rescheduling_proposal_service import (
    InvalidProposalStateError,
    ReschedulingProposalNotFoundError,
    StaleProposalError,
    rescheduling_proposal_service,
)
from app.services.forecast_service import forecast_service
from app.services.procrastination_detection_service import (
    procrastination_detection_service,
)


router = APIRouter()


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ReschedulingProposalNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, StaleProposalError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=409, detail=str(exc))


@router.post(
    "/rescheduling-proposals",
    response_model=ReschedulingProposalRead | None,
    status_code=status.HTTP_201_CREATED,
)
def generate_rescheduling_proposal(
    payload: ReschedulingProposalGenerateRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ReschedulingProposal | None:
    return rescheduling_proposal_service.create_for_user(
        db,
        user.id,
        datetime.now(timezone.utc),
        horizon_days=payload.horizon_days,
    )


@router.get("/proposals", response_model=list[ReschedulingProposalRead])
def list_rescheduling_proposals(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    proposal_status: Annotated[ProposalStatus | None, Query(alias="status")] = None,
) -> list[ReschedulingProposal]:
    return rescheduling_proposal_service.list_for_user(
        db,
        user.id,
        proposal_status,
    )


@router.post(
    "/proposals/{proposal_id}/approve",
    response_model=ReschedulingProposalRead,
)
def approve_rescheduling_proposal(
    proposal_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ReschedulingProposal:
    try:
        return rescheduling_proposal_service.approve(db, user.id, proposal_id)
    except (
        ReschedulingProposalNotFoundError,
        InvalidProposalStateError,
    ) as exc:
        raise _handle_error(exc) from exc


@router.post(
    "/proposals/{proposal_id}/reject",
    response_model=ReschedulingProposalRead,
)
def reject_rescheduling_proposal(
    proposal_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ReschedulingProposal:
    try:
        return rescheduling_proposal_service.reject(db, user.id, proposal_id)
    except (
        ReschedulingProposalNotFoundError,
        InvalidProposalStateError,
    ) as exc:
        raise _handle_error(exc) from exc


@router.post(
    "/proposals/{proposal_id}/apply",
    response_model=ReschedulingProposalRead,
)
def apply_rescheduling_proposal(
    proposal_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ReschedulingProposal:
    try:
        return rescheduling_proposal_service.apply(db, user.id, proposal_id)
    except (
        ReschedulingProposalNotFoundError,
        InvalidProposalStateError,
        StaleProposalError,
    ) as exc:
        raise _handle_error(exc) from exc


@router.post(
    "/proposals/{proposal_id}/confirm",
    response_model=ReschedulingProposalRead,
)
def confirm_rescheduling_proposal(
    proposal_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ReschedulingProposal:
    try:
        return rescheduling_proposal_service.confirm(db, user.id, proposal_id)
    except (
        ReschedulingProposalNotFoundError,
        InvalidProposalStateError,
        StaleProposalError,
    ) as exc:
        raise _handle_error(exc) from exc


@router.post(
    "/procrastination-events/detect",
    response_model=list[ProcrastinationEventRead],
)
def detect_procrastination_events(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list:
    return procrastination_detection_service.detect(
        db,
        user.id,
        datetime.now(timezone.utc),
    )


@router.get(
    "/procrastination-events",
    response_model=list[ProcrastinationEventRead],
)
def list_procrastination_events(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    event_status: Annotated[str | None, Query(alias="status")] = "active",
) -> list:
    return procrastination_detection_service.list_for_user(
        db,
        user.id,
        status=event_status,
    )


@router.post("/forecasts/recalculate", response_model=list[ForecastHistoryRead])
def recalculate_forecasts(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list:
    return forecast_service.generate_for_user(
        db,
        user.id,
        datetime.now(timezone.utc),
    )


@router.get("/forecasts", response_model=list[ForecastHistoryRead])
def list_forecasts(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    latest_only: bool = True,
) -> list:
    return forecast_service.list_for_user(
        db,
        user.id,
        latest_only=latest_only,
    )


@router.get("/audits", response_model=list[AutomationAuditRead])
def list_automation_audits(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AutomationAudit]:
    return list(
        db.scalars(
            select(AutomationAudit)
            .where(AutomationAudit.user_id == user.id)
            .order_by(AutomationAudit.created_at.desc(), AutomationAudit.id.desc())
            .limit(limit)
        )
    )
