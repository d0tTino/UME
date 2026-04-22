"""Factory helpers for graph and vector store initialization."""


from typing import Callable

from .kernel.graph_adapter import IGraphAdapter
from .factories import create_graph_adapter as _create_base_adapter
from .vector_store import VectorBackend, create_default_store


def create_graph_adapter(
    db_path: str | None = None,
    *,
    role: str | None = None,
) -> IGraphAdapter:
    """Instantiate the configured :class:`IGraphAdapter`."""

    return _create_base_adapter(db_path, role=role)


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
