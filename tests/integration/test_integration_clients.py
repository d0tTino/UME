from __future__ import annotations
# ruff: noqa: E402

import pytest
import sys
import importlib.util
from pathlib import Path

base = Path(__file__).resolve().parents[2]
spec_ev = importlib.util.spec_from_file_location(
    "events_pb2", base / "src" / "ume_client" / "events_pb2.py"
)
assert spec_ev and spec_ev.loader
events_pb2 = importlib.util.module_from_spec(spec_ev)
spec_ev.loader.exec_module(events_pb2)
sys.modules["events_pb2"] = events_pb2
sys.path.insert(0, str(base / "src" / "ume_client"))
sys.path.insert(0, str(base / "src"))

pytestmark = pytest.mark.integration

import httpx
from fastapi.testclient import TestClient
from ume.api import app, configure_graph, configure_vector_store
from ume.persistent_graph import PersistentGraph
from ume.integrations import (
    LangGraph,
    Letta,
    MemGPT,
    SuperMemory,
    BaseClient,
    AsyncLangGraph,
    AsyncLetta,
    AsyncBaseClient,
)
from ume.config import settings

class DummyVectorStore:
    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.vectors: dict[str, list[float]] = {}

    def add(self, vid: str, vector: list[float]) -> None:
        assert len(vector) == self.dim
        self.vectors[vid] = vector

    def query(self, vector: list[float], k: int = 5) -> list[str]:
        def dist(v: list[float]) -> float:
            return sum((a - b) ** 2 for a, b in zip(v, vector))
        return [vid for vid, v in sorted(self.vectors.items(), key=lambda kv: dist(kv[1]))][:k]

    def close(self) -> None:  # pragma: no cover - no cleanup needed
        pass


def _token(client: TestClient) -> str:
    res = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    )
    return str(res.json()["access_token"])


def test_integration_clients(tmp_path) -> None:
    db_path = tmp_path / "db.sqlite"
    graph = PersistentGraph(str(db_path), check_same_thread=False)
    configure_graph(graph)
    configure_vector_store(DummyVectorStore(dim=2))

    with TestClient(app) as client:
        token = _token(client)
        store = app.state.vector_store
        store.add("n1", [1.0, 0.0])
        store.add("n2", [0.0, 1.0])
        store.add("n3", [-1.0, 0.0])
        store.add("n4", [0.0, -1.0])

        tests = [
            (LangGraph, "n1", [1.0, 0.0]),
            (Letta, "n2", [0.0, 1.0]),
            (MemGPT, "n3", [-1.0, 0.0]),
            (SuperMemory, "n4", [0.0, -1.0]),
        ]
        for cls, nid, vec in tests:
            event = {
                "event_type": "CREATE_NODE",
                "timestamp": 1,
                "node_id": nid,
                "payload": {"node_id": nid, "attributes": {"text": nid}},
            }
            with cls(base_url=str(client.base_url), api_key=token) as c:
                assert isinstance(c, BaseClient)
                c._client = httpx.Client(base_url=str(client.base_url), transport=client._transport)  # type: ignore[attr-defined]
                c.send_events([event])
                result = c.recall({"vector": vec, "k": 1})
            assert graph.get_node(nid) == {"text": nid, "tokens": [nid]}
            assert "nodes" in result


@pytest.mark.asyncio
async def test_async_langgraph_and_letta(tmp_path) -> None:
    db_path = tmp_path / "db_async.sqlite"
    graph = PersistentGraph(str(db_path), check_same_thread=False)
    configure_graph(graph)
    configure_vector_store(DummyVectorStore(dim=2))

    with TestClient(app) as client:
        token = _token(client)
        store = app.state.vector_store
        store.add("n1", [1.0, 0.0])
        store.add("n2", [0.0, 1.0])

        async with AsyncLangGraph(base_url=str(client.base_url), api_key=token) as lg:
            assert isinstance(lg, AsyncBaseClient)
            lg._client = httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url=str(client.base_url))
            await lg.send_events([
                {"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1", "payload": {"node_id": "n1", "attributes": {"text": "n1"}}}
            ])
            result1 = await lg.recall({"vector": [1.0, 0.0], "k": 1})

        async with AsyncLetta(base_url=str(client.base_url), api_key=token) as lt:
            assert isinstance(lt, AsyncBaseClient)
            lt._client = httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url=str(client.base_url))
            await lt.send_events([
                {"event_type": "CREATE_NODE", "timestamp": 2, "node_id": "n2", "payload": {"node_id": "n2", "attributes": {"text": "n2"}}}
            ])
            result2 = await lt.recall({"vector": [0.0, 1.0], "k": 1})

        assert graph.get_node("n1") == {"text": "n1", "tokens": ["n1"]}
        assert graph.get_node("n2") == {"text": "n2", "tokens": ["n2"]}
        assert "nodes" in result1
        assert "nodes" in result2




