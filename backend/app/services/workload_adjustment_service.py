from __future__ import annotations

from app.schemas.coaching import CoachingContext, WorkloadAdjustment


class WorkloadAdjustmentService:
    """Calculate repeatable workload guidance before any LLM call."""

    def calculate(self, context: CoachingContext) -> WorkloadAdjustment:
        score = 100.0
        reasons: list[str] = []

        if context.sleep_hours is not None:
            if context.sleep_hours < 5:
                score -= 35
                reasons.append("Very low sleep")
            elif context.sleep_hours < 7:
                score -= 25
                reasons.append("Insufficient sleep")

        if context.energy_level is not None:
            if context.energy_level == "depleted":
                score -= 30
                reasons.append("Depleted energy")
            elif context.energy_level == "low":
                score -= 25
                reasons.append("Low energy")
            elif context.energy_level == "steady":
                score -= 5
                reasons.append("Steady but limited energy")

        if context.mood_level is not None:
            if context.mood_level == "struggling":
                score -= 15
                reasons.append("Mood is struggling")
            elif context.mood_level == "low":
                score -= 10
                reasons.append("Low mood")

        if context.stress_level is not None:
            if context.stress_level >= 5:
                score -= 20
                reasons.append("Very high stress")
            elif context.stress_level >= 4:
                score -= 15
                reasons.append("High stress")

        if context.recent_completion_rate < 0.5:
            score -= 10
            reasons.append("Low recent completion rate")

        score = max(0.0, min(score, 100.0))

        if score >= 80:
            multiplier = 1.0
            level = "normal"
        elif score >= 50:
            multiplier = 0.8
            level = "reduced"
        else:
            multiplier = 0.6
            level = "light"

        return WorkloadAdjustment(
            readiness_score=score,
            workload_multiplier=multiplier,
            workload_level=level,
            reasons=reasons,
        )


workload_adjustment_service = WorkloadAdjustmentService()
