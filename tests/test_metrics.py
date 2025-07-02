import pytest
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

spec_graph = importlib.util.spec_from_file_location("ume.graph", root / "src" / "ume" / "graph.py")
assert spec_graph and spec_graph.loader
graph_module = importlib.util.module_from_spec(spec_graph)
sys.modules["ume.graph"] = graph_module
spec_graph.loader.exec_module(graph_module)
MockGraph = graph_module.MockGraph

spec_config = importlib.util.spec_from_file_location("ume.config", root / "src" / "ume" / "config.py")
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
    yield
    REQUEST_COUNT.clear()
    REQUEST_LATENCY.clear()


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
