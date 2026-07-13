import asyncio

import httpx
import pytest

from app.services.llm_service import LLMResponseError, LLMService


class FakeAsyncClient:
    response: httpx.Response
    request: dict | None = None
    configured_timeout: float | None = None

    def __init__(self, timeout: float):
        type(self).configured_timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url: str, *, headers: dict, json: dict):
        type(self).request = {
            "url": url,
            "headers": headers,
            "json": json,
        }
        return type(self).response


def _response(status_code: int, content) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=content,
        request=httpx.Request("POST", "https://ollama.test/api/chat"),
    )


def _service() -> LLMService:
    service = LLMService()
    service.base_url = "https://ollama.test"
    service.model = "test-model"
    service.api_key = "test-key"
    service.timeout = 42
    return service


def test_generate_json_requests_json_mode_and_returns_dictionary(monkeypatch):
    FakeAsyncClient.response = _response(
        200,
        {
            "message": {
                "content": '{"summary":"Focus on one task","suggestions":[]}'
            }
        },
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    result = asyncio.run(
        _service().generate_json(
            system_prompt="Return JSON.",
            user_prompt="Create coaching advice.",
        )
    )

    assert result == {
        "summary": "Focus on one task",
        "suggestions": [],
    }
    assert FakeAsyncClient.configured_timeout == 42
    assert FakeAsyncClient.request == {
        "url": "https://ollama.test/api/chat",
        "headers": {"Authorization": "Bearer test-key"},
        "json": {
            "model": "test-model",
            "messages": [
                {"role": "system", "content": "Return JSON."},
                {"role": "user", "content": "Create coaching advice."},
            ],
            "stream": False,
            "format": "json",
        },
    }


def test_generate_json_rejects_invalid_json(monkeypatch):
    FakeAsyncClient.response = _response(
        200,
        {"message": {"content": "not-json"}},
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    with pytest.raises(LLMResponseError, match="returned invalid JSON"):
        asyncio.run(_service().generate_json("system", "user"))


def test_generate_json_rejects_non_object_json(monkeypatch):
    FakeAsyncClient.response = _response(
        200,
        {"message": {"content": '[{"summary":"not an object"}]'}},
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    with pytest.raises(LLMResponseError, match="must be an object"):
        asyncio.run(_service().generate_json("system", "user"))


def test_generate_json_detects_non_200_response(monkeypatch):
    FakeAsyncClient.response = _response(502, {"error": "upstream failure"})
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(_service().generate_json("system", "user"))
