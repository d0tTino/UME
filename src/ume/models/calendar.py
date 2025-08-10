"""Calendar event node model and factory helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import uuid

SCHEMA_VERSION = "3.0"


@dataclass
class CalendarEvent:
    """Represents a calendar event in the graph."""

    id: str
    title: str
    start: datetime
    end: datetime | None = None
    description: str | None = None
    is_all_day: bool = False
    location: str | None = None
    status: str | None = None
    rrule: str | None = None
    visibility: str | None = None
    schema_version: str = SCHEMA_VERSION


def create_calendar_event(
    title: str,
    start: datetime,
    end: datetime | None = None,
    *,
    description: str | None = None,
    event_id: str | None = None,
    is_all_day: bool = False,
    location: str | None = None,
    status: str | None = None,
    rrule: str | None = None,
    visibility: str | None = None,
) -> CalendarEvent:
    """Factory helper to build :class:`CalendarEvent` instances."""

    return CalendarEvent(
        id=event_id or str(uuid.uuid4()),
        title=title,
        start=start,
        end=end,
        description=description,
        is_all_day=is_all_day,
        location=location,
        status=status,
        rrule=rrule,
        visibility=visibility,
    )
