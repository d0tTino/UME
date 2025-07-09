import pytest
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
import pytest

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ume.vector_backends import get_backend
from ume.api import app, configure_vector_store
from ume.config import settings

faiss = pytest.importorskip("faiss")
if not hasattr(faiss, "IndexFlatL2"):
    pytest.skip("faiss is missing required functionality", allow_module_level=True)


@pytest.fixture(params=["faiss", "chroma"])
def store_cls(request):
    return get_backend(request.param)


def test_add_vector_authorized(store_cls) -> None:
    configure_vector_store(store_cls(dim=2, use_gpu=False))
    client = TestClient(app)
    token = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    ).json()["access_token"]
    res = client.post(
        "/vectors",
        json={"id": "v1", "vector": [0.0, 1.0]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert app.state.vector_store.query([0.0, 1.0], k=1) == ["v1"]


def test_add_vector_invalid_dimension(store_cls) -> None:
    configure_vector_store(store_cls(dim=2, use_gpu=False))
    client = TestClient(app)
    token = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    ).json()["access_token"]
    res = client.post(
        "/vectors",
        json={"id": "v_bad", "vector": [0.0]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "Invalid vector dimension"


def test_add_vector_unauthorized(store_cls) -> None:
    configure_vector_store(store_cls(dim=2, use_gpu=False))
    client = TestClient(app)
    res = client.post("/vectors", json={"id": "v2", "vector": [1.0]})
    assert res.status_code == 401


def test_search_vectors(store_cls) -> None:
    configure_vector_store(store_cls(dim=2, use_gpu=False))
    client = TestClient(app)
    store = app.state.vector_store
    store.add("a", [0, 0])
    store.add("b", [1, 0])
    store.add("c", [2, 0])
    token = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    ).json()["access_token"]
    res = client.get(
        "/vectors/search",
        params=[("vector", 1.1), ("vector", 0), ("k", 2)],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["ids"] == ["b", "c"]


def test_search_vectors_invalid_dimension(store_cls) -> None:
    configure_vector_store(store_cls(dim=2, use_gpu=False))
    client = TestClient(app)
    store = app.state.vector_store
    store.add("a", [0, 0])
    token = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    ).json()["access_token"]
    res = client.get(
        "/vectors/search",
        params=[("vector", 1.1)],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "Invalid vector dimension"


def test_benchmark_endpoint(store_cls):
    configure_vector_store(store_cls(dim=2, use_gpu=False))
    client = TestClient(app)
    token = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    ).json()["access_token"]
    res = client.get(
        "/vectors/benchmark",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "avg_build_time" in data and "avg_query_latency" in data


def test_benchmark_requires_authentication(store_cls) -> None:
    configure_vector_store(store_cls(dim=2, use_gpu=False))
    client = TestClient(app)
    res = client.get("/vectors/benchmark")
    assert res.status_code == 401


def test_recall_by_query(monkeypatch, store_cls) -> None:
    configure_vector_store(store_cls(dim=2, use_gpu=False))
    from ume import MockGraph
    from ume.api import configure_graph

    graph = MockGraph()
    graph.add_node("a", {"val": 1})
    graph.add_node("b", {"val": 2})
    configure_graph(graph)
    store = app.state.vector_store
    store.add("a", [1.0, 0.0])
    store.add("b", [0.0, 1.0])

    monkeypatch.setattr("ume.embedding.generate_embedding", lambda q: [1.0, 0.0])
    client = TestClient(app)
    token = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    ).json()["access_token"]
    res = client.get(
        "/recall",
        params={"query": "foo", "k": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data == {"nodes": [{"id": "a", "attributes": {"val": 1}}]}


def test_recall_invalid_dimension(store_cls) -> None:
    configure_vector_store(store_cls(dim=2, use_gpu=False))
    from ume import MockGraph
    from ume.api import configure_graph

    graph = MockGraph()
    graph.add_node("a", {})
    configure_graph(graph)
    client = TestClient(app)
    token = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    ).json()["access_token"]
    res = client.get(
        "/recall",
        params=[("vector", 0.0)],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "Invalid vector dimension"


def test_recall_unauthorized(store_cls) -> None:
    configure_vector_store(store_cls(dim=2, use_gpu=False))
    from ume import MockGraph
    from ume.api import configure_graph

    graph = MockGraph()
    graph.add_node("a", {})
    configure_graph(graph)
    client = TestClient(app)
    res = client.get("/recall", params={"vector": [0.0, 1.0]})
    assert res.status_code == 401


def test_recall_stream(store_cls, monkeypatch) -> None:
    configure_vector_store(store_cls(dim=2, use_gpu=False))
    from ume import MockGraph
    from ume.api import configure_graph

    graph = MockGraph()
    graph.add_node("a", {"val": 1})
    configure_graph(graph)
    store = app.state.vector_store
    store.add("a", [1.0, 0.0])
    monkeypatch.setattr("ume.embedding.generate_embedding", lambda q: [1.0, 0.0])
    with TestClient(app) as client:
        token = client.post(
            "/auth/token",
            data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
        ).json()["access_token"]
        with client.stream(
            "GET",
            "/recall/stream",
            params={"query": "foo", "k": 1},
            headers={"Authorization": f"Bearer {token}"},
        ) as res:
            assert res.status_code == 200
            lines = [line for line in res.iter_lines() if line.startswith("data:")]
        assert lines
