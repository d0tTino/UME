# ruff: noqa: E402

import asyncio

import grpc
import sys
import importlib.util
from pathlib import Path


# Load generated protobuf modules manually so we can alias them before importing
# ume_client.
base = Path(__file__).resolve().parents[1] / "src" / "ume_client"
spec = importlib.util.spec_from_file_location("ume_client.ume_pb2", base / "ume_pb2.py")
assert spec is not None and spec.loader is not None
ume_pb2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ume_pb2)
sys.modules["ume_client.ume_pb2"] = ume_pb2
sys.modules["ume_pb2"] = ume_pb2

spec = importlib.util.spec_from_file_location("ume_client.ume_pb2_grpc", base / "ume_pb2_grpc.py")
assert spec is not None and spec.loader is not None
ume_pb2_grpc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ume_pb2_grpc)
sys.modules["ume_client.ume_pb2_grpc"] = ume_pb2_grpc
sys.modules["ume_pb2_grpc"] = ume_pb2_grpc


import types
sys.modules.setdefault("httpx", types.ModuleType("httpx"))
sys.modules.setdefault("structlog", types.ModuleType("structlog"))

from ume.grpc_service import UMEServicer, serve, main


class DummyEngine:
    def __init__(self, result: list[dict[str, object]] | None = None) -> None:
        self.result: list[dict[str, object]] = result or []

    def execute_cypher(self, query: str) -> list[dict[str, object]]:
        return self.result


class DummyStore:
    def __init__(self, ids: list[str] | None = None) -> None:
        self.ids: list[str] = ids or []
        self.queries: list[tuple[list[float], int]] = []

    def query(self, vector: list[float], k: int = 5) -> list[str]:
        self.queries.append((list(vector), k))
        return self.ids


def test_run_cypher():
    svc = UMEServicer(DummyEngine([{"a": 1}]), DummyStore())  # type: ignore[arg-type]
    req = ume_pb2.CypherQuery(cypher="MATCH n RETURN n")
    res = asyncio.run(svc.RunCypher(req, None))
    assert [dict(r) for r in res.records] == [{"a": 1}]


def test_search_vectors():
    store = DummyStore(["x", "y"])
    svc = UMEServicer(DummyEngine(), store)  # type: ignore[arg-type]
    req = ume_pb2.VectorSearchRequest(vector=[1.0, 2.0], k=2)
    res = asyncio.run(svc.SearchVectors(req, None))
    assert res.ids == ["x", "y"]
    assert store.queries == [([1.0, 2.0], 2)]


def test_get_audit_entries(monkeypatch):
    svc = UMEServicer(DummyEngine(), DummyStore())  # type: ignore[arg-type]
    monkeypatch.setattr(
        "ume.grpc_service.get_audit_entries",
        lambda: [
            {"timestamp": 1, "user_id": "u1", "reason": "r1", "signature": "s1"},
            {"timestamp": 2, "user_id": "u2", "reason": "r2", "signature": "s2"},
        ],
    )
    req = ume_pb2.AuditRequest(limit=1)
    res = asyncio.run(svc.GetAuditEntries(req, None))
    assert len(res.entries) == 1
    entry = res.entries[0]
    assert entry.timestamp == 2
    assert entry.user_id == "u2"


def test_serve(monkeypatch):
    created: dict[str, object] = {}

    class DummyServer:
        def __init__(self) -> None:
            self.ports: list[str] = []

        def add_insecure_port(self, addr: str) -> None:
            self.ports.append(addr)

    server = DummyServer()
    monkeypatch.setattr(grpc.aio, "server", lambda: server)
    monkeypatch.setattr(
        ume_pb2_grpc,
        "add_UMEServicer_to_server",
        lambda servicer, srv: created.setdefault("servicer", servicer),
    )

    result = serve(DummyEngine(), DummyStore(), port=123)  # type: ignore[arg-type]
    assert result is server
    assert server.ports == ["[::]:123"]
    assert isinstance(created["servicer"], UMEServicer)


def test_stream_cypher() -> None:
    engine = DummyEngine([{"x": 1}, {"y": 2}])
    svc = UMEServicer(engine, DummyStore())  # type: ignore[arg-type]
    req = ume_pb2.CypherQuery(cypher="MATCH n RETURN n")
    res = asyncio.run(
        collect_async(svc.StreamCypher(req, None))
    )
    assert [dict(r.record) for r in res] == [{"x": 1}, {"y": 2}]


from typing import Any, AsyncIterator, List


async def collect_async(gen: AsyncIterator[Any]) -> List[Any]:
    result: List[Any] = []
    async for item in gen:
        result.append(item)
    return result


def test_main(monkeypatch):
    called: dict[str, bool] = {}
    monkeypatch.setattr("ume.grpc_service.configure_logging", lambda: called.setdefault("log", True))

    class DummyQE:
        @staticmethod
        def from_credentials(*args, **kwargs):
            called["qe"] = True
            return "qe"

    monkeypatch.setattr("ume.grpc_service.Neo4jQueryEngine", DummyQE)

    class DummyStore2:
        def __init__(self, *args: object, **kwargs: object) -> None:
            called["store"] = True

    monkeypatch.setattr("ume.grpc_service.VectorStore", DummyStore2)

    class DummyServer:
        async def start(self) -> None:
            called["start"] = True

        async def wait_for_termination(self) -> None:
            called["wait"] = True

    monkeypatch.setattr("ume.grpc_service.serve", lambda qe, store, port=50051: DummyServer())

    asyncio.run(main())

    assert called["log"]
    assert called["qe"]
    assert called["store"]
    assert called["start"]
    assert called["wait"]
