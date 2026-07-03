import httpx
from fastapi import APIRouter, HTTPException, status

from app.config import settings
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
