from __future__ import annotations

import sys
import types
from pathlib import Path
import os

# Force pure-Python protobuf implementation for compatibility with Python 3.12
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

try:
    from testcontainers.core.container import DockerContainer
    from testcontainers.neo4j import Neo4jContainer
except Exception:  # pragma: no cover - optional dependency may be missing
    DockerContainer = None  # type: ignore[assignment,misc]
    Neo4jContainer = None  # type: ignore[assignment]

import pytest

# Ensure the src directory is importable when UME isn't installed
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Stub optional dependencies so importing ume modules doesn't fail when they
# aren't installed. Tests that rely on these packages will provide their own
# implementations.
import importlib.util

if importlib.util.find_spec("httpx") is None:
    sys.modules.setdefault("httpx", types.ModuleType("httpx"))

yaml_stub = types.ModuleType("yaml")
yaml_stub.safe_load = lambda _: {}
if importlib.util.find_spec("yaml") is None:
    sys.modules.setdefault("yaml", yaml_stub)

prom_stub = types.ModuleType("prometheus_client")
class _DummyMetric:  # pragma: no cover - simple stub
    def __init__(self, *_: object, **__: object) -> None:
        pass

    def labels(self, *_: object, **__: object) -> "_DummyMetric":
        return self

    def inc(self, *_: object, **__: object) -> None:
        pass

    def observe(self, *_: object, **__: object) -> None:
        pass

prom_stub.Counter = _DummyMetric  # type: ignore[attr-defined]
prom_stub.Histogram = _DummyMetric  # type: ignore[attr-defined]
prom_stub.Gauge = _DummyMetric  # type: ignore[attr-defined]
if importlib.util.find_spec("prometheus_client") is None:
    sys.modules.setdefault("prometheus_client", prom_stub)

if importlib.util.find_spec("numpy") is None:
    sys.modules.setdefault("numpy", types.ModuleType("numpy"))
jsonschema_stub = types.ModuleType("jsonschema")
class _ValidationError(Exception):
    pass

def _validate(*_: object, **__: object) -> None:
    return None

jsonschema_stub.validate = _validate  # type: ignore[attr-defined]
jsonschema_stub.ValidationError = _ValidationError  # type: ignore[attr-defined]
sys.modules.setdefault("jsonschema", jsonschema_stub)

try:
    from ume.pipeline import privacy_agent as privacy_agent_module
except Exception:  # pragma: no cover - optional deps may be missing
    privacy_agent_module = None  # type: ignore[assignment]


@pytest.fixture
def privacy_agent():
    return privacy_agent_module


def _docker_enabled() -> bool:
    return DockerContainer is not None and bool(os.environ.get("UME_DOCKER_TESTS"))


@pytest.fixture(scope="session")
def redpanda_service():
    """Spin up a Redpanda container for integration tests."""
    if not _docker_enabled():
        pytest.skip("Docker-based tests disabled")
    container = DockerContainer("docker.redpanda.com/redpandadata/redpanda:latest")
    container.with_exposed_ports(9092)  # type: ignore[no-untyped-call]
    container.with_command(
        "redpanda start --smp 1 --overprovisioned --node-id 0 --check=false "
        "--kafka-addr PLAINTEXT://0.0.0.0:9092 "
        "--advertise-kafka-addr PLAINTEXT://127.0.0.1:9092"
    )
    try:
        container.start()  # type: ignore[no-untyped-call]
    except Exception as exc:  # pragma: no cover - environment issues
        pytest.skip(f"Redpanda not available: {exc}")
    broker = f"{container.get_container_host_ip()}:{container.get_exposed_port(9092)}"
    yield {"bootstrap_servers": broker}
    container.stop()  # type: ignore[no-untyped-call]


@pytest.fixture(scope="session")
def neo4j_service():
    """Launch a Neo4j container for integration tests."""
    if not _docker_enabled():
        pytest.skip("Docker-based tests disabled")
    container = Neo4jContainer("neo4j:5")
    container.with_env("NEO4J_AUTH", "neo4j/test")  # type: ignore[no-untyped-call]
    try:
        container.start()  # type: ignore[no-untyped-call]
    except Exception as exc:  # pragma: no cover - environment issues
        pytest.skip(f"Neo4j not available: {exc}")
    yield {
        "uri": container.get_connection_url(),
        "user": "neo4j",
        "password": "test",
    }
    container.stop()  # type: ignore[no-untyped-call]

