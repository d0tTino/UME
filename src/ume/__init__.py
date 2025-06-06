"""Universal Memory Engine (UME) core package."""

from .event import Event, EventType, parse_event, EventError
from .graph import MockGraph
from .persistent_graph import PersistentGraph
from .auto_snapshot import (
    enable_periodic_snapshot,
    enable_snapshot_autosave_and_restore,
)
from .graph_adapter import IGraphAdapter
from .rbac_adapter import RoleBasedGraphAdapter, AccessDeniedError
from .query import Neo4jQueryEngine
from .analytics import shortest_path, find_communities, temporal_node_counts
from .api import app as api_app
from .processing import apply_event_to_graph, ProcessingError
from .listeners import (
    GraphListener,
    register_listener,
    unregister_listener,
)
from .audit import log_audit_entry, get_audit_entries
from .plugins.alignment import PolicyViolationError

from .snapshot import (
    snapshot_graph_to_file,
    load_graph_from_file,
    load_graph_into_existing,
    SnapshotError,
)
from .schema_utils import validate_event_dict
from .stream_processor import app as stream_app

__all__ = [
    "Event",
    "EventType",
    "parse_event",
    "EventError",
    "MockGraph",
    "PersistentGraph",
    "IGraphAdapter",
    "RoleBasedGraphAdapter",
    "AccessDeniedError",
    "apply_event_to_graph",
    "ProcessingError",
    "snapshot_graph_to_file",
    "load_graph_from_file",
    "load_graph_into_existing",
    "SnapshotError",
    "enable_snapshot_autosave_and_restore",
    "enable_periodic_snapshot",
    "Neo4jQueryEngine",
    "shortest_path",
    "find_communities",
    "temporal_node_counts",
    "api_app",
    "validate_event_dict",
    "GraphListener",
    "register_listener",
    "unregister_listener",
    "log_audit_entry",
    "get_audit_entries",
    "PolicyViolationError",
]
