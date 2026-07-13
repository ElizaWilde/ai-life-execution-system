'''
Responsible for:
    Call LLM
    Generate daily plan
    Generate daily review
    Return structured JSON
'''
import json
import httpx

from app.config import settings


class LLMResponseError(ValueError):
    """Raised when Ollama returns a response that violates the requested shape."""


class LLMService:
    def __init__(self):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self.api_key = settings.ollama_api_key
        self.timeout = settings.ollama_timeout_seconds

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        return await self._request_chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            history=history,
        )

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> dict:
        """Request and validate a JSON object from the configured Ollama model."""
        raw = await self._request_chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format="json",
        )

        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMResponseError("Ollama returned invalid JSON") from exc

        if not isinstance(result, dict):
            raise LLMResponseError("Ollama JSON response must be an object")

        return result

    async def _request_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        history: list[dict[str, str]] | None = None,
        response_format: str | None = None,
    ) -> str:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": user_prompt})
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if response_format is not None:
            payload["format"] = response_format

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

        data = response.json()
        try:
            content = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise LLMResponseError("Ollama returned an invalid chat response") from exc

        if not isinstance(content, str):
            raise LLMResponseError("Ollama chat content must be a string")

        return content

    async def generate_daily_plan(
        self,
        weekly_goals: list[dict],
        unfinished_tasks: list[dict],
        available_minutes: int,
    ) -> list[dict]:
        system_prompt = """
You are a planning assistant.

Generate a realistic daily execution plan from weekly goals.

Rules:
- Do not overload the user.
- Prefer urgent unfinished tasks.
- Split large goals into small tasks.
- Each task must have a title, estimated_minutes, and priority.
- Output JSON only.
"""

        user_prompt = f"""
Weekly goals:
{json.dumps(weekly_goals, ensure_ascii=False, indent=2)}

Unfinished tasks:
{json.dumps(unfinished_tasks, ensure_ascii=False, indent=2)}

Available minutes today:
{available_minutes}

Return JSON array only.
"""

        raw = await self.chat(system_prompt, user_prompt)

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return [
                {
                    "title": "Review generated plan manually",
                    "estimated_minutes": 30,
                    "priority": "medium",
                    "raw_model_output": raw,
                }
            ]

    async def generate_daily_review(
        self,
        planned_tasks: list[dict],
        completed_tasks: list[dict],
        study_sessions: list[dict],
    ) -> str:
        system_prompt = """
You are a daily review assistant.

Write a short practical daily review.
Do not give generic motivation.
Focus on execution, unfinished work, and tomorrow's adjustment.
"""

        user_prompt = f"""
Planned tasks:
{json.dumps(planned_tasks, ensure_ascii=False, indent=2)}

Completed tasks:
{json.dumps(completed_tasks, ensure_ascii=False, indent=2)}

Study sessions:
{json.dumps(study_sessions, ensure_ascii=False, indent=2)}
"""

        return await self.chat(system_prompt, user_prompt)


llm_service = LLMService()
