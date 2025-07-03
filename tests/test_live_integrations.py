from fastapi.testclient import TestClient
# ruff: noqa: E402
import sys
import types
from typing import Dict, List
import httpx
sys.modules.setdefault("neo4j", types.ModuleType("neo4j"))
neo4j_mod = sys.modules["neo4j"]
neo4j_mod.GraphDatabase = getattr(neo4j_mod, "GraphDatabase", object)
neo4j_mod.Driver = getattr(neo4j_mod, "Driver", object)

from integrations.langgraph import LangGraph
from integrations.letta import Letta
from ume.api import app, configure_graph, configure_vector_store
from ume import MockGraph
from ume.config import settings

class DummyVectorStore:
    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.vectors: Dict[str, List[float]] = {}

    def add(self, vid: str, vector: List[float]) -> None:
        assert len(vector) == self.dim
        self.vectors[vid] = vector

    def query(self, vector: List[float], k: int = 5) -> List[str]:
        def dist(v: List[float]) -> float:
            return sum((a - b) ** 2 for a, b in zip(v, vector))
        return [
            vid
            for vid, v in sorted(
                self.vectors.items(), key=lambda kv: dist(kv[1])
            )
        ][:k]

    def close(self) -> None:  # pragma: no cover - no cleanup needed
        pass


def _token(client: TestClient) -> str:
    res = client.post(
        "/auth/token",
        data={
            "username": settings.UME_OAUTH_USERNAME,
            "password": settings.UME_OAUTH_PASSWORD,
        },
    )
    return res.json()["access_token"]


def setup_module(_: object) -> None:
    object.__setattr__(settings, "UME_API_TOKEN", "live-token")
    configure_graph(MockGraph())
    configure_vector_store(DummyVectorStore(dim=2))


def test_langgraph_and_letta_roundtrip() -> None:
    client = TestClient(app)
    token = _token(client)
    store = app.state.vector_store
    store.add("n1", [1.0, 0.0])
    store.add("n2", [0.0, 1.0])
    store.add("n3", [-1.0, 0.0])

    single = {
        "event_type": "CREATE_NODE",
        "timestamp": 1,
        "node_id": "n1",
        "payload": {"node_id": "n1", "attributes": {"text": "a"}},
    }
    with LangGraph(base_url=str(client.base_url), api_key=token) as lg:
        lg._client = httpx.Client(
            base_url=str(client.base_url),
            transport=client._transport,
        )  # type: ignore[attr-defined]
        lg.send_events([single])
        result = lg.recall({"vector": [1.0, 0.0], "k": 1})
    assert app.state.graph.get_node("n1") == {"text": "a"}
    assert result == {"nodes": [{"id": "n1", "attributes": {"text": "a"}}]}

    batch = [
        {
            "event_type": "CREATE_NODE",
            "timestamp": 2,
            "node_id": "n2",
            "payload": {"node_id": "n2", "attributes": {"text": "b"}},
        },
        {
            "event_type": "CREATE_NODE",
            "timestamp": 3,
            "node_id": "n3",
            "payload": {"node_id": "n3", "attributes": {"text": "c"}},
        },
    ]
    with Letta(base_url=str(client.base_url), api_key=token) as lt:
        lt._client = httpx.Client(
            base_url=str(client.base_url),
            transport=client._transport,
        )  # type: ignore[attr-defined]
        lt.send_events(batch)
        result2 = lt.recall({"vector": [0.0, 1.0], "k": 1})
    assert app.state.graph.get_node("n2") == {"text": "b"}
    assert app.state.graph.get_node("n3") == {"text": "c"}
    assert result2 == {"nodes": [{"id": "n2", "attributes": {"text": "b"}}]}
