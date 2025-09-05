from __future__ import annotations

import pytest

from ume.calendar_routes import CalendarEventTimeError, validate_event_times


def test_valid_event_times():
    """Times with matching awareness and correct order are accepted."""
    validate_event_times(
        "2024-01-01T10:00:00+00:00",
        "2024-01-01T11:00:00+00:00",
    )


def test_end_before_start():
    """end_time earlier than start_time should raise an error."""
    with pytest.raises(CalendarEventTimeError):
        validate_event_times(
            "2024-01-01T11:00:00+00:00",
            "2024-01-01T10:00:00+00:00",
        )


def test_timezone_mixing_rejected():
    """Mixing naive and aware datetimes should be rejected."""
    with pytest.raises(CalendarEventTimeError):
        validate_event_times(
            "2024-01-01T10:00:00",
            "2024-01-01T11:00:00+00:00",
        )
