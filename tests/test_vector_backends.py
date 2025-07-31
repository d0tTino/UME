# ruff: noqa: E402
import pytest
from unittest.mock import MagicMock

try:
    from pymilvus import connections
except Exception:  # pragma: no cover - optional dependency
    connections = None


def milvus_available() -> bool:
    if connections is None:
        return False
    try:
        connections.connect(host="localhost", port="19530", timeout=1)
        connections.disconnect("default")
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not milvus_available(), reason="Milvus server not available"
)

from ume.vector_store import VectorBackend


class MilvusBackend(VectorBackend):
    """Simple backend using a Milvus-like client."""

    def __init__(self, client: object) -> None:
        self.client = client

    def add(self, item_id: str, vector: list[float], *, persist: bool = False) -> None:
        self.client.insert(vectors=[vector], ids=[item_id])

    def add_many(self, vectors: dict[str, list[float]], *, persist: bool = False) -> None:
        self.client.insert(vectors=list(vectors.values()), ids=list(vectors.keys()))

    def delete(self, item_id: str) -> None:
        self.client.delete(ids=[item_id])

    def query(self, vector: list[float], k: int = 5) -> list[str]:
        return self.client.search(vector=vector, limit=k)

    def save(self, path: str | None = None) -> None:
        pass

    def load(self, path: str | None = None) -> None:
        pass

    def close(self) -> None:
        self.client.close()

    def get_vector_timestamps(self) -> dict[str, int]:
        return {}


def test_add_calls_insert() -> None:
    client = MagicMock()
    backend = MilvusBackend(client)
    backend.add("a", [0.1, 0.2])
    client.insert.assert_called_once_with(vectors=[[0.1, 0.2]], ids=["a"])


def test_add_many_inserts_multiple_vectors() -> None:
    client = MagicMock()
    backend = MilvusBackend(client)
    backend.add_many({"a": [0.1, 0.2], "b": [0.3, 0.4]})
    client.insert.assert_called_once_with(
        vectors=[[0.1, 0.2], [0.3, 0.4]],
        ids=["a", "b"],
    )


def test_query_calls_search_and_returns_results() -> None:
    client = MagicMock()
    client.search.return_value = ["a"]
    backend = MilvusBackend(client)
    result = backend.query([0.1, 0.2], k=1)
    client.search.assert_called_once_with(vector=[0.1, 0.2], limit=1)
    assert result == ["a"]


def test_delete_calls_client() -> None:
    client = MagicMock()
    backend = MilvusBackend(client)
    backend.delete("a")
    client.delete.assert_called_once_with(ids=["a"])


def test_close_calls_client_close() -> None:
    client = MagicMock()
    backend = MilvusBackend(client)
    backend.close()
    client.close.assert_called_once_with()
