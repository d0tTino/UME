# src/ume/__init__.py
"""
Universal Memory Engine (UME) core package.
"""

from .event import Event, parse_event, EventError
from .graph import MockGraph
from .graph_adapter import IGraphAdapter
from .processing import apply_event_to_graph, ProcessingError
from .snapshot import (
    snapshot_graph_to_file,
    load_graph_from_file,
    SnapshotError,
)
from .memory import MemoryManager

__all__ = [
    "Event",
    "parse_event",
    "EventError",
    "MockGraph",
    "IGraphAdapter",
    "apply_event_to_graph",
    "ProcessingError",
    "snapshot_graph_to_file",
    "load_graph_from_file",  # Add this
    "SnapshotError",  # Add this
    "MemoryManager",
]
