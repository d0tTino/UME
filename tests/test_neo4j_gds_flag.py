import pytest

try:  # pragma: no cover - optional dependency
    from neo4j import Driver
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    pytest.skip(
        "neo4j not installed; install with the 'neo4j' extra to run these tests",
        allow_module_level=True,
    )

from typing import cast
from ume.neo4j_graph import Neo4jGraph


class DummyDriver:
    def session(self):
        class DummySession:
            def run(self, *a, **k):
                return []

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                pass

        return DummySession()

    def close(self):
        pass


def test_gds_requires_flag():
    graph = Neo4jGraph("bolt://", "u", "p", driver=cast(Driver, DummyDriver()))
    with pytest.raises(NotImplementedError):
        graph.pagerank_centrality()
