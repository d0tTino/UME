import pytest
from typing import cast

from typing import cast


from ume.neo4j_graph import Neo4jGraph
from neo4j import Driver


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
