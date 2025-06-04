"""
Universal Memory Engine (UME) core package.
"""
from .event import Event, EventType, parse_event, EventError
from .graph import MockGraph
from .persistent_graph import PersistentGraph
from .auto_snapshot import enable_periodic_snapshot
from .graph_adapter import IGraphAdapter
from .processing import apply_event_to_graph, ProcessingError
from .snapshot import (
    snapshot_graph_to_file,
    load_graph_from_file,
    load_graph_into_existing,
    SnapshotError,
)

__all__ = [
    "Event", "EventType", "parse_event", "EventError",
    "MockGraph",
    "PersistentGraph",
    "enable_periodic_snapshot",
    "IGraphAdapter",
    "apply_event_to_graph", "ProcessingError",
    "snapshot_graph_to_file",
    "load_graph_from_file",
    "load_graph_into_existing",
    "SnapshotError"
]
