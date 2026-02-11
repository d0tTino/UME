import time

import pytest

from ume.event import Event, EventType
from ume.events.handlers import EVENT_HANDLER_REGISTRY
from ume.events.handlers.base import EventHandler
from ume.graph import MockGraph
from ume.processing import ProcessingError, apply_event_to_graph


def test_event_handler_registry_covers_all_event_types() -> None:
    assert set(EVENT_HANDLER_REGISTRY.keys()) == set(EventType)


def test_event_handler_registry_implements_interface() -> None:
    for event_type, handler in EVENT_HANDLER_REGISTRY.items():
        assert isinstance(event_type, EventType)
        assert isinstance(handler, EventHandler)


def test_unknown_event_type_raises_processing_error() -> None:
    event = Event(
        event_type="NOT_A_REAL_EVENT",
        timestamp=int(time.time()),
        payload={},
    )
    with pytest.raises(ProcessingError, match="Unknown event_type 'NOT_A_REAL_EVENT'"):
        apply_event_to_graph(event, MockGraph())
