"""
Universal Memory Engine (UME) core package.
"""
from .event import Event, EventType, parse_event, EventError
from .graph import MockGraph
from .graph_adapter import IGraphAdapter
from .rbac_adapter import RoleBasedGraphAdapter, AccessDeniedError
from .processing import apply_event_to_graph, ProcessingError
from .snapshot import snapshot_graph_to_file, load_graph_from_file, SnapshotError

__all__ = [
    "Event", "EventType", "parse_event", "EventError",
    "MockGraph",
    "IGraphAdapter",
    "RoleBasedGraphAdapter",
    "AccessDeniedError",
    "apply_event_to_graph", "ProcessingError",
    "snapshot_graph_to_file",
    "load_graph_from_file",
    "SnapshotError"
]
