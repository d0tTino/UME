"""Calendar event node model and factory helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import uuid

SCHEMA_VERSION = "1.0"


@dataclass
class CalendarEvent:
    """Represents a calendar event in the graph."""

    id: str
    title: str
    start: datetime
    end: datetime | None = None
    description: str | None = None
    schema_version: str = SCHEMA_VERSION


def create_calendar_event(
    title: str,
    start: datetime,
    end: datetime | None = None,
    *,
    description: str | None = None,
    event_id: str | None = None,
) -> CalendarEvent:
    """Factory helper to build :class:`CalendarEvent` instances."""

    return CalendarEvent(
        id=event_id or str(uuid.uuid4()),
        title=title,
        start=start,
        end=end,
        description=description,
    )
