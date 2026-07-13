import asyncio
from datetime import date
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.config import settings
from app.models import CoachingRecommendation
from app.prompts.coaching_prompt import (
    COACHING_SYSTEM_PROMPT,
    build_coaching_user_prompt,
)
from app.schemas.coaching import CoachingContext, WorkloadAdjustment
from app.services.coaching_service import (
    InvalidCoachingResponseError,
    PendingSessionChangesError,
    coaching_service,
)
from app.services.coaching_context_service import coaching_context_service
from app.services.llm_service import llm_service
from app.services.workload_adjustment_service import workload_adjustment_service
from conftest import TestingSessionLocal


TARGET_DATE = date(2026, 7, 12)


def _context() -> CoachingContext:
    return CoachingContext(
        target_date=TARGET_DATE,
        energy_level="steady",
        mood_level="neutral",
        sleep_hours=6.5,
        stress_level=3,
        planned_tasks=3,
        completed_tasks=1,
        unfinished_tasks=2,
        recent_focus_minutes=90,
        recent_completion_rate=0.5,
        available_minutes=None,
        high_priority_tasks=["Finish CoachingService"],
        user_notes=None,
    )


def _adjustment() -> WorkloadAdjustment:
    return WorkloadAdjustment(
        readiness_score=70,
        workload_multiplier=0.8,
        workload_level="reduced",
        reasons=["Insufficient sleep", "Steady but limited energy"],
    )


def _llm_result() -> dict:
    return {
        "summary": "Use a reduced workload and finish one important task.",
        "suggestions": ["Finish CoachingService first."],
        "risk_factors": ["Insufficient sleep."],
        "planning_changes": ["Move optional work to tomorrow."],
    }


def test_generate_daily_recommendation_closes_read_transaction_and_saves(
    monkeypatch,
):
    context = _context()
    adjustment = _adjustment()

    monkeypatch.setattr(
        coaching_context_service,
        "build_daily_context",
        lambda **kwargs: context,
    )
    monkeypatch.setattr(
        workload_adjustment_service,
        "calculate",
        lambda supplied_context: adjustment,
    )

    with TestingSessionLocal() as db:
        db.get(CoachingRecommendation, -1)
        assert db.in_transaction()

        async def generate_json(**kwargs):
            assert not db.in_transaction()
            return _llm_result()

        generate = AsyncMock(side_effect=generate_json)
        monkeypatch.setattr(llm_service, "generate_json", generate)

        result = asyncio.run(
            coaching_service.generate_daily_recommendation(
                db=db,
                user_id=1,
                target_date=TARGET_DATE,
            )
        )

        saved = db.scalar(
            select(CoachingRecommendation).where(
                CoachingRecommendation.user_id == 1,
                CoachingRecommendation.recommendation_date == TARGET_DATE,
            )
        )

    assert saved is not None
    assert result.id == saved.id
    assert result.workload_level == "reduced"
    assert result.adjustment_reasons_json == adjustment.reasons
    assert result.summary == _llm_result()["summary"]
    assert result.recommendations_json.suggestions == [
        "Finish CoachingService first."
    ]
    assert result.model_name == settings.ollama_model
    assert result.prompt_version == "phase2-v1"
    generate.assert_awaited_once_with(
        system_prompt=COACHING_SYSTEM_PROMPT,
        user_prompt=build_coaching_user_prompt(context, adjustment),
    )


def test_invalid_llm_recommendation_is_not_saved(monkeypatch):
    monkeypatch.setattr(
        coaching_context_service,
        "build_daily_context",
        lambda **kwargs: _context(),
    )
    monkeypatch.setattr(
        workload_adjustment_service,
        "calculate",
        lambda supplied_context: _adjustment(),
    )
    monkeypatch.setattr(
        llm_service,
        "generate_json",
        AsyncMock(return_value={"summary": "Missing required fields"}),
    )

    with TestingSessionLocal() as db:
        with pytest.raises(InvalidCoachingResponseError):
            asyncio.run(
                coaching_service.generate_daily_recommendation(
                    db=db,
                    user_id=1,
                    target_date=TARGET_DATE,
                )
            )

        assert db.scalar(select(CoachingRecommendation)) is None


def test_pending_session_changes_are_not_rolled_back_or_sent_to_llm(monkeypatch):
    generate = AsyncMock(return_value=_llm_result())
    monkeypatch.setattr(llm_service, "generate_json", generate)

    with TestingSessionLocal() as db:
        pending = CoachingRecommendation(
            user_id=1,
            recommendation_date=TARGET_DATE,
            readiness_score=100,
            workload_multiplier=1,
            workload_level="normal",
            adjustment_reasons_json=[],
            summary="Pending caller change",
            recommendations_json=_llm_result(),
            model_name="test",
            prompt_version="test",
        )
        db.add(pending)

        with pytest.raises(PendingSessionChangesError):
            asyncio.run(
                coaching_service.generate_daily_recommendation(
                    db=db,
                    user_id=1,
                    target_date=TARGET_DATE,
                )
            )

        assert pending in db.new
        generate.assert_not_awaited()
