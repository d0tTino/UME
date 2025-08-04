from datetime import datetime
from ume.models.calendar import create_calendar_event

def test_create_event_fields():
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 2)
    event = create_calendar_event(
        "title",
        start,
        end,
        description="desc",
        is_all_day=True,
        location="room",
        status="confirmed",
        rrule="FREQ=DAILY",
        visibility="public",
        event_id="abc",
    )
    assert event.id == "abc"
    assert event.title == "title"
    assert event.start_time == start
    assert event.end_time == end
    assert event.description == "desc"
    assert event.is_all_day is True
    assert event.location == "room"
    assert event.status == "confirmed"
    assert event.rrule == "FREQ=DAILY"
    assert event.visibility == "public"
