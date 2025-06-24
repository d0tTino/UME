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

from ume.grpc_service import UMEServicer, serve


class DummyEngine:
    def __init__(self, result=None):
        self.result = result or []

    def execute_cypher(self, query: str):
        return self.result


class DummyStore:
    def __init__(self, ids=None):
        self.ids = ids or []
        self.queries = []

    def query(self, vector, k=5):
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
        def __init__(self):
            self.ports = []

        def add_insecure_port(self, addr):
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
