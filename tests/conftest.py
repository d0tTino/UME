from __future__ import annotations

import sys
import types
import importlib
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
if importlib.util.find_spec("httpx") is None:
    sys.modules.setdefault("httpx", types.ModuleType("httpx"))

yaml_stub = types.ModuleType("yaml")
yaml_stub.safe_load = lambda _: {}
if importlib.util.find_spec("yaml") is None:
    sys.modules.setdefault("yaml", yaml_stub)

prom_stub = types.ModuleType("prometheus_client")


class _DummyValue:  # pragma: no cover - minimal metric value stub
    def __init__(self) -> None:
        self._v = 0

    def set(self, value: int | float) -> None:
        self._v = value

    def get(self) -> int | float:
        return self._v


class _DummyMetric:  # pragma: no cover - simple stub
    def __init__(self, *_: object, **__: object) -> None:
        self._value = _DummyValue()

    def labels(self, *_: object, **__: object) -> "_DummyMetric":
        return self

    def inc(self, amount: int | float = 1) -> None:
        self._value.set(self._value.get() + amount)

    def set(self, value: int | float) -> None:
        self._value.set(value)

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
if importlib.util.find_spec("jsonschema") is None:
    sys.modules.setdefault("jsonschema", jsonschema_stub)

# Force the vector backend to chroma to avoid faiss dependency during tests
from ume.config import settings as _settings  # noqa: E402
object.__setattr__(_settings, "UME_VECTOR_BACKEND", "chroma")

# Additional optional packages used in some modules. These are large or
# platform-specific dependencies that aren't needed for most unit tests, so we
# provide lightweight stubs when they aren't installed.
_OPTIONAL_PACKAGES = [
    "confluent_kafka",
    "structlog",
    "neo4j",
    "faiss",
]

for _package in _OPTIONAL_PACKAGES:
    if importlib.util.find_spec(_package) is None:
        module = types.ModuleType(_package)
        if _package == "confluent_kafka":
            class _Dummy:
                pass

            module.Consumer = _Dummy
            module.Producer = _Dummy
            module.KafkaError = _Dummy
            module.KafkaException = Exception
            module.Message = _Dummy
        if _package == "faiss":
            # minimal stub just to satisfy import checks in tests
            module.IndexFlatL2 = object
        if _package == "neo4j":
            module.GraphDatabase = object
            module.Driver = object
        sys.modules.setdefault(_package, module)

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


@pytest.fixture(scope="session")
def postgres_service():
    """Launch a Postgres container for integration tests."""
    if not _docker_enabled():
        pytest.skip("Docker-based tests disabled")
    try:
        from testcontainers.postgres import PostgresContainer
    except Exception:  # pragma: no cover - optional dependency missing
        pytest.skip("Postgres test container not available")
    container = PostgresContainer("postgres:15-alpine")
    try:
        container.start()  # type: ignore[no-untyped-call]
    except Exception as exc:  # pragma: no cover - environment issues
        pytest.skip(f"Postgres not available: {exc}")
    yield {"dsn": container.get_connection_url()}
    container.stop()  # type: ignore[no-untyped-call]


@pytest.fixture(scope="session")
def redis_service():
    """Launch a Redis container for integration tests."""
    if not _docker_enabled():
        pytest.skip("Docker-based tests disabled")
    try:
        from testcontainers.redis import RedisContainer
    except Exception:  # pragma: no cover - optional dependency missing
        pytest.skip("Redis test container not available")
    container = RedisContainer("redis:7-alpine")
    try:
        container.start()  # type: ignore[no-untyped-call]
    except Exception as exc:  # pragma: no cover - environment issues
        pytest.skip(f"Redis not available: {exc}")
    port = container.get_exposed_port(6379)  # type: ignore[no-untyped-call]
    host = container.get_container_host_ip()
    yield {"url": f"redis://{host}:{port}/0"}
    container.stop()  # type: ignore[no-untyped-call]

