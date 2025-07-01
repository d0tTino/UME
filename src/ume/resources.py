"""Factory helpers for graph and vector store initialization."""


from typing import Callable

from .graph_adapter import IGraphAdapter
from .vector_store import VectorStore, create_default_store
from .factories import create_graph_adapter


def _default_graph_factory() -> IGraphAdapter:
    """Return a graph adapter configured from :class:`~ume.config.Settings`."""
    return create_graph_adapter()


def _default_vector_store_factory() -> VectorStore:
    """Return a vector store configured from :class:`~ume.config.Settings`."""
    return create_default_store()


#: Callable used to create the active graph adapter. Tests may override this.
graph_factory: Callable[[], IGraphAdapter] = _default_graph_factory

#: Callable used to create the active vector store. Tests may override this.
vector_store_factory: Callable[[], VectorStore] = _default_vector_store_factory


def create_graph() -> IGraphAdapter:
    """Instantiate the configured graph adapter."""
    return graph_factory()


def create_vector_store() -> VectorStore:
    """Instantiate the configured vector store."""
    return vector_store_factory()

__all__ = [
    "create_graph",
    "create_vector_store",
    "graph_factory",
    "vector_store_factory",
]
