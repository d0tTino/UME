"""
Universal Memory Engine (UME) core package.
"""
from .event import Event, EventType, parse_event, EventError
from .graph import MockGraph
from .graph_adapter import IGraphAdapter
from .query import Neo4jQueryEngine
from .analytics import shortest_path, find_communities, temporal_node_counts
from .api import app as api_app
from .processing import apply_event_to_graph, ProcessingError
from .snapshot import snapshot_graph_to_file, load_graph_from_file, SnapshotError

__all__ = [
    "Event", "EventType", "parse_event", "EventError",
    "MockGraph",
    "IGraphAdapter",
    "Neo4jQueryEngine",
    "shortest_path",
    "find_communities",
    "temporal_node_counts",
    "api_app",
    "apply_event_to_graph", "ProcessingError",
    "snapshot_graph_to_file",
    "load_graph_from_file",
    "SnapshotError"
]
