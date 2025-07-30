import pytest
from pytest import MonkeyPatch
from fastapi.testclient import TestClient
import importlib.util
import os
import sys
from pathlib import Path
from typing import Generator, List
import types
from prometheus_client.samples import Sample

sys.modules.setdefault("numpy", types.ModuleType("numpy"))
sys.modules.setdefault("neo4j", types.ModuleType("neo4j"))
neo4j_mod = sys.modules["neo4j"]
class GraphDatabase:  # minimal stub
    pass
class Driver:  # minimal stub
    pass
neo4j_mod.GraphDatabase = GraphDatabase  # type: ignore[attr-defined]
neo4j_mod.Driver = Driver  # type: ignore[attr-defined]
resource_mod = types.ModuleType("opentelemetry.sdk.resources")
class Resource:  # minimal stub
    pass
resource_mod.Resource = Resource  # type: ignore[attr-defined]
sys.modules.setdefault("opentelemetry.sdk.resources", resource_mod)

http_exporter_mod = types.ModuleType(
    "opentelemetry.exporter.otlp.proto.http.trace_exporter"
)
class OTLPSpanExporter:  # minimal stub
    pass
http_exporter_mod.OTLPSpanExporter = OTLPSpanExporter  # type: ignore[attr-defined]
sys.modules.setdefault(
    "opentelemetry.exporter.otlp.proto.http.trace_exporter",
    http_exporter_mod,
)

grpc_exporter_mod = types.ModuleType(
    "opentelemetry.exporter.otlp.proto.grpc.trace_exporter"
)
grpc_exporter_mod.OTLPSpanExporter = OTLPSpanExporter  # type: ignore[attr-defined]
sys.modules.setdefault(
    "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
    grpc_exporter_mod,
)

root = Path(__file__).resolve().parents[1]
os.environ.setdefault("UME_AUDIT_SIGNING_KEY", "test-key")
old_ume = sys.modules.get("ume")
old_api = sys.modules.get("ume.api")
old_metrics = sys.modules.get("ume.metrics")
old_graph = sys.modules.get("ume.graph")
old_config = sys.modules.get("ume.config")
package = types.ModuleType("ume")
package.__path__ = [str(root / "src" / "ume")]
sys.modules["ume"] = package

class DummyVS:
    def __init__(self, *_: object, **__: object) -> None:
        pass

def dummy_create() -> DummyVS:
    return DummyVS()


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

package.VectorStore = DummyVS  # type: ignore[attr-defined]
package.create_vector_store = dummy_create  # type: ignore[attr-defined]
package.create_default_store = dummy_create  # type: ignore[attr-defined]

spec_api = importlib.util.spec_from_file_location("ume.api", root / "src" / "ume" / "api.py")
assert spec_api and spec_api.loader
api_module = importlib.util.module_from_spec(spec_api)
sys.modules["ume.api"] = api_module
spec_api.loader.exec_module(api_module)
app = api_module.app
configure_graph = api_module.configure_graph
configure_vector_store = api_module.configure_vector_store

if "ume.metrics" in sys.modules:
    metrics_module = sys.modules["ume.metrics"]
else:
    spec_metrics = importlib.util.spec_from_file_location("ume.metrics", root / "src" / "ume" / "metrics.py")
    assert spec_metrics and spec_metrics.loader
    metrics_module = importlib.util.module_from_spec(spec_metrics)
    sys.modules["ume.metrics"] = metrics_module
    spec_metrics.loader.exec_module(metrics_module)
REQUEST_COUNT = metrics_module.REQUEST_COUNT
REQUEST_LATENCY = metrics_module.REQUEST_LATENCY
RECALL_LATENCY = metrics_module.RECALL_LATENCY
RECALL_LATENCY_MS = metrics_module.RECALL_LATENCY_MS
LEDGER_COMPACTED_BYTES = metrics_module.LEDGER_COMPACTED_BYTES
INGEST_EVENTS_TOTAL = metrics_module.INGEST_EVENTS_TOTAL
SEMANTIC_SEARCH_LATENCY = metrics_module.SEMANTIC_SEARCH_LATENCY

spec_graph = importlib.util.spec_from_file_location("ume.graph", root / "src" / "ume" / "graph.py")
assert spec_graph and spec_graph.loader
graph_module = importlib.util.module_from_spec(spec_graph)
sys.modules["ume.graph"] = graph_module
spec_graph.loader.exec_module(graph_module)
MockGraph = graph_module.MockGraph

spec_config = importlib.util.spec_from_file_location(
    "ume.config", root / "src" / "ume" / "config" / "__init__.py"
)
assert spec_config and spec_config.loader
config_module = importlib.util.module_from_spec(spec_config)
sys.modules["ume.config"] = config_module
spec_config.loader.exec_module(config_module)
settings = config_module.settings

if old_ume is not None:
    sys.modules["ume"] = old_ume
else:
    sys.modules.pop("ume", None)
if old_api is not None:
    sys.modules["ume.api"] = old_api
else:
    sys.modules.pop("ume.api", None)
if old_metrics is not None:
    sys.modules["ume.metrics"] = old_metrics
else:
    sys.modules.pop("ume.metrics", None)
if old_graph is not None:
    sys.modules["ume.graph"] = old_graph
else:
    sys.modules.pop("ume.graph", None)
if old_config is not None:
    sys.modules["ume.config"] = old_config
else:
    sys.modules.pop("ume.config", None)


def setup_module(_: object) -> None:
    object.__setattr__(settings, "UME_API_TOKEN", "secret-token")
    app.state.query_engine = type("QE", (), {"execute_cypher": lambda self, q: [{"q": q}]})()
    configure_graph(MockGraph())


def _token(client: TestClient) -> str:
    res = client.post(
        "/auth/token",
        data={
            "username": settings.UME_OAUTH_USERNAME,
            "password": settings.UME_OAUTH_PASSWORD,
        },
    )
    token = res.json()["access_token"]
    assert isinstance(token, str)
    return token


@pytest.fixture(autouse=True)  # type: ignore[misc]
def reset_metrics() -> Generator[None, None, None]:
    REQUEST_COUNT.clear()
    REQUEST_LATENCY.clear()
    INGEST_EVENTS_TOTAL.clear()
    yield
    REQUEST_COUNT.clear()
    REQUEST_LATENCY.clear()
    INGEST_EVENTS_TOTAL.clear()


def _count_samples() -> List[Sample]:
    return [
        s
        for m in REQUEST_COUNT.collect()
        for s in m.samples
        if s.name.endswith("_total")
    ]


def _latency_counts() -> List[float]:
    return [
        s.value
        for m in REQUEST_LATENCY.collect()
        for s in m.samples
        if s.name.endswith("_count")
    ]


def _recall_latency_counts() -> List[float]:
    return [
        s.value
        for m in RECALL_LATENCY.collect()
        for s in m.samples
        if s.name.endswith("_count")
    ]


def _recall_latency_ms_counts() -> List[float]:
    return [
        s.value
        for m in RECALL_LATENCY_MS.collect()
        for s in m.samples
        if s.name.endswith("_count")
    ]


def _ingest_event_count(event_type: str) -> float:
    for m in INGEST_EVENTS_TOTAL.collect():
        for s in m.samples:
            if s.name.endswith("_total") and s.labels.get("event_type") == event_type:
                return float(s.value)
    return 0.0


def _semantic_latency_counts() -> List[float]:
    return [
        s.value
        for m in SEMANTIC_SEARCH_LATENCY.collect()
        for s in m.samples
        if s.name.endswith("_count")
    ]


def _ledger_compacted_bytes() -> float:
    for m in LEDGER_COMPACTED_BYTES.collect():
        for s in m.samples:
            if s.name == "ume_ledger_compacted_bytes" and s.labels == {}:
                return float(s.value)
    return 0.0


def test_http_metrics_recorded():
    client = TestClient(app)
    tok = _token(client)
    client.get("/query", params={"cypher": "MATCH (n)"}, headers={"Authorization": f"Bearer {tok}"})
    client.get("/metrics", headers={"Authorization": f"Bearer {tok}"})

    paths = {s.labels.get("path") for s in _count_samples()}
    assert "/query" in paths and "/metrics" in paths
    assert sum(_latency_counts()) > 0


def test_metrics_reset_between_tests():
    assert _count_samples() == []
    assert sum(_latency_counts()) == 0


def test_recall_latency_metric_recorded(tmp_path) -> None:
    configure_graph(MockGraph())
    configure_vector_store(DummyVectorStore(dim=2))
    app.state.vector_store = DummyVectorStore(dim=2)
    app.state.graph = MockGraph()
    client = TestClient(app)
    tok = _token(client)
    store = app.state.vector_store
    store.add("n1", [0.0, 1.0])
    app.state.graph.get_node = lambda _id: {"embedding": [0.0, 1.0]}
    client.get(
        "/recall",
        params=[("vector", 0.0), ("vector", 1.0)],
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert sum(_recall_latency_counts()) > 0


def test_recall_metrics_exposed_via_endpoint(tmp_path) -> None:
    configure_graph(MockGraph())
    configure_vector_store(DummyVectorStore(dim=2))
    app.state.vector_store = DummyVectorStore(dim=2)
    app.state.graph = MockGraph()
    client = TestClient(app)
    tok = _token(client)
    store = app.state.vector_store
    store.add("n1", [0.0, 1.0])
    app.state.graph.get_node = lambda _id: {"embedding": [0.0, 1.0]}
    before_sec = sum(_recall_latency_counts())
    before_ms = sum(_recall_latency_ms_counts())
    client.get(
        "/recall",
        params=[("vector", 0.0), ("vector", 1.0)],
        headers={"Authorization": f"Bearer {tok}"},
    )
    client.get("/metrics", headers={"Authorization": f"Bearer {tok}"})
    assert sum(_recall_latency_counts()) > before_sec
    assert sum(_recall_latency_ms_counts()) > before_ms


def test_ledger_compacted_bytes_metric_recorded() -> None:
    LEDGER_COMPACTED_BYTES.set(123)
    client = TestClient(app)
    tok = _token(client)
    client.get("/metrics", headers={"Authorization": f"Bearer {tok}"})
    assert _ledger_compacted_bytes() == 123


def test_ingest_events_counter_increment(monkeypatch: MonkeyPatch) -> None:
    from ume import ingestion_api as ingestion_api_mod

    class FakeProducer:
        def __init__(self) -> None:
            self.produced: list[tuple[str, bytes]] = []

        def produce(self, topic: str, value: bytes) -> None:
            self.produced.append((topic, value))

        def poll(self, _: int) -> None:
            pass

        def flush(self) -> None:
            pass

    prod = FakeProducer()
    monkeypatch.setattr(ingestion_api_mod, "Producer", lambda conf: prod)
    with TestClient(ingestion_api_mod.app) as client:
        before = _ingest_event_count("CREATE_NODE")
        event = {"eventType": "CREATE_NODE", "timestamp": 1, "node_id": "n1", "payload": {}}
        res = client.post("/events", json=event)
        assert res.status_code == 202
        assert _ingest_event_count("CREATE_NODE") == before + 1


def test_semantic_search_latency_metric_recorded(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("ume.embedding.generate_embedding", lambda _: [1.0, 0.0])
    configure_vector_store(DummyVectorStore(dim=2))
    app.state.vector_store = DummyVectorStore(dim=2)
    g = MockGraph()
    g.add_node("a", {"val": 1})
    configure_graph(g)
    app.state.vector_store.add("a", [1.0, 0.0])
    with TestClient(app) as client:
        tok = _token(client)
        before = sum(_semantic_latency_counts())
        res = client.post(
            "/search/semantic",
            json={"query": "foo", "k": 1},
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert res.status_code == 200
        assert sum(_semantic_latency_counts()) > before
