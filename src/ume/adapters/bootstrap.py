from __future__ import annotations

from .registry import register_graph_backend, register_lazy_graph_backend


_BUILTINS_REGISTERED = False


def register_builtin_graph_backends() -> None:
    """Register built-in graph backend constructors."""
    global _BUILTINS_REGISTERED
    if _BUILTINS_REGISTERED:
        return

    register_graph_backend("sqlite", _create_persistent_graph)
    register_graph_backend("persistent", _create_persistent_graph)
    register_graph_backend("postgres", _create_postgres_graph)
    register_graph_backend("redis", _create_redis_graph)
    register_graph_backend("arango", _create_arango_graph)
    register_lazy_graph_backend("neo4j", _load_neo4j_constructor)

    _BUILTINS_REGISTERED = True


def _create_persistent_graph(db_path: str | None):
    from ume.config import settings
    from ume.persistent_graph import PersistentGraph

    return PersistentGraph(db_path or settings.UME_DB_PATH)


def _create_postgres_graph(db_path: str | None):
    from ume.config import settings
    from ume.postgres_graph import PostgresGraph

    return PostgresGraph(db_path or settings.UME_DB_PATH)


def _create_redis_graph(db_path: str | None):
    from ume.config import settings
    from ume.redis_graph_adapter import RedisGraphAdapter

    return RedisGraphAdapter(db_path or settings.UME_DB_PATH)


def _create_arango_graph(_: str | None):
    from ume.config import settings
    from ume.arango_graph import ArangoGraph

    return ArangoGraph(
        settings.ARANGO_URL,
        settings.ARANGO_USER,
        settings.ARANGO_PASSWORD,
        db_name=settings.ARANGO_DB_NAME,
    )


def _load_neo4j_constructor():
    def _create_neo4j_graph(_: str | None):
        from ume.config import settings

        try:
            from ume.neo4j_graph import Neo4jGraph
        except Exception as exc:
            raise ImportError("neo4j is required for Neo4jGraph") from exc

        return Neo4jGraph(
            settings.NEO4J_URI,
            settings.NEO4J_USER,
            settings.NEO4J_PASSWORD,
        )

    return _create_neo4j_graph
