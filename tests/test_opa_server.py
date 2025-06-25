import shutil
import socket
import subprocess
import time

import httpx
import pytest

from ume.event import Event, EventType
from ume.plugins.alignment.rego_engine import RegoPolicyEngine
from ume.plugins.alignment import PolicyViolationError
from ume.config import settings


from typing import cast


def _get_free_port() -> int:
    with socket.socket() as s:
        s.bind(("localhost", 0))
        return cast(int, s.getsockname()[1])


@pytest.fixture(scope="session")
def opa_server(tmp_path_factory):
    opa_bin = shutil.which("opa")
    if not opa_bin:
        pytest.skip("OPA binary not available")
    assert opa_bin is not None
    port = _get_free_port()
    data_dir = tmp_path_factory.mktemp("opa")
    proc = subprocess.Popen([
        opa_bin,
        "run",
        "--server",
        "--addr",
        f"localhost:{port}",
        str(data_dir),
    ])
    url = f"http://localhost:{port}"
    for _ in range(20):
        try:
            httpx.get(f"{url}/health")
            break
        except Exception:
            time.sleep(0.1)
    else:
        proc.terminate()
        pytest.skip("OPA server failed to start")
    yield url
    proc.terminate()
    proc.wait()


def test_remote_opa_allows_event(opa_server, monkeypatch):
    policy = """package ume
default allow = true
"""
    httpx.put(f"{opa_server}/v1/policies/test", content=policy)
    monkeypatch.setattr(settings, "OPA_URL", opa_server, raising=False)
    engine = RegoPolicyEngine(policy_paths=None)
    event = Event(event_type=EventType.CREATE_NODE, timestamp=0, payload={"node_id": "n1", "attributes": {}})
    engine.validate(event)


def test_remote_opa_denies_event(opa_server, monkeypatch):
    policy = """package ume
default allow = false
"""
    httpx.put(f"{opa_server}/v1/policies/test", content=policy)
    monkeypatch.setattr(settings, "OPA_URL", opa_server, raising=False)
    engine = RegoPolicyEngine(policy_paths=None)
    event = Event(event_type=EventType.CREATE_NODE, timestamp=0, payload={"node_id": "n1", "attributes": {}})
    with pytest.raises(PolicyViolationError):
        engine.validate(event)

