from __future__ import annotations

from .config import settings
from .persistent_graph import PersistentGraph
from .postgres_graph import PostgresGraph
from .redis_graph_adapter import RedisGraphAdapter
from .rbac_adapter import RoleBasedGraphAdapter
from .vector_store import VectorBackend, create_vector_store as _create_vector_store
from .memory import EpisodicMemory, SemanticMemory

from .graph_adapter import IGraphAdapter
from .tracing import TracingGraphAdapter, is_tracing_enabled


def create_graph_adapter(
    db_path: str | None = None,
    *,
    role: str | None = None,
) -> IGraphAdapter:
    """Create the default :class:`IGraphAdapter` using configuration settings."""
    backend = settings.UME_GRAPH_BACKEND.lower()
    base: IGraphAdapter
    if backend == "postgres":
        base = PostgresGraph(db_path or settings.UME_DB_PATH)
    elif backend == "redis":
        base = RedisGraphAdapter(db_path or settings.UME_DB_PATH)
    else:
        base = PersistentGraph(db_path or settings.UME_DB_PATH)
    if is_tracing_enabled():
        base = TracingGraphAdapter(base)
    role = role if role is not None else settings.UME_ROLE
    if role:
        return RoleBasedGraphAdapter(base, role=role)
    return base


# Re-export the vector store factory to keep the name consistent

def create_vector_store() -> VectorBackend:
    """Create a vector store configured from ``ume.config.settings``."""
    return _create_vector_store()


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
