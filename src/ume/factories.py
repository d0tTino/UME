from __future__ import annotations

from .adapters.bootstrap import register_builtin_graph_backends
from .adapters.registry import (
    create_registered_graph_adapter,
    ensure_external_graph_backends_discovered,
    get_graph_backend_capabilities,
)
from .config import settings
from .rbac_adapter import RoleBasedGraphAdapter
from .vector_store import VectorBackend, create_vector_store as _create_vector_store
from .plugins.registry import get_plugin_metadata
from .vector_backends import VECTOR_BACKEND_CAPABILITY
from .integrations.registry import (
    available_adapters,
    get_adapter_capabilities,
    register_builtin_adapters,
)
from .capabilities import (
    CapabilityNegotiation,
    NATIVE_ACL_CAPABILITY,
    VECTOR_SIMILARITY_CAPABILITY,
)
from .capability_schema import build_capability_schema
from .memory import EpisodicMemory, SemanticMemory

from .graph_adapter import IGraphAdapter
from .tracing import TracingGraphAdapter, is_tracing_enabled


def _configured_adapter_modules() -> list[str]:
    raw = settings.UME_GRAPH_ADAPTER_MODULES
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]




def graph_capability_negotiation(backend: str | None = None) -> CapabilityNegotiation:
    """Return graph capability support and configured fallbacks."""
    backend_name = (backend or settings.UME_GRAPH_BACKEND).lower()
    try:
        supported = get_graph_backend_capabilities(backend_name)
    except ValueError:
        supported = frozenset()
    fallbacks: dict[str, str] = {}
    if NATIVE_ACL_CAPABILITY not in supported:
        fallbacks[NATIVE_ACL_CAPABILITY] = "application_side_acl_filtering"
    return CapabilityNegotiation(supported=supported, fallbacks=fallbacks)


def vector_capability_negotiation(backend: str | None = None) -> CapabilityNegotiation:
    """Return vector backend capability support metadata."""
    backend_name = (backend or settings.UME_VECTOR_BACKEND).lower()
    try:
        metadata = get_plugin_metadata(VECTOR_BACKEND_CAPABILITY, backend_name)
        supported = metadata.capabilities
    except ValueError:
        supported = frozenset()
    fallbacks: dict[str, str] = {}
    if VECTOR_SIMILARITY_CAPABILITY not in supported:
        fallbacks[VECTOR_SIMILARITY_CAPABILITY] = "semantic_search_disabled"
    return CapabilityNegotiation(supported=supported, fallbacks=fallbacks)




def integration_capability_negotiation(backend: str) -> CapabilityNegotiation:
    """Return integration adapter capability support metadata."""
    register_builtin_adapters()
    supported = get_adapter_capabilities(backend)
    return CapabilityNegotiation(supported=supported, fallbacks={})


def get_capability_manifest(
    *,
    graph_backend: str | None = None,
    vector_backend: str | None = None,
    integration_backends: list[str] | None = None,
) -> dict[str, object]:
    """Return canonical backend capability negotiation metadata."""
    graph_name = (graph_backend or settings.UME_GRAPH_BACKEND).lower()
    vector_name = (vector_backend or settings.UME_VECTOR_BACKEND).lower()

    graph_negotiation = graph_capability_negotiation(graph_name)
    vector_negotiation = vector_capability_negotiation(vector_name)

    register_builtin_adapters()
    adapter_names = integration_backends or sorted(available_adapters())
    integration_payload: dict[str, dict[str, object]] = {}
    for adapter_name in adapter_names:
        negotiation = integration_capability_negotiation(adapter_name)
        integration_payload[adapter_name] = build_capability_schema(
            domain="integration",
            backend=adapter_name,
            declared=negotiation.supported,
            supported=negotiation.supported,
            fallbacks=negotiation.fallbacks,
        ).as_dict()

    return {
        "graph_backend": graph_name,
        "vector_backend": vector_name,
        "graph": build_capability_schema(
            domain="graph",
            backend=graph_name,
            declared=graph_negotiation.supported,
            supported=graph_negotiation.supported,
            fallbacks=graph_negotiation.fallbacks,
        ).as_dict(),
        "vector": build_capability_schema(
            domain="vector",
            backend=vector_name,
            declared=vector_negotiation.supported,
            supported=vector_negotiation.supported,
            fallbacks=vector_negotiation.fallbacks,
        ).as_dict(),
        "integrations": integration_payload,
    }

def create_graph_adapter(
    db_path: str | None = None,
    *,
    role: str | None = None,
) -> IGraphAdapter:
    """Create the default :class:`IGraphAdapter` using configuration settings."""
    register_builtin_graph_backends()
    ensure_external_graph_backends_discovered(module_paths=_configured_adapter_modules())
    backend = settings.UME_GRAPH_BACKEND.lower()
    base = create_registered_graph_adapter(backend, db_path, default="persistent")
    setattr(base, "capability_negotiation", graph_capability_negotiation(backend))
    if is_tracing_enabled():
        base = TracingGraphAdapter(base)
    role = role if role is not None else settings.UME_ROLE
    if role:
        return RoleBasedGraphAdapter(base, role=role)
    return base


# Re-export the vector store factory to keep the name consistent

def create_vector_store() -> VectorBackend:
    """Create a vector store configured from ``ume.config.settings``."""
    store = _create_vector_store()
    setattr(store, "capability_negotiation", vector_capability_negotiation())
    return store


def create_episodic_memory(
    db_path: str | None = None, *, log_path: str | None = None
) -> EpisodicMemory:
    """Instantiate :class:`EpisodicMemory` using configuration defaults."""
    return EpisodicMemory(db_path or settings.UME_DB_PATH, log_path=log_path)


def create_semantic_memory(db_path: str | None = None) -> SemanticMemory:
    """Instantiate :class:`SemanticMemory` using configuration defaults."""
    return SemanticMemory(db_path or settings.UME_DB_PATH)


def create_tiered_memory(
    *,
    episodic_db: str | None = None,
    semantic_db: str | None = None,
    log_path: str | None = None,
) -> tuple[EpisodicMemory, SemanticMemory]:
    """Create paired episodic and semantic memory instances.

    The returned objects can be passed to
    :func:`ume.start_memory_aging_scheduler` to automatically migrate events
    from the episodic layer to long-term storage.
    """
    episodic = create_episodic_memory(episodic_db, log_path=log_path)
    semantic = create_semantic_memory(semantic_db)
    return episodic, semantic
