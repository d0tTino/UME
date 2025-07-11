"""Factory helpers for graph and vector store initialization."""


from typing import Callable

from .config import settings
from .graph_adapter import IGraphAdapter
from .persistent_graph import PersistentGraph
from .postgres_graph import PostgresGraph
from .redis_graph_adapter import RedisGraphAdapter
from .rbac_adapter import RoleBasedGraphAdapter
from .tracing import TracingGraphAdapter, is_tracing_enabled
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - for type hints only
    from .neo4j_graph import Neo4jGraph
else:  # pragma: no cover - optional dependency
    try:
        from .neo4j_graph import Neo4jGraph
    except Exception:
        class Neo4jGraph:
            def __init__(self, *_: object, **__: object) -> None:
                raise ImportError("neo4j is required for Neo4jGraph")
from .vector_store import VectorBackend, create_default_store


def create_graph_adapter(
    db_path: str | None = None,
    *,
    role: str | None = None,
) -> IGraphAdapter:
    """Instantiate the configured :class:`IGraphAdapter`."""

    backend = settings.UME_GRAPH_BACKEND.lower()
    if backend == "postgres":
        base: IGraphAdapter = PostgresGraph(db_path or settings.UME_DB_PATH)
    elif backend == "redis":
        base = RedisGraphAdapter(db_path or settings.UME_DB_PATH)
    elif backend == "neo4j":
        base = Neo4jGraph(
            settings.NEO4J_URI,
            settings.NEO4J_USER,
            settings.NEO4J_PASSWORD,
        )
    else:
        base = PersistentGraph(db_path or settings.UME_DB_PATH)

    if is_tracing_enabled():
        base = TracingGraphAdapter(base)

    role = role if role is not None else settings.UME_ROLE
    if role:
        base = RoleBasedGraphAdapter(base, role=role)

    return base


def _default_graph_factory() -> IGraphAdapter:
    """Return a graph adapter configured from :class:`~ume.config.Settings`."""
    return create_graph_adapter()


def _default_vector_store_factory() -> VectorBackend:
    """Return a vector store configured from :class:`~ume.config.Settings`."""
    return create_default_store()


#: Callable used to create the active graph adapter. Tests may override this.
graph_factory: Callable[[], IGraphAdapter] = _default_graph_factory

#: Callable used to create the active vector store. Tests may override this.
vector_store_factory: Callable[[], VectorBackend] = _default_vector_store_factory


def create_graph() -> IGraphAdapter:
    """Instantiate the configured graph adapter."""
    return graph_factory()


def create_vector_store() -> VectorBackend:
    """Instantiate the configured vector store."""
    return vector_store_factory()

__all__ = [
    "create_graph_adapter",
    "create_graph",
    "create_vector_store",
    "graph_factory",
    "vector_store_factory",
]
