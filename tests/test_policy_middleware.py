import os
import time
from shutil import which
import urllib.request
import tempfile

import pytest

from ume import (
    Event,
    MockGraph,
    ProcessingError,
    RegoPolicyMiddleware,
    apply_event_to_graph,
)


def _get_opa_executable() -> str:
    """Ensure the OPA binary is available and return its path."""
    opa_path = which("opa")
    if opa_path:
        return opa_path
    url = "https://openpolicyagent.org/downloads/latest/opa_linux_amd64_static"
    tmp_dir = tempfile.mkdtemp()
    dest = os.path.join(tmp_dir, "opa")
    urllib.request.urlretrieve(url, dest)
    os.chmod(dest, 0o755)
    return dest


@pytest.fixture(scope="session")
def policy_middleware() -> RegoPolicyMiddleware:
    policy_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "policies", "example.rego"))
    opa_bin = _get_opa_executable()
    return RegoPolicyMiddleware(policy_file, opa_executable=opa_bin)


def test_allowed_event(policy_middleware: RegoPolicyMiddleware) -> None:
    graph = MockGraph()
    event = Event(event_type="CREATE_NODE", timestamp=int(time.time()), payload={"node_id": "n"})
    apply_event_to_graph(event, graph, policy=policy_middleware)
    assert graph.node_exists("n")


def test_blocked_event(policy_middleware: RegoPolicyMiddleware) -> None:
    graph = MockGraph()
    event = Event(event_type="FORBIDDEN_EVENT", timestamp=int(time.time()), payload={})
    with pytest.raises(ProcessingError, match="blocked by policy"):
        apply_event_to_graph(event, graph, policy=policy_middleware)
