# src/ume/__init__.py
"""
Universal Memory Engine (UME) core package.
"""
from .event import Event, parse_event, EventError
from .graph import MockGraph
from .graph_adapter import IGraphAdapter  # Add this import
from .processing import apply_event_to_graph, ProcessingError
from .snapshot import snapshot_graph_to_file

__all__ = [
    "Event", "parse_event", "EventError",
    "MockGraph",
    "IGraphAdapter",  # Add this string
    "apply_event_to_graph", "ProcessingError",
    "snapshot_graph_to_file"
]
