"""Universal Memory Engine (UME) core package."""

from .event import Event, EventType, parse_event, EventError
from .graph import MockGraph
from .persistent_graph import PersistentGraph
from .neo4j_graph import Neo4jGraph
from .auto_snapshot import (
    enable_periodic_snapshot,
    disable_periodic_snapshot,
    enable_snapshot_autosave_and_restore,
)
from .retention import start_retention_scheduler, stop_retention_scheduler
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
from .utils import ssl_config
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - used for type hints only
    from .vector_store import VectorStore, VectorStoreListener, create_default_store
else:  # pragma: no cover - optional dependency
    try:
        from .vector_store import VectorStore, VectorStoreListener, create_default_store
    except Exception:
        class VectorStore:
            def __init__(self, *_: Any, **__: Any) -> None:
                raise ImportError("faiss is required for VectorStore")

        class VectorStoreListener:
            def __init__(self, *_: Any, **__: Any) -> None:
                raise ImportError("faiss is required for VectorStoreListener")

        def create_default_store(*_: Any, **__: Any) -> None:
            raise ImportError("faiss is required for create_default_store")


from .llm_ferry import LLMFerry
from .dag_executor import DAGExecutor, Task
from .dag_service import DAGService
from .reliability import score_text, filter_low_confidence

try:  # Optional dependency
    from .embedding import generate_embedding
except Exception:  # pragma: no cover - optional import
    def generate_embedding(text: str) -> list[float]:
        raise ImportError("sentence-transformers is required to generate embeddings")


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
    "disable_periodic_snapshot",
    "start_retention_scheduler",
    "stop_retention_scheduler",
    "validate_event_dict",
    "GraphSchema",
    "load_default_schema",
    "GraphSchemaManager",
    "DEFAULT_SCHEMA_MANAGER",
    "PolicyViolationError",
    "Settings",
    "log_audit_entry",
    "get_audit_entries",
    "ssl_config",
    "VectorStore",
    "VectorStoreListener",
    "create_default_store",

    "LLMFerry",

    "score_text",
    "filter_low_confidence",

    "generate_embedding",
    "build_concept_graph",
    "update_concept_graph_for_node",
    "Task",
    "DAGExecutor",
    "DAGService",
]
