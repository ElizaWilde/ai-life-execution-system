from datetime import date

from app.schemas.coaching import CoachingContext
from app.services.workload_adjustment_service import workload_adjustment_service


def _context(**overrides) -> CoachingContext:
    defaults = {
        "target_date": date.today(),
        "energy_level": "high",
        "mood_level": "good",
        "sleep_hours": 7.5,
        "stress_level": 1,
        "planned_tasks": 3,
        "completed_tasks": 2,
        "unfinished_tasks": 1,
        "recent_focus_minutes": 120,
        "recent_completion_rate": 0.75,
        "available_minutes": 180,
        "high_priority_tasks": ["Ship Phase 2"],
        "user_notes": None,
    }
    defaults.update(overrides)
    return CoachingContext(**defaults)


def test_normal_sleep_and_high_energy_keep_normal_workload():
    adjustment = workload_adjustment_service.calculate(_context())

    assert adjustment.readiness_score == 100.0
    assert adjustment.workload_multiplier == 1.0
    assert adjustment.workload_level == "normal"
    assert adjustment.reasons == []


def test_low_sleep_reduces_workload():
    adjustment = workload_adjustment_service.calculate(
        _context(sleep_hours=6.0)
    )

    assert adjustment.readiness_score == 75.0
    assert adjustment.workload_multiplier == 0.8
    assert adjustment.workload_level == "reduced"
    assert adjustment.reasons == ["Insufficient sleep"]


def test_depleted_energy_high_stress_and_low_sleep_make_light_workload():
    adjustment = workload_adjustment_service.calculate(
        _context(
            energy_level="depleted",
            mood_level="struggling",
            sleep_hours=4.5,
            stress_level=5,
            recent_completion_rate=0.25,
        )
    )

    assert adjustment.readiness_score == 0.0
    assert adjustment.workload_multiplier == 0.6
    assert adjustment.workload_level == "light"
    assert adjustment.reasons == [
        "Very low sleep",
        "Depleted energy",
        "Mood is struggling",
        "Very high stress",
        "Low recent completion rate",
    ]


def test_score_never_exceeds_100():
    adjustment = workload_adjustment_service.calculate(
        _context(
            energy_level="energized",
            mood_level="great",
            sleep_hours=9.0,
            stress_level=1,
            recent_completion_rate=1.0,
        )
    )

    assert adjustment.readiness_score == 100.0
    assert adjustment.workload_level == "normal"


def test_score_never_goes_below_zero():
    adjustment = workload_adjustment_service.calculate(
        _context(
            energy_level="depleted",
            mood_level="struggling",
            sleep_hours=2.0,
            stress_level=5,
            recent_completion_rate=0.0,
        )
    )

    assert adjustment.readiness_score == 0.0
    assert adjustment.workload_level == "light"
