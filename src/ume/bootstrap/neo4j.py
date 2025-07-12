from importlib import import_module
from typing import Any, cast

__all__ = ["load_neo4j"]

def load_neo4j(package: str) -> type[Any]:
    """Return the Neo4jGraph class, using a stub if dependency missing."""
    try:
        return cast(type[Any], import_module(f"{package}.neo4j_graph").Neo4jGraph)
    except Exception:
        class Neo4jGraph:
            def __init__(self, *_: object, **__: object) -> None:
                raise ImportError("neo4j is required for Neo4jGraph")
        return Neo4jGraph
