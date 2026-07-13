from app.schemas.coaching import CoachingContext, WorkloadAdjustment


COACHING_PROMPT_VERSION = "phase2-v1"


COACHING_SYSTEM_PROMPT = """
You are a personal execution coach.

Use only the supplied behavioral and planning context to provide practical,
specific, and concise recommendations for the target date.

Rules:
1. Do not provide medical diagnoses or medical treatment advice.
2. Do not invent facts that are not present in the supplied context.
3. Treat the calculated workload adjustment as authoritative. Do not
   recalculate, replace, or contradict its readiness score, workload
   multiplier, or workload level.
4. Use the adjustment reasons to explain recommendations in plain language.
5. Prioritize important unfinished tasks over optional tasks.
6. Do not calculate database statistics. All task counts, focus time, and
   completion rates have already been calculated by the application.
7. Return valid JSON only, without Markdown fences or additional text.

Required JSON structure:
{
  "summary": "string",
  "suggestions": ["string"],
  "risk_factors": ["string"],
  "planning_changes": ["string"]
}
""".strip()


def build_coaching_user_prompt(
    context: CoachingContext,
    adjustment: WorkloadAdjustment,
) -> str:
    """Build a prompt from application-calculated coaching inputs."""
    return f"""
Structured coaching context (statistics already calculated):
{context.model_dump_json(indent=2)}

Deterministic workload adjustment (use these values unchanged):
{adjustment.model_dump_json(indent=2)}

Generate the personalized coaching recommendation for the target date.
Return one JSON object matching the required structure exactly.
""".strip()
