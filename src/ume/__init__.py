"""Universal Memory Engine (UME) core package."""

# ruff: noqa: E402

import importlib  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402
import types  # noqa: E402
from types import SimpleNamespace

def _make_stub(name: str) -> types.ModuleType:
    stub = types.ModuleType(name)
    return stub

os.environ.setdefault("UME_AUDIT_SIGNING_KEY", "stub")
try:  # Expose config for tests as early as possible
    config = importlib.import_module(".config", __name__)
    Settings = config.Settings
    setattr(sys.modules[__name__], "config", config)
except Exception:  # pragma: no cover - allow import without environment setup
    stub = _make_stub("ume.config")
    sys.modules["ume.config"] = stub
    stub.settings = SimpleNamespace(  # type: ignore[attr-defined]
        UME_DB_PATH="ume_graph.db",
        UME_SNAPSHOT_PATH="ume_snapshot.json",
        UME_AUDIT_LOG_PATH="/tmp/audit.log",
        UME_AUDIT_SIGNING_KEY="stub",
        UME_CONSENT_LEDGER_PATH="consent_ledger.db",
        UME_AGENT_ID="SYSTEM",
        UME_EMBED_MODEL="all-MiniLM-L6-v2",
        UME_CLI_DB="ume_graph.db",
        UME_ROLE=None,
        UME_API_ROLE=None,
        UME_RATE_LIMIT_REDIS=None,
        UME_LOG_LEVEL="INFO",
        UME_LOG_JSON=False,
        UME_GRAPH_RETENTION_DAYS=30,
        UME_RELIABILITY_THRESHOLD=0.5,
        WATCH_PATHS=["."],
        DAG_RESOURCES={"cpu": 1, "io": 1},
        UME_VECTOR_DIM=0,
        UME_VECTOR_INDEX="vectors.faiss",
        UME_VECTOR_USE_GPU=False,
        UME_VECTOR_GPU_MEM_MB=256,
        UME_VECTOR_MAX_AGE_DAYS=90,
        NEO4J_URI="bolt://localhost:7687",
        NEO4J_USER="neo4j",
        NEO4J_PASSWORD="password",  # pragma: allowlist secret
        KAFKA_BOOTSTRAP_SERVERS="localhost:9092",
        KAFKA_RAW_EVENTS_TOPIC="ume-raw-events",
        KAFKA_CLEAN_EVENTS_TOPIC="ume-clean-events",
        KAFKA_QUARANTINE_TOPIC="ume-quarantine-events",
        KAFKA_EDGE_TOPIC="ume_edges",
        KAFKA_NODE_TOPIC="ume_nodes",
        KAFKA_GROUP_ID="ume_client_group",
        KAFKA_PRIVACY_AGENT_GROUP_ID="ume-privacy-agent-group",
        KAFKA_PRODUCER_BATCH_SIZE=10,
        UME_OAUTH_USERNAME="ume",
        UME_OAUTH_PASSWORD="password",  # pragma: allowlist secret
        UME_OAUTH_ROLE="AnalyticsAgent",
        UME_OAUTH_TTL=3600,
        UME_API_TOKEN=None,
        OPA_URL=None,
        OPA_TOKEN=None,
        UME_OTLP_ENDPOINT=None,
        LLM_FERRY_API_URL="https://example.com/api",
        LLM_FERRY_API_KEY="",
        TWITTER_BEARER_TOKEN=None,
        ANGEL_BRIDGE_LOOKBACK_HOURS=24,
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
    "config",
    "vector_store",
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

    # Submodules
    "audit",
    "config",
    "persistent_graph",
    "plugins",
    "grpc_service",
    "vector_store",
    "api",

]

# Lazily import selected submodules on first access to avoid import-time side
# effects when environment variables are not yet configured.
_KNOWN_SUBMODULES = {
    "audit",
    "config",
    "persistent_graph",
    "plugins",
    "grpc_service",
    "vector_store",
    "api",
}

def __getattr__(name: str) -> object:  # pragma: no cover - thin wrapper
    if name in _KNOWN_SUBMODULES:
        from importlib import import_module

        module = import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(name)
