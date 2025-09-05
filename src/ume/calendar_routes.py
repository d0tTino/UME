from __future__ import annotations

"""Calendar event endpoints and helpers."""

from datetime import datetime, timezone


class CalendarEventTimeError(ValueError):
    """Raised when calendar event times are invalid."""


def validate_event_times(start_time: str, end_time: str) -> None:
    """Validate start and end times for a calendar event.

    Both ``start_time`` and ``end_time`` should be ISO 8601 strings. They must
    either both include timezone information or both be naive. If they are
    timezone-aware they will be normalised to UTC before comparison. The
    function raises :class:`CalendarEventTimeError` if ``end_time`` does not
    occur after ``start_time`` or if the timezone awareness of the values
    differs.
    """
    try:
        start = datetime.fromisoformat(start_time)
        end = datetime.fromisoformat(end_time)
    except ValueError as exc:
        raise CalendarEventTimeError("Invalid datetime format") from exc

    # Guard against mixing aware and naive datetimes
    if (start.tzinfo is None) != (end.tzinfo is None):
        raise CalendarEventTimeError(
            "start_time and end_time must both be timezone-aware or both naive"
        )

    if start.tzinfo is not None and end.tzinfo is not None:
        start = start.astimezone(timezone.utc)
        end = end.astimezone(timezone.utc)

    if end <= start:
        raise CalendarEventTimeError("end_time must occur after start_time")
