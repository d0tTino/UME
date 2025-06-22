from fastapi.testclient import TestClient
import pytest

from ume import VectorStore
from ume.api import app, configure_vector_store
from ume.config import settings

pytest.importorskip("faiss")


def test_add_vector_authorized() -> None:
    configure_vector_store(VectorStore(dim=2, use_gpu=False))
    client = TestClient(app)
    token = client.post(
        "/token",
        data={
            "username": settings.UME_OAUTH_USERNAME,
            "password": settings.UME_OAUTH_PASSWORD,
            "scope": settings.UME_OAUTH_ROLE,
        },
    ).json()["access_token"]
    res = client.post(
        "/vectors",
        json={"id": "v1", "vector": [0.0, 1.0]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert app.state.vector_store.query([0.0, 1.0], k=1) == ["v1"]


def test_add_vector_invalid_dimension() -> None:
    configure_vector_store(VectorStore(dim=2, use_gpu=False))
    client = TestClient(app)
    token = client.post(
        "/token",
        data={
            "username": settings.UME_OAUTH_USERNAME,
            "password": settings.UME_OAUTH_PASSWORD,
            "scope": settings.UME_OAUTH_ROLE,
        },
    ).json()["access_token"]
    res = client.post(
        "/vectors",
        json={"id": "v_bad", "vector": [0.0]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "Invalid vector dimension"


def test_add_vector_unauthorized() -> None:
    configure_vector_store(VectorStore(dim=2, use_gpu=False))
    client = TestClient(app)
    res = client.post("/vectors", json={"id": "v2", "vector": [1.0]})
    assert res.status_code == 401


def test_search_vectors() -> None:
    configure_vector_store(VectorStore(dim=2, use_gpu=False))
    client = TestClient(app)
    store = app.state.vector_store
    store.add("a", [0, 0])
    store.add("b", [1, 0])
    store.add("c", [2, 0])
    token = client.post(
        "/token",
        data={
            "username": settings.UME_OAUTH_USERNAME,
            "password": settings.UME_OAUTH_PASSWORD,
            "scope": settings.UME_OAUTH_ROLE,
        },
    ).json()["access_token"]
    res = client.get(
        "/vectors/search",
        params=[("vector", 1.1), ("vector", 0), ("k", 2)],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["ids"] == ["b", "c"]


def test_search_vectors_invalid_dimension() -> None:
    configure_vector_store(VectorStore(dim=2, use_gpu=False))
    client = TestClient(app)
    store = app.state.vector_store
    store.add("a", [0, 0])
    token = client.post(
        "/token",
        data={
            "username": settings.UME_OAUTH_USERNAME,
            "password": settings.UME_OAUTH_PASSWORD,
            "scope": settings.UME_OAUTH_ROLE,
        },
    ).json()["access_token"]
    res = client.get(
        "/vectors/search",
        params=[("vector", 1.1)],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "Invalid vector dimension"


def test_benchmark_endpoint():
    configure_vector_store(VectorStore(dim=2, use_gpu=False))
    client = TestClient(app)
    token = client.post(
        "/token",
        data={
            "username": settings.UME_OAUTH_USERNAME,
            "password": settings.UME_OAUTH_PASSWORD,
            "scope": settings.UME_OAUTH_ROLE,
        },
    ).json()["access_token"]
    res = client.get(
        "/vectors/benchmark",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "build_time" in data and "avg_query_latency" in data
