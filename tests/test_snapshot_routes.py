from pathlib import Path
import sys

# ruff: noqa: E402

import pytest
from fastapi.testclient import TestClient

class _DummyLimiter:
    async def __call__(self, *_: object, **__: object) -> None:  # pragma: no cover - stub
        return None

    @classmethod
    async def init(cls, *_: object, **__: object) -> None:  # pragma: no cover - stub
        return None

sys.modules.setdefault("fastapi_limiter", type("m", (), {"FastAPILimiter": _DummyLimiter}))
sys.modules.setdefault(
    "fastapi_limiter.depends",
    type(
        "m",
        (),
        {
            "RateLimiter": type(
                "RateLimiter",
                (),
                {
                    "__init__": lambda self, *_, **__: None,
                    "__call__": lambda self, *_, **__: None,
                },
            )
        },
    ),
)

neo4j_stub = sys.modules.setdefault("neo4j", type("m", (), {}))
setattr(neo4j_stub, "GraphDatabase", type("GraphDatabase", (), {}))
setattr(neo4j_stub, "Driver", type("Driver", (), {}))

from ume.factories import create_graph_adapter
from ume.api import app, configure_graph
from ume.config import settings


def _token(client: TestClient) -> str:
    res = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    )
    return str(res.json()["access_token"])


@pytest.mark.parametrize(
    "backend,service",
    [
        ("sqlite", None),
        ("postgres", "postgres_service"),
        ("redis", "redis_service"),
    ],
)
def test_snapshot_routes_roundtrip(
    tmp_path: Path,
    backend: str,
    service: str | None,
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if service:
        info = request.getfixturevalue(service)
        db_path = info["dsn"] if backend == "postgres" else info["url"]
    else:
        db_path = str(tmp_path / "graph.db")

    if backend == "sqlite":
        import sqlite3
        orig_connect = sqlite3.connect
        def _connect(*a, **kw):
            return orig_connect(*a, check_same_thread=False, **kw)
        monkeypatch.setattr(sqlite3, "connect", _connect)
    monkeypatch.setenv("UME_GRAPH_BACKEND", backend)
    monkeypatch.setenv("UME_DB_PATH", db_path)
    monkeypatch.setattr(settings, "UME_GRAPH_BACKEND", backend, raising=False)
    monkeypatch.setattr(settings, "UME_DB_PATH", db_path, raising=False)

    graph = create_graph_adapter(db_path)
    graph.add_node("a", {"x": 1})
    graph.add_node("b", {"y": 2})
    graph.add_edge("a", "b", "L")
    configure_graph(graph)

    client = TestClient(app)
    token = _token(client)
    snapshot = tmp_path / "snap.json"

    res_save = client.post(
        "/snapshot/save",
        json={"path": str(snapshot)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_save.status_code == 200
    assert snapshot.is_file()

    graph.clear()
    fresh = create_graph_adapter(db_path)
    configure_graph(fresh)

    res_load = client.post(
        "/snapshot/load",
        json={"path": str(snapshot)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_load.status_code == 200
    assert set(fresh.get_all_node_ids()) == {"a", "b"}
    assert ("a", "b", "L") in fresh.get_all_edges()
