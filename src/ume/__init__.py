"""Universal Memory Engine (UME) core package."""

# ruff: noqa: E402

from .bootstrap import (
    load_config,
    load_neo4j,
    load_vector_modules,
    load_embedding,
)

# Expose config for tests as early as possible
config, Settings = load_config(__name__)


from .event import Event, EventType, parse_event, EventError
from .graph import MockGraph
from .persistent_graph import PersistentGraph
from .postgres_graph import PostgresGraph
from .redis_graph_adapter import RedisGraphAdapter
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - used for type hints only
    from .neo4j_graph import Neo4jGraph
else:  # pragma: no cover - optional dependency
    Neo4jGraph = load_neo4j(__name__)
from .auto_snapshot import (
    enable_periodic_snapshot,
    disable_periodic_snapshot,
    enable_snapshot_autosave_and_restore,
)
from .retention import start_retention_scheduler, stop_retention_scheduler
from .memory_aging import (
    start_memory_aging_scheduler,
    stop_memory_aging_scheduler,
    start_vector_age_scheduler,
    stop_vector_age_scheduler,
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
from .utils import ssl_config
from .memory import EpisodicMemory, SemanticMemory, ColdMemory
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - used for type hints only
    from .vector_store import (
        VectorBackend,
        VectorStore,
        VectorStoreListener,
        create_default_store,
    )
    from .vector_backends import FaissBackend, ChromaBackend
else:  # pragma: no cover - optional dependency
    (
        VectorBackend,
        VectorStore,
        VectorStoreListener,
        create_default_store,
        FaissBackend,
        ChromaBackend,
    ) = load_vector_modules(__name__)


from .llm_ferry import LLMFerry
from .dag_executor import DAGExecutor, Task
from .agent_orchestrator import (
    AgentOrchestrator,
    Supervisor,
    Critic,
    AgentTask,
    ReflectionAgent,
)
from .message_bus import MessageEnvelope
from .resources import (
    create_graph_adapter,
    create_graph,
    create_vector_store,
    graph_factory,
    vector_store_factory,
)

from .dag_service import DAGService
from .resource_scheduler import ResourceScheduler, ScheduledTask

# Import the API lazily via __getattr__ to avoid circular imports during
# initialization. The ``api`` module will be loaded on first attribute access.
from .reliability import score_text, filter_low_confidence  # noqa: E402
from ._internal.listeners import register_listener  # noqa: E402

generate_embedding, OntologyListener, configure_ontology_graph = load_embedding(
    __name__, register_listener
)


__all__ = [
    "Event",
    "EventType",
    "parse_event",
    "EventError",
    "MockGraph",
    "PersistentGraph",
    "PostgresGraph",
    "RedisGraphAdapter",
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
    "start_vector_age_scheduler",
    "stop_vector_age_scheduler",
    "validate_event_dict",
    "GraphSchema",
    "load_default_schema",
    "GraphSchemaManager",
    "DEFAULT_SCHEMA_MANAGER",
    "PolicyViolationError",
    "Settings",
    "config",
    "log_audit_entry",
    "get_audit_entries",
    "ssl_config",
    "create_graph_adapter",
    "create_graph",
    "create_vector_store",
    "graph_factory",
    "vector_store_factory",

    "EpisodicMemory",
    "SemanticMemory",
    "ColdMemory",

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


]

# Lazily import selected submodules on first access to avoid import-time side
# effects when environment variables are not yet configured.
_KNOWN_SUBMODULES = {
    "audit",
    "config",
    "persistent_graph",
    "plugins",
    "grpc_server",
    "vector_store",
    "recommendation_feedback",
    "embedding",
    "resources",
    "api",
    "policy",
}

def __getattr__(name: str) -> object:  # pragma: no cover - thin wrapper
    if name in _KNOWN_SUBMODULES:
        from importlib import import_module

        module = import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(name)
