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


import os

pytestmark = pytest.mark.skipif(
    not milvus_available() and not os.environ.get("UME_DOCKER_TESTS"),
    reason="Milvus server not available",
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


import os
import importlib.util
from pathlib import Path
import time

from ume.vector_backends import MilvusBackend as RealMilvusBackend


def _real_testcontainers_available() -> bool:
    spec = importlib.util.find_spec("testcontainers")
    if spec is None:
        return False
    return "src/testcontainers" not in str(Path(spec.origin).resolve())


def _pymilvus_available() -> bool:
    return importlib.util.find_spec("pymilvus") is not None


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("UME_DOCKER_TESTS"), reason="Docker tests disabled")
def test_milvus_backend_add_query_delete() -> None:
    if not _real_testcontainers_available() or not _pymilvus_available():
        pytest.skip("testcontainers or pymilvus not available")

    from testcontainers.core.container import DockerContainer

    image = "milvusdb/milvus:v2.4.0"
    container = DockerContainer(image).with_exposed_ports(19530)
    try:
        container.start()
    except Exception as exc:  # pragma: no cover - environment issues
        pytest.skip(f"Milvus container not available: {exc}")

    host = container.get_container_host_ip()
    port = container.get_exposed_port(19530)
    uri = f"{host}:{port}"

    from pymilvus import MilvusClient

    for _ in range(30):
        try:
            client = MilvusClient(uri=uri)
            client.list_collections()
            break
        except Exception:
            time.sleep(1)
    else:
        container.stop()
        pytest.skip("Milvus failed to start")

    backend = RealMilvusBackend(dim=2, uri=uri, collection="test_vectors")
    backend.add("a", [0.1, 0.2], persist=True)
    assert backend.query([0.1, 0.2], k=1) == ["a"]
    backend.delete("a")
    assert backend.query([0.1, 0.2], k=1) == []
    backend.close()
    container.stop()
