# src/ume/__init__.py
"""
Universal Memory Engine (UME) core package.
"""
from .event import Event, parse_event, EventError
from .graph import MockGraph
from .processing import apply_event_to_graph, ProcessingError # Add this

__all__ = [
    "Event", "parse_event", "EventError",
    "MockGraph",
    "apply_event_to_graph", "ProcessingError" # Add these
]
