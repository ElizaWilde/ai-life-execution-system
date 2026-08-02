from collections.abc import Iterable

from sqlalchemy import func

from app.models import StudySession


MINIMUM_COUNTED_FOCUS_SECONDS = 3 * 60


def focused_seconds(session: StudySession) -> int:
    """Return exact active time, with compatibility for pre-migration rows."""
    if session.duration_seconds is not None:
        return max(0, session.duration_seconds)
    return max(0, (session.duration_minutes or 0) * 60)


def is_counted_focus_session(session: StudySession) -> bool:
    """Return whether a completed session is long enough for statistics."""
    return focused_seconds(session) >= MINIMUM_COUNTED_FOCUS_SECONDS


def counted_focus_session_clause():
    """Build the SQL predicate matching :func:`is_counted_focus_session`."""
    return (
        func.coalesce(
            StudySession.duration_seconds,
            StudySession.duration_minutes * 60,
            0,
        )
        >= MINIMUM_COUNTED_FOCUS_SECONDS
    )


def total_focused_seconds(sessions: Iterable[StudySession]) -> int:
    return sum(
        focused_seconds(session)
        for session in sessions
        if is_counted_focus_session(session)
    )


def total_focused_minutes(sessions: Iterable[StudySession]) -> int:
    """Round only after combining sessions so short intervals are not lost."""
    return total_focused_seconds(sessions) // 60
