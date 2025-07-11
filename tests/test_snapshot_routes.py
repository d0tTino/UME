from pathlib import Path
from tempfile import TemporaryDirectory
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

import os
import types

os.environ.setdefault("UME_VECTOR_BACKEND", "faiss")
sys.modules.setdefault("faiss", types.ModuleType("faiss"))

from ume.config import settings
object.__setattr__(settings, "UME_VECTOR_BACKEND", "faiss")

from ume.resources import create_graph_adapter
from ume.api import app, configure_graph
from ume.event_ledger import EventLedger


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
            kw.setdefault("check_same_thread", False)
            return orig_connect(*a, **kw)
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


@pytest.mark.parametrize(
    "backend,service",
    [
        ("sqlite", None),
        ("postgres", "postgres_service"),
        ("redis", "redis_service"),
    ],
)
def test_restore_route_builds_graph(
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
            kw.setdefault("check_same_thread", False)
            return orig_connect(*a, **kw)

        monkeypatch.setattr(sqlite3, "connect", _connect)

    monkeypatch.setenv("UME_GRAPH_BACKEND", backend)
    monkeypatch.setenv("UME_DB_PATH", db_path)
    monkeypatch.setattr(settings, "UME_GRAPH_BACKEND", backend, raising=False)
    monkeypatch.setattr(settings, "UME_DB_PATH", db_path, raising=False)

    ledger = EventLedger(str(tmp_path / "ledger.db"))
    ledger.append(
        0,
        {
            "event_type": "CREATE_NODE",
            "timestamp": 1,
            "node_id": "a",
            "payload": {"node_id": "a"},
        },
    )
    ledger.append(
        1,
        {
            "event_type": "CREATE_NODE",
            "timestamp": 2,
            "node_id": "b",
            "payload": {"node_id": "b"},
        },
    )
    ledger.append(
        2,
        {
            "event_type": "CREATE_EDGE",
            "timestamp": 3,
            "node_id": "a",
            "target_node_id": "b",
            "label": "L",
            "payload": {},
        },
    )
    monkeypatch.setattr("ume.snapshot_routes.event_ledger", ledger)

    graph = create_graph_adapter(db_path)
    configure_graph(graph)

    client = TestClient(app)
    token = _token(client)

    res = client.post(
        "/snapshot/restore",
        json={"path": db_path},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    fresh = create_graph_adapter(db_path)
    assert set(fresh.get_all_node_ids()) == {"a", "b"}
    assert ("a", "b", "L") in fresh.get_all_edges()


@pytest.mark.parametrize(
    "backend,service",
    [
        ("sqlite", None),
        ("postgres", "postgres_service"),
        ("redis", "redis_service"),
    ],
)
def test_save_route_creates_file(
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
            kw.setdefault("check_same_thread", False)
            return orig_connect(*a, **kw)

        monkeypatch.setattr(sqlite3, "connect", _connect)

    monkeypatch.setenv("UME_GRAPH_BACKEND", backend)
    monkeypatch.setenv("UME_DB_PATH", db_path)
    monkeypatch.setattr(settings, "UME_GRAPH_BACKEND", backend, raising=False)
    monkeypatch.setattr(settings, "UME_DB_PATH", db_path, raising=False)

    graph = create_graph_adapter(db_path)
    graph.add_node("a", {"x": 1})
    configure_graph(graph)

    client = TestClient(app)
    token = _token(client)

    with TemporaryDirectory() as tmpdir:
        snapshot = Path(tmpdir) / "snap.json"

        res = client.post(
            "/snapshot/save",
            json={"path": str(snapshot)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert snapshot.is_file()


@pytest.mark.parametrize(
    "backend,service",
    [
        ("sqlite", None),
        ("postgres", "postgres_service"),
        ("redis", "redis_service"),
    ],
)
def test_load_route_restores_graph(
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
            kw.setdefault("check_same_thread", False)
            return orig_connect(*a, **kw)

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

    with TemporaryDirectory() as tmpdir:
        snapshot = Path(tmpdir) / "snap.json"

        res_save = client.post(
            "/snapshot/save",
            json={"path": str(snapshot)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_save.status_code == 200

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


@pytest.mark.parametrize(
    "backend,service",
    [
        ("sqlite", None),
        ("postgres", "postgres_service"),
        ("redis", "redis_service"),
    ],
)
def test_restore_route_temporarydir(
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
            kw.setdefault("check_same_thread", False)
            return orig_connect(*a, **kw)

        monkeypatch.setattr(sqlite3, "connect", _connect)

    monkeypatch.setenv("UME_GRAPH_BACKEND", backend)
    monkeypatch.setenv("UME_DB_PATH", db_path)
    monkeypatch.setattr(settings, "UME_GRAPH_BACKEND", backend, raising=False)
    monkeypatch.setattr(settings, "UME_DB_PATH", db_path, raising=False)

    with TemporaryDirectory() as tmpdir:
        ledger = EventLedger(str(Path(tmpdir) / "ledger.db"))

        ledger.append(
            0,
            {
                "event_type": "CREATE_NODE",
                "timestamp": 1,
                "node_id": "a",
                "payload": {"node_id": "a"},
            },
        )
        ledger.append(
            1,
            {
                "event_type": "CREATE_NODE",
                "timestamp": 2,
                "node_id": "b",
                "payload": {"node_id": "b"},
            },
        )
        ledger.append(
            2,
            {
                "event_type": "CREATE_EDGE",
                "timestamp": 3,
                "node_id": "a",
                "target_node_id": "b",
                "label": "L",
                "payload": {},
            },
        )

        monkeypatch.setattr("ume.snapshot_routes.event_ledger", ledger)

        graph = create_graph_adapter(db_path)
        configure_graph(graph)

        client = TestClient(app)
        token = _token(client)

        res = client.post(
            "/snapshot/restore",
            json={"path": db_path},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200

        fresh = create_graph_adapter(db_path)
        assert set(fresh.get_all_node_ids()) == {"a", "b"}
        assert ("a", "b", "L") in fresh.get_all_edges()


def test_snapshot_dir_restrictions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setenv("UME_SNAPSHOT_DIR", str(allowed))
    monkeypatch.setattr(settings, "UME_SNAPSHOT_DIR", str(allowed), raising=False)
    db_path = str(tmp_path / "graph.db")
    monkeypatch.setenv("UME_GRAPH_BACKEND", "sqlite")
    monkeypatch.setenv("UME_DB_PATH", db_path)
    monkeypatch.setattr(settings, "UME_GRAPH_BACKEND", "sqlite", raising=False)
    monkeypatch.setattr(settings, "UME_DB_PATH", db_path, raising=False)
    import sqlite3
    orig_connect = sqlite3.connect

    def _connect(*a: object, **kw: object) -> sqlite3.Connection:
        kw.setdefault("check_same_thread", False)
        return orig_connect(*a, **kw)

    monkeypatch.setattr(sqlite3, "connect", _connect)
    graph = create_graph_adapter(db_path)
    configure_graph(graph)
    client = TestClient(app)
    token = _token(client)

    inside = allowed / "snap.json"
    res_ok = client.post(
        "/snapshot/save",
        json={"path": str(inside)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_ok.status_code == 200

    outside = tmp_path / "snap.json"
    res_bad = client.post(
        "/snapshot/save",
        json={"path": str(outside)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_bad.status_code == 400
    assert res_bad.json()["detail"] == "Path outside allowed directory"

@pytest.mark.parametrize("dir_value", ["", "."])
def test_unrestricted_snapshot_dir_allows_absolute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dir_value: str) -> None:
    monkeypatch.setenv("UME_SNAPSHOT_DIR", dir_value)
    monkeypatch.setattr(settings, "UME_SNAPSHOT_DIR", dir_value, raising=False)
    db_path = str(tmp_path / "graph.db")
    monkeypatch.setenv("UME_GRAPH_BACKEND", "sqlite")
    monkeypatch.setenv("UME_DB_PATH", db_path)
    monkeypatch.setattr(settings, "UME_GRAPH_BACKEND", "sqlite", raising=False)
    monkeypatch.setattr(settings, "UME_DB_PATH", db_path, raising=False)
    import sqlite3
    orig_connect = sqlite3.connect

    def _connect(*a: object, **kw: object) -> sqlite3.Connection:
        kw.setdefault("check_same_thread", False)
        return orig_connect(*a, **kw)

    monkeypatch.setattr(sqlite3, "connect", _connect)
    graph = create_graph_adapter(db_path)
    configure_graph(graph)
    client = TestClient(app)
    token = _token(client)

    snapshot = tmp_path / "snap.json"
    res = client.post(
        "/snapshot/save",
        json={"path": str(snapshot)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

