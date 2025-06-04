"""
Universal Memory Engine (UME) core package.
"""
from .event import Event, EventType, parse_event, EventError
from .graph import MockGraph
from .graph_adapter import IGraphAdapter
from .processing import apply_event_to_graph, ProcessingError
from .snapshot import snapshot_graph_to_file, load_graph_from_file, SnapshotError
from .schema_utils import validate_event_dict

__all__ = [
    "Event", "EventType", "parse_event", "EventError",
    "MockGraph",
    "IGraphAdapter",
    "apply_event_to_graph", "ProcessingError",
    "snapshot_graph_to_file",
    "load_graph_from_file",
    "SnapshotError",
    "validate_event_dict",
]
