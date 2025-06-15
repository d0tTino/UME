from fastapi.testclient import TestClient

from ume.api import app
from ume.config import settings


def setup_module(_):
    app.state.vector_index = {}


def test_add_vector_authorized():
    client = TestClient(app)
    res = client.post(
        "/vectors",
        json={"id": "v1", "vector": [0.0, 1.0]},
        headers={"Authorization": f"Bearer {settings.UME_API_TOKEN}"},
    )
    assert res.status_code == 200
    assert app.state.vector_index["v1"] == [0.0, 1.0]


def test_add_vector_unauthorized():
    client = TestClient(app)
    res = client.post("/vectors", json={"id": "v2", "vector": [1.0]})
    assert res.status_code == 401


def test_search_vectors():
    client = TestClient(app)
    app.state.vector_index = {"a": [0, 0], "b": [1, 0], "c": [2, 0]}
    res = client.get(
        "/vectors/search",
        params=[("vector", 1.1), ("vector", 0), ("k", 2)],
        headers={"Authorization": f"Bearer {settings.UME_API_TOKEN}"},
    )
    assert res.status_code == 200
    assert res.json()["ids"] == ["b", "c"]
