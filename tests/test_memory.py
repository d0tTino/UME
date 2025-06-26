import time
from ume import Event, MemoryManager


def make_event(idx: int) -> Event:
    return Event(event_type="test", timestamp=int(time.time()), payload={}, event_id=str(idx))


def test_memory_across_tiers():
    manager = MemoryManager(short_term_limit=3, long_term_limit=5)
    for i in range(1, 11):
        manager.insert_event(make_event(i))

    # Verify distribution
    assert [e.event_id for e in manager.short_term] == ["8", "9", "10"]
    assert [e.event_id for e in manager.long_term] == ["3", "4", "5", "6", "7"]
    assert [e.event_id for e in manager.archive] == ["1", "2"]

    # Verify recall across tiers
    assert manager.get_event("9").event_id == "9"
    assert manager.get_event("5").event_id == "5"
    assert manager.get_event("1").event_id == "1"
    assert manager.get_event("missing") is None
