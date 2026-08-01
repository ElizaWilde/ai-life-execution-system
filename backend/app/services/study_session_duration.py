from collections.abc import Iterable

from app.models import StudySession


def focused_seconds(session: StudySession) -> int:
    """Return exact active time, with compatibility for pre-migration rows."""
    if session.duration_seconds is not None:
        return max(0, session.duration_seconds)
    return max(0, (session.duration_minutes or 0) * 60)


def total_focused_seconds(sessions: Iterable[StudySession]) -> int:
    return sum(focused_seconds(session) for session in sessions)


def total_focused_minutes(sessions: Iterable[StudySession]) -> int:
    """Round only after combining sessions so short intervals are not lost."""
    return total_focused_seconds(sessions) // 60
