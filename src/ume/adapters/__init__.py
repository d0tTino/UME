from typing import Dict, Type

from ..graph import MockGraph
from ..graph_adapter import IGraphAdapter

from .neo4j_adapter import Neo4jAdapter
from .lancedb_adapter import LanceDBAdapter

_ADAPTERS: Dict[str, Type[IGraphAdapter]] = {
    "mock": MockGraph,
    "neo4j": Neo4jAdapter,
    "lancedb": LanceDBAdapter,
}


def get_adapter(name: str) -> IGraphAdapter:
    """Return an adapter instance by name."""
    key = name.lower()
    if key not in _ADAPTERS:
        raise ValueError(f"Unknown adapter '{name}'")
    return _ADAPTERS[key]()

__all__ = ["Neo4jAdapter", "LanceDBAdapter", "get_adapter"]
