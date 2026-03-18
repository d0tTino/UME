"""Universal Memory Engine (UME) public package surface."""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class _ShimExport:
    module: str
    attr: str
    deprecation_key: str


_RUNTIME_EXPORTS: dict[str, _ShimExport] = {
    "Neo4jGraph": _ShimExport(
        module="ume.bootstrap.runtime",
        attr="bootstrap_runtime",
        deprecation_key="ume.__getattr__.runtime_export_fallback.Neo4jGraph",
    ),
    "VectorBackend": _ShimExport(
        module="ume.bootstrap.runtime",
        attr="bootstrap_runtime",
        deprecation_key="ume.__getattr__.runtime_export_fallback.VectorBackend",
    ),
    "VectorStore": _ShimExport(
        module="ume.bootstrap.runtime",
        attr="bootstrap_runtime",
        deprecation_key="ume.__getattr__.runtime_export_fallback.VectorStore",
    ),
    "VectorStoreListener": _ShimExport(
        module="ume.bootstrap.runtime",
        attr="bootstrap_runtime",
        deprecation_key="ume.__getattr__.runtime_export_fallback.VectorStoreListener",
    ),
    "create_default_store": _ShimExport(
        module="ume.bootstrap.runtime",
        attr="bootstrap_runtime",
        deprecation_key="ume.__getattr__.runtime_export_fallback.create_default_store",
    ),
    "FaissBackend": _ShimExport(
        module="ume.bootstrap.runtime",
        attr="bootstrap_runtime",
        deprecation_key="ume.__getattr__.runtime_export_fallback.FaissBackend",
    ),
    "ChromaBackend": _ShimExport(
        module="ume.bootstrap.runtime",
        attr="bootstrap_runtime",
        deprecation_key="ume.__getattr__.runtime_export_fallback.ChromaBackend",
    ),
    "generate_embedding": _ShimExport(
        module="ume.bootstrap.runtime",
        attr="bootstrap_runtime",
        deprecation_key="ume.__getattr__.runtime_export_fallback.generate_embedding",
    ),
    "OntologyListener": _ShimExport(
        module="ume.bootstrap.runtime",
        attr="bootstrap_runtime",
        deprecation_key="ume.__getattr__.runtime_export_fallback.OntologyListener",
    ),
    "configure_ontology_graph": _ShimExport(
        module="ume.bootstrap.runtime",
        attr="bootstrap_runtime",
        deprecation_key="ume.__getattr__.runtime_export_fallback.configure_ontology_graph",
    ),
}

_COMPAT_EXPORTS: dict[str, _ShimExport] = {
    "MockGraph": _ShimExport(
        module="ume.graph",
        attr="MockGraph",
        deprecation_key="ume.__getattr__.compat_exports.MockGraph",
    ),
    "PersistentGraph": _ShimExport(
        module="ume.persistent_graph",
        attr="PersistentGraph",
        deprecation_key="ume.__getattr__.compat_exports.PersistentGraph",
    ),
    "RoleBasedGraphAdapter": _ShimExport(
        module="ume.rbac_adapter",
        attr="RoleBasedGraphAdapter",
        deprecation_key="ume.__getattr__.compat_exports.RoleBasedGraphAdapter",
    ),
    "AccessDeniedError": _ShimExport(
        module="ume.rbac_adapter",
        attr="AccessDeniedError",
        deprecation_key="ume.__getattr__.compat_exports.AccessDeniedError",
    ),
    "PermissionsGraphAdapter": _ShimExport(
        module="ume.permissions_adapter",
        attr="PermissionsGraphAdapter",
        deprecation_key="ume.__getattr__.compat_exports.PermissionsGraphAdapter",
    ),
    "PolicyViolationError": _ShimExport(
        module="ume.plugins.alignment",
        attr="PolicyViolationError",
        deprecation_key="ume.__getattr__.compat_exports.PolicyViolationError",
    ),
    "apply_event_to_graph": _ShimExport(
        module="ume.processing",
        attr="apply_event_to_graph",
        deprecation_key="ume.__getattr__.compat_exports.apply_event_to_graph",
    ),
    "ProcessingError": _ShimExport(
        module="ume.processing",
        attr="ProcessingError",
        deprecation_key="ume.__getattr__.compat_exports.ProcessingError",
    ),
    "snapshot_graph_to_file": _ShimExport(
        module="ume.snapshot",
        attr="snapshot_graph_to_file",
        deprecation_key="ume.__getattr__.compat_exports.snapshot_graph_to_file",
    ),
    "load_graph_from_file": _ShimExport(
        module="ume.snapshot",
        attr="load_graph_from_file",
        deprecation_key="ume.__getattr__.compat_exports.load_graph_from_file",
    ),
    "SnapshotError": _ShimExport(
        module="ume.snapshot",
        attr="SnapshotError",
        deprecation_key="ume.__getattr__.compat_exports.SnapshotError",
    ),
    "DEFAULT_SCHEMA_MANAGER": _ShimExport(
        module="ume.schema_manager",
        attr="DEFAULT_SCHEMA_MANAGER",
        deprecation_key="ume.__getattr__.compat_exports.DEFAULT_SCHEMA_MANAGER",
    ),
    "get_audit_entries": _ShimExport(
        module="ume.audit",
        attr="get_audit_entries",
        deprecation_key="ume.__getattr__.compat_exports.get_audit_entries",
    ),
    "Task": _ShimExport(
        module="ume.dag_executor",
        attr="Task",
        deprecation_key="ume.__getattr__.compat_exports.Task",
    ),
    "DAGExecutor": _ShimExport(
        module="ume.dag_executor",
        attr="DAGExecutor",
        deprecation_key="ume.__getattr__.compat_exports.DAGExecutor",
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

        spec = _RUNTIME_EXPORTS[name]
        warn_deprecated(
            spec.deprecation_key,
            detail=(
                f"Requested symbol ume.{name}. Falling back to compatibility shim. "
                "Call ume.bootstrap.runtime.bootstrap_runtime() from service entry points."
            ),
            stacklevel=2,
        )
        runtime_exports = bootstrap_runtime(__name__)
        return runtime_exports[name]

    if name in _COMPAT_EXPORTS:
        spec = _COMPAT_EXPORTS[name]
        warn_deprecated(
            spec.deprecation_key,
            detail=f"Requested symbol ume.{name} currently resolves to {spec.module}.{spec.attr}.",
            stacklevel=2,
        )
        value: Any = getattr(import_module(spec.module), spec.attr)
        globals()[name] = value
        return value

    raise AttributeError(name)
