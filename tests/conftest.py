from __future__ import annotations

import sys
from pathlib import Path
import os

try:
    from testcontainers.core.container import DockerContainer
    from testcontainers.neo4j import Neo4jContainer
except Exception:  # pragma: no cover - optional dependency may be missing
    DockerContainer = None
    Neo4jContainer = None

import pytest

# Ensure the src directory is importable when UME isn't installed
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from ume.pipeline import privacy_agent as privacy_agent_module
except Exception:  # pragma: no cover - optional deps may be missing
    privacy_agent_module = None


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
    container.with_exposed_ports(9092)
    container.with_command(
        "redpanda start --smp 1 --overprovisioned --node-id 0 --check=false "
        "--kafka-addr PLAINTEXT://0.0.0.0:9092 "
        "--advertise-kafka-addr PLAINTEXT://127.0.0.1:9092"
    )
    try:
        container.start()
    except Exception as exc:  # pragma: no cover - environment issues
        pytest.skip(f"Redpanda not available: {exc}")
    broker = f"{container.get_container_host_ip()}:{container.get_exposed_port(9092)}"
    yield {"bootstrap_servers": broker}
    container.stop()


@pytest.fixture(scope="session")
def neo4j_service():
    """Launch a Neo4j container for integration tests."""
    if not _docker_enabled():
        pytest.skip("Docker-based tests disabled")
    container = Neo4jContainer("neo4j:5")
    container.with_env("NEO4J_AUTH", "neo4j/test")
    try:
        container.start()
    except Exception as exc:  # pragma: no cover - environment issues
        pytest.skip(f"Neo4j not available: {exc}")
    yield {
        "uri": container.get_connection_url(),
        "user": "neo4j",
        "password": "test",
    }
    container.stop()

