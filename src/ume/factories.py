from __future__ import annotations

from .config import settings
from .persistent_graph import PersistentGraph
from .rbac_adapter import RoleBasedGraphAdapter
from .vector_store import VectorStore, create_vector_store as _create_vector_store

from .graph_adapter import IGraphAdapter


def create_graph_adapter(
    db_path: str | None = None,
    *,
    role: str | None = None,
) -> IGraphAdapter:
    """Create the default :class:`IGraphAdapter` using configuration settings."""
    base = PersistentGraph(db_path or settings.UME_DB_PATH)
    role = role if role is not None else settings.UME_ROLE
    if role:
        return RoleBasedGraphAdapter(base, role=role)
    return base


# Re-export the vector store factory to keep the name consistent

def create_vector_store() -> VectorStore:
    """Create a :class:`VectorStore` configured from ``ume.config.settings``."""
    return _create_vector_store()
