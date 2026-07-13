from datetime import date

from app.prompts.coaching_prompt import (
    COACHING_PROMPT_VERSION,
    COACHING_SYSTEM_PROMPT,
    build_coaching_user_prompt,
)
from app.schemas.coaching import CoachingContext, WorkloadAdjustment


def _context() -> CoachingContext:
    return CoachingContext(
        target_date=date(2026, 7, 11),
        energy_level="steady",
        mood_level="neutral",
        sleep_hours=6.5,
        stress_level=3,
        planned_tasks=4,
        completed_tasks=1,
        unfinished_tasks=3,
        recent_focus_minutes=90,
        recent_completion_rate=0.5,
        available_minutes=120,
        high_priority_tasks=["Finish coaching prompt"],
        user_notes="Prefer a quieter workday.",
    )


def _adjustment() -> WorkloadAdjustment:
    return WorkloadAdjustment(
        readiness_score=70,
        workload_multiplier=0.8,
        workload_level="reduced",
        reasons=["Insufficient sleep", "Steady but limited energy"],
    )


def test_coaching_system_prompt_is_versioned_and_requires_json():
    assert COACHING_PROMPT_VERSION == "phase2-v1"
    assert "Return valid JSON only" in COACHING_SYSTEM_PROMPT
    assert '"summary"' in COACHING_SYSTEM_PROMPT
    assert '"suggestions"' in COACHING_SYSTEM_PROMPT
    assert '"risk_factors"' in COACHING_SYSTEM_PROMPT
    assert '"planning_changes"' in COACHING_SYSTEM_PROMPT


def test_coaching_prompt_includes_structured_context_and_adjustment():
    context = _context()
    adjustment = _adjustment()

    prompt = build_coaching_user_prompt(context, adjustment)

    assert context.model_dump_json(indent=2) in prompt
    assert adjustment.model_dump_json(indent=2) in prompt
    assert "statistics already calculated" in prompt
    assert "use these values unchanged" in prompt
    assert "Return one JSON object" in prompt


def test_system_prompt_prevents_llm_recalculation():
    assert "Do not calculate database statistics" in COACHING_SYSTEM_PROMPT
    assert "Do not\n   recalculate" in COACHING_SYSTEM_PROMPT
    assert "Treat the calculated workload adjustment as authoritative" in (
        COACHING_SYSTEM_PROMPT
    )
