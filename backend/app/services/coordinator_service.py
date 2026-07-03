from app.services.llm_service import llm_service


COORDINATOR_SYSTEM_PROMPT = """You are the Coordinator Agent for an AI Life Execution System.
Answer the user's questions clearly and practically.
For now, this is a basic conversation test: do not claim to have used tools, changed plans,
or saved memories. If the user asks for an unavailable action, explain what would be needed.
Keep answers concise unless the user asks for detail."""


class CoordinatorService:
    async def answer(self, message: str, history: list[dict[str, str]]) -> str:
        return await llm_service.chat(
            system_prompt=COORDINATOR_SYSTEM_PROMPT,
            user_prompt=message,
            history=history,
        )


coordinator_service = CoordinatorService()
