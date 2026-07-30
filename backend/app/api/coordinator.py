import httpx
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models import AutomationCommand, User
from app.schemas.command import CommandRead, CommandRequest
from app.schemas.coordinator import CoordinatorChatRequest, CoordinatorChatResponse
from app.services.coordinator_service import coordinator_service


router = APIRouter()


@router.post("/chat", response_model=CoordinatorChatResponse)
async def chat(request: CoordinatorChatRequest) -> CoordinatorChatResponse:
    if not settings.ollama_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OLLAMA_API_KEY is not configured",
        )

    try:
        reply = await coordinator_service.answer(
            message=request.message,
            history=[item.model_dump() for item in request.history],
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

    return CoordinatorChatResponse(reply=reply, model=settings.ollama_model)


@router.post("/commands", response_model=CommandRead)
def execute_command(
    payload: CommandRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AutomationCommand:
    try:
        return coordinator_service.process_command(
            db,
            user,
            payload.message,
            idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/commands", response_model=list[CommandRead])
def list_commands(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[AutomationCommand]:
    return list(
        db.scalars(
            select(AutomationCommand)
            .where(AutomationCommand.user_id == user.id)
            .order_by(AutomationCommand.created_at.desc(), AutomationCommand.id.desc())
            .limit(50)
        )
    )


@router.post("/commands/{command_id}/confirm", response_model=CommandRead)
def confirm_command(
    command_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AutomationCommand:
    try:
        return coordinator_service.confirm(db, user, command_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/commands/{command_id}/reject", response_model=CommandRead)
def reject_command(
    command_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AutomationCommand:
    try:
        return coordinator_service.reject(db, user.id, command_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
