from datetime import datetime
import uuid

from ume.models import (
    CalendarEvent,
    Decision,
    create_calendar_event,
    create_decision,
)



def test_create_calendar_event_defaults_and_schema_version() -> None:
    start = datetime.utcnow()
    event = create_calendar_event("Meeting", start)

    assert isinstance(event, CalendarEvent)
    uuid.UUID(event.id)
    assert event.end is None
    assert event.description is None
    assert event.is_all_day is False
    assert event.location is None
    assert event.status is None
    assert event.rrule is None
    assert event.visibility is None
    assert event.schema_version == "3.0"
    assert event.start == start


def test_create_decision_defaults_and_schema_version() -> None:
    decision = create_decision("Approve budget")

    assert isinstance(decision, Decision)
    uuid.UUID(decision.id)
    assert decision.made_by is None
    assert isinstance(decision.timestamp, datetime)
    assert decision.schema_version == "1.0"
