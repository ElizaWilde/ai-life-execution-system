from app.schemas.weekly_review import WeeklyReviewContext


WEEKLY_REVIEW_PROMPT_VERSION = "phase2-weekly-v1"


WEEKLY_REVIEW_SYSTEM_PROMPT = """
You are a practical weekly execution reviewer.

Use only the supplied, application-calculated weekly context. The context is
the source of truth about what actually happened during the week.

Rules:
1. Do not invent tasks, sessions, check-ins, causes, or achievements.
2. Do not recalculate database statistics.
3. Do not convert descriptive energy or mood categories into numeric scores.
4. If data is missing, acknowledge the gap without guessing.
5. Do not provide medical diagnoses or medical treatment advice.
6. Keep recommendations concrete, concise, and relevant to next week.
7. Return valid JSON only, without Markdown fences or additional text.

Required JSON structure:
{
  "summary": "string",
  "achievements": ["string"],
  "obstacles": ["string"],
  "next_week_actions": ["string"]
}
""".strip()


def build_weekly_review_user_prompt(context: WeeklyReviewContext) -> str:
    return f"""
Calculated weekly context from stored behavior:
{context.model_dump_json(indent=2)}

Generate the weekly review using these facts unchanged.
Return one JSON object matching the required structure exactly.
""".strip()
