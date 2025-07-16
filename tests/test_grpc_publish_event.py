import asyncio
import sys
import os
import importlib.util
from pathlib import Path

import grpc
import pytest

pytest.skip("gRPC not functional in this environment", allow_module_level=True)

base = Path(__file__).resolve().parents[1]
spec_ev = importlib.util.spec_from_file_location(
    "events_pb2", base / "src" / "ume_client" / "events_pb2.py"
)
assert spec_ev and spec_ev.loader
events_pb2 = importlib.util.module_from_spec(spec_ev)
spec_ev.loader.exec_module(events_pb2)
sys.modules["events_pb2"] = events_pb2

sys.path.insert(0, str(base / "src" / "ume_client"))
sys.path.insert(0, str(base / "src"))

# Ensure required configuration is present for importing ume.grpc_server
os.environ.setdefault("UME_AUDIT_SIGNING_KEY", "test-key")

from ume_client.async_client import AsyncUMEClient  # noqa: E402
from ume.graph import MockGraph  # noqa: E402
from ume.grpc_server import serve  # noqa: E402
from ume.services.ingest import dict_to_envelope  # noqa: E402


class DummyQE:
    def execute_cypher(self, cypher: str):
        return []


class DummyStore:
    def __init__(self) -> None:
        self.queries: list[tuple[list[float], int]] = []

    def query(self, vector: list[float], k: int = 5) -> list[str]:
        self.queries.append((list(vector), k))
        return ["x"]


def _build_envelope(node_id: str | None):
    event = {
        "event_type": "CREATE_NODE",
        "timestamp": 1,
        "node_id": node_id,
        "payload": {"node_id": node_id, "attributes": {"name": "x"}} if node_id is not None else {},
        "event_id": "e1",
    }
    return dict_to_envelope(event)


async def _run_server(port_holder: list[int], graph: MockGraph, store: DummyStore):
    server = serve(DummyQE(), store, graph=graph, port=0)
    port = server.add_insecure_port("localhost:0")
    port_holder.append(port)
    await server.start()
    await server.wait_for_termination()


async def _run_success_test(port: int, graph: MockGraph, store: DummyStore):
    env = _build_envelope("n1")
    async with AsyncUMEClient(f"localhost:{port}") as client:
        await client.publish_event(env)
        ids = await client.search_vectors([1.0, 2.0], k=1)
        assert ids == ["x"]
    assert graph.node_exists("n1")
    assert store.queries == [([1.0, 2.0], 1)]


async def _run_error_test(port: int):
    env = _build_envelope(None)
    async with AsyncUMEClient(f"localhost:{port}") as client:
        with pytest.raises(grpc.aio.AioRpcError) as exc:
            await client.publish_event(env)
        assert exc.value.code() == grpc.StatusCode.INVALID_ARGUMENT


def test_publish_event():
    port_holder: list[int] = []
    graph = MockGraph()
    store = DummyStore()

    async def runner():
        server_task = asyncio.create_task(_run_server(port_holder, graph, store))
        while not port_holder:
            await asyncio.sleep(0.01)
        await _run_success_test(port_holder[0], graph, store)
        await _run_error_test(port_holder[0])
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    asyncio.run(runner())
