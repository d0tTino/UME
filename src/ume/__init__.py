"""Universal Memory Engine (UME) core package."""

# ruff: noqa: E402

import importlib  # noqa: E402
import sys  # noqa: E402
import types  # noqa: E402
from types import SimpleNamespace

def _make_stub(name: str) -> types.ModuleType:
    stub = types.ModuleType(name)
    return stub

try:  # Expose config for tests as early as possible
    config = importlib.import_module(".config", __name__)
    Settings = config.Settings
    setattr(sys.modules[__name__], "config", config)
except Exception:  # pragma: no cover - allow import without environment setup
    stub = _make_stub("ume.config")
    sys.modules["ume.config"] = stub
    stub.settings = SimpleNamespace(  # type: ignore[attr-defined]
        UME_AUDIT_LOG_PATH="/tmp/audit.log",
        UME_AUDIT_SIGNING_KEY="stub",
        NEO4J_URI="",
        NEO4J_USER="",
        NEO4J_PASSWORD="",
        UME_VECTOR_DIM=0,
        UME_VECTOR_USE_GPU=False,
    )
    class _StubSettings:
        pass
    Settings = _StubSettings
    stub.Settings = _StubSettings  # type: ignore[attr-defined]
    config = stub
    setattr(sys.modules[__name__], "config", stub)


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
from .memory_aging import start_memory_aging_scheduler, stop_memory_aging_scheduler
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
from .utils import ssl_config
from .memory import EpisodicMemory, SemanticMemory
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - used for type hints only
    from .vector_store import VectorStore, VectorStoreListener, create_default_store
else:  # pragma: no cover - optional dependency
    try:
        from .vector_store import VectorStore, VectorStoreListener, create_default_store
    except Exception:
        vector_stub = types.ModuleType("ume.vector_store")

        class VectorStore:
            def __init__(self, *_: object, **__: object) -> None:
                raise ImportError("faiss is required for VectorStore")

        class VectorStoreListener:
            def __init__(self, *_: object, **__: object) -> None:
                raise ImportError("faiss is required for VectorStoreListener")

        def create_default_store(*_: object, **__: object) -> None:
            raise ImportError("faiss is required for create_default_store")

        vector_stub.VectorStore = VectorStore
        vector_stub.VectorStoreListener = VectorStoreListener
        vector_stub.create_default_store = create_default_store
        sys.modules[__name__ + ".vector_store"] = vector_stub
        setattr(sys.modules[__name__], "vector_store", vector_stub)


from .llm_ferry import LLMFerry
from .dag_executor import DAGExecutor, Task
from .agent_orchestrator import (
    AgentOrchestrator,
    Supervisor,
    Critic,
    AgentTask,
    MessageEnvelope,
    ReflectionAgent,
)
from .dag_service import DAGService
from .resource_scheduler import ResourceScheduler, ScheduledTask

try:
    api = importlib.import_module('.api', __name__)
except Exception:
    api = None  # type: ignore[assignment]
from .reliability import score_text, filter_low_confidence  # noqa: E402
from ._internal.listeners import register_listener  # noqa: E402

try:  # Optional dependency
    from .embedding import generate_embedding
    _EMBEDDINGS_AVAILABLE = True
except Exception:  # pragma: no cover - optional import
    _EMBEDDINGS_AVAILABLE = False

    def generate_embedding(text: str) -> list[float]:
        raise ImportError("sentence-transformers is required to generate embeddings")

if _EMBEDDINGS_AVAILABLE:
    from .ontology import OntologyListener, configure_ontology_graph
    _ONTOLOGY_LISTENER = OntologyListener()
    register_listener(_ONTOLOGY_LISTENER)


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
    "start_memory_aging_scheduler",
    "stop_memory_aging_scheduler",
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

    "EpisodicMemory",
    "SemanticMemory",

    "LLMFerry",

    "score_text",
    "filter_low_confidence",

    "generate_embedding",
    "configure_ontology_graph",
    "OntologyListener",
    "AgentTask",
    "AgentOrchestrator",
    "Supervisor",
    "Critic",
    "MessageEnvelope",
    "ReflectionAgent",
    "Task",
    "DAGExecutor",
    "DAGService",
    "ResourceScheduler",
    "ScheduledTask",
    "TweetBot",
    "ResourceScheduler",
    "ScheduledTask",

]
