"""Universal Memory Engine (UME) public package surface."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from .bootstrap.config import load_config
from .deprecations import warn_deprecated
from .event import Event, EventError, EventType, parse_event
from .graph_adapter import IGraphAdapter

# Load only configuration by default. Optional runtimes are initialized via
# ``ume.bootstrap.runtime.bootstrap_runtime`` in application entry points.
config, Settings = load_config(__name__)

__all__ = [
    "Event",
    "EventError",
    "EventType",
    "IGraphAdapter",
    "Settings",
    "config",
    "parse_event",
]

_RUNTIME_EXPORTS = {
    "Neo4jGraph",
    "VectorBackend",
    "VectorStore",
    "VectorStoreListener",
    "create_default_store",
    "FaissBackend",
    "ChromaBackend",
    "generate_embedding",
    "OntologyListener",
    "configure_ontology_graph",
}

_COMPAT_EXPORTS: dict[str, tuple[str, str]] = {
    "MockGraph": ("ume.graph", "MockGraph"),
    "PersistentGraph": ("ume.persistent_graph", "PersistentGraph"),
    "PostgresGraph": ("ume.postgres_graph", "PostgresGraph"),
    "RedisGraphAdapter": ("ume.redis_graph_adapter", "RedisGraphAdapter"),
    "ArangoGraph": ("ume.arango_graph", "ArangoGraph"),
    "enable_periodic_snapshot": ("ume.auto_snapshot", "enable_periodic_snapshot"),
    "disable_periodic_snapshot": ("ume.auto_snapshot", "disable_periodic_snapshot"),
    "enable_snapshot_autosave_and_restore": (
        "ume.auto_snapshot",
        "enable_snapshot_autosave_and_restore",
    ),
    "start_retention_scheduler": ("ume.retention", "start_retention_scheduler"),
    "stop_retention_scheduler": ("ume.retention", "stop_retention_scheduler"),
    "start_ledger_compaction_scheduler": (
        "ume.retention",
        "start_ledger_compaction_scheduler",
    ),
    "stop_ledger_compaction_scheduler": (
        "ume.retention",
        "stop_ledger_compaction_scheduler",
    ),
    "start_memory_aging_scheduler": (
        "ume.memory_aging",
        "start_memory_aging_scheduler",
    ),
    "stop_memory_aging_scheduler": ("ume.memory_aging", "stop_memory_aging_scheduler"),
    "start_vector_age_scheduler": ("ume.memory_aging", "start_vector_age_scheduler"),
    "stop_vector_age_scheduler": ("ume.memory_aging", "stop_vector_age_scheduler"),
    "RoleBasedGraphAdapter": ("ume.rbac_adapter", "RoleBasedGraphAdapter"),
    "AccessDeniedError": ("ume.rbac_adapter", "AccessDeniedError"),
    "PermissionsGraphAdapter": ("ume.permissions_adapter", "PermissionsGraphAdapter"),
    "PolicyViolationError": ("ume.plugins.alignment", "PolicyViolationError"),
    "apply_event_to_graph": ("ume.processing", "apply_event_to_graph"),
    "ProcessingError": ("ume.processing", "ProcessingError"),
    "log_audit_entry": ("ume.audit", "log_audit_entry"),
    "get_audit_entries": ("ume.audit", "get_audit_entries"),
    "snapshot_graph_to_file": ("ume.snapshot", "snapshot_graph_to_file"),
    "load_graph_from_file": ("ume.snapshot", "load_graph_from_file"),
    "load_graph_into_existing": ("ume.snapshot", "load_graph_into_existing"),
    "SnapshotError": ("ume.snapshot", "SnapshotError"),
    "validate_event_dict": ("ume.schema_utils", "validate_event_dict"),
    "GraphSchema": ("ume.graph_schema", "GraphSchema"),
    "load_default_schema": ("ume.graph_schema", "load_default_schema"),
    "GraphSchemaManager": ("ume.schema_manager", "GraphSchemaManager"),
    "DEFAULT_SCHEMA_MANAGER": ("ume.schema_manager", "DEFAULT_SCHEMA_MANAGER"),
    "ssl_config": ("ume.utils", "ssl_config"),
    "EpisodicMemory": ("ume.memory", "EpisodicMemory"),
    "SemanticMemory": ("ume.memory", "SemanticMemory"),
    "ColdMemory": ("ume.memory", "ColdMemory"),
    "LLMFerry": ("ume.llm_ferry", "LLMFerry"),
    "score_text": ("ume.reliability", "score_text"),
    "filter_low_confidence": ("ume.reliability", "filter_low_confidence"),
    "AgentTask": ("ume.agent_orchestrator", "AgentTask"),
    "AgentOrchestrator": ("ume.agent_orchestrator", "AgentOrchestrator"),
    "Supervisor": ("ume.agent_orchestrator", "Supervisor"),
    "Critic": ("ume.agent_orchestrator", "Critic"),
    "MessageEnvelope": ("ume.message_bus", "MessageEnvelope"),
    "ReflectionAgent": ("ume.agent_orchestrator", "ReflectionAgent"),
    "Task": ("ume.dag_executor", "Task"),
    "DAGExecutor": ("ume.dag_executor", "DAGExecutor"),
    "DAGService": ("ume.dag_service", "DAGService"),
    "ResourceScheduler": ("ume.resource_scheduler", "ResourceScheduler"),
    "ScheduledTask": ("ume.resource_scheduler", "ScheduledTask"),
    "Dossier": ("ume.dossier", "Dossier"),
    "tokenize": ("ume.tokenization", "tokenize"),
    "create_graph_adapter": ("ume.factories", "create_graph_adapter"),
    "create_vector_store": ("ume.factories", "create_vector_store"),
    "create_graph": ("ume.resources", "create_graph"),
    "graph_factory": ("ume.resources", "graph_factory"),
    "vector_store_factory": ("ume.resources", "vector_store_factory"),
    "get_capability_manifest": ("ume.factories", "get_capability_manifest"),
    "start_dossier_snapshot_scheduler": (
        "ume.dossier.scheduler",
        "start_dossier_snapshot_scheduler",
    ),
    "stop_dossier_snapshot_scheduler": (
        "ume.dossier.scheduler",
        "stop_dossier_snapshot_scheduler",
    ),
}

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
    "snapshot_routes",
    "dossier",
}


def __getattr__(name: str) -> object:
    if name in _KNOWN_SUBMODULES:
        module = import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module

    if name in _RUNTIME_EXPORTS:
        from .bootstrap.runtime import bootstrap_runtime

        warn_deprecated(
            "ume.__getattr__.runtime_export_fallback",
            detail=(
                f"Requested symbol ume.{name}. Falling back to compatibility shim. "
                "Call ume.bootstrap.runtime.bootstrap_runtime() from service entry points."
            ),
            stacklevel=2,
        )
        runtime_exports = bootstrap_runtime(__name__)
        return runtime_exports[name]

    if name in _COMPAT_EXPORTS:
        mod_name, attr = _COMPAT_EXPORTS[name]
        warn_deprecated(
            "ume.__getattr__.compat_exports",
            detail=f"Requested symbol ume.{name} currently resolves to {mod_name}.{attr}.",
            stacklevel=2,
        )
        value: Any = getattr(import_module(mod_name), attr)
        globals()[name] = value
        return value

    raise AttributeError(name)
