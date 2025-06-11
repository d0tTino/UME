"""Universal Memory Engine (UME) core package."""

from .event import Event, EventType, parse_event, EventError
from .graph import MockGraph
from .persistent_graph import PersistentGraph
from .neo4j_graph import Neo4jGraph
from .auto_snapshot import (
    enable_periodic_snapshot,
    enable_snapshot_autosave_and_restore,
)
from .graph_adapter import IGraphAdapter
from .rbac_adapter import RoleBasedGraphAdapter, AccessDeniedError
from .plugins.alignment import PolicyViolationError
from .processing import apply_event_to_graph, ProcessingError
from .audit import log_audit_entry, get_audit_entries
from .snapshot import (
    snapshot_graph_to_file,
    load_graph_from_file,
    load_graph_into_existing,
    SnapshotError,
)
from .schema_utils import validate_event_dict
from .graph_schema import GraphSchema, load_default_schema
from .schema_manager import GraphSchemaManager, DEFAULT_SCHEMA_MANAGER
from .config import Settings

__all__ = [
    "Event",
    "EventType",
    "parse_event",
    "EventError",
    "MockGraph",
    "PersistentGraph",
    "Neo4jGraph",
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
    "validate_event_dict",
    "GraphSchema",
    "load_default_schema",
    "GraphSchemaManager",
    "DEFAULT_SCHEMA_MANAGER",
    "PolicyViolationError",
    "log_audit_entry",
    "get_audit_entries",
    "Settings",
]
