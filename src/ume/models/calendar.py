"""Calendar event node model and factory helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import uuid

SCHEMA_VERSION = "3.0.0"


@dataclass
class CalendarEventStatus(str, Enum):
    """Possible participation statuses for a calendar event."""

    TENTATIVE = "tentative"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class CalendarEventVisibility(str, Enum):
    """Visibility levels for a calendar event."""

    PUBLIC_TO_GROUP = "public_to_group"
    PRIVATE = "private"


@dataclass
class CalendarEvent:
    """Represents a calendar event in the graph."""

    id: str
    title: str
    start_time: datetime
    end_time: datetime | None = None
    description: str | None = None
    is_all_day: bool = False
    location: str | None = None
    status: CalendarEventStatus | None = None
    rrule: str | None = None
    visibility: CalendarEventVisibility | None = None
    schema_version: str = SCHEMA_VERSION


def create_calendar_event(
    title: str,
    start_time: datetime,
    end_time: datetime | None = None,
    *,
    description: str | None = None,
    event_id: str | None = None,
    is_all_day: bool = False,
    location: str | None = None,
    status: CalendarEventStatus | None = None,
    rrule: str | None = None,
    visibility: CalendarEventVisibility | None = None,
) -> CalendarEvent:
    """Factory helper to build :class:`CalendarEvent` instances."""

    return CalendarEvent(
        id=event_id or str(uuid.uuid4()),
        title=title,
        start_time=start_time,
        end_time=end_time,
        description=description,
        is_all_day=is_all_day,
        location=location,
        status=status,
        rrule=rrule,
        visibility=visibility,
    )
