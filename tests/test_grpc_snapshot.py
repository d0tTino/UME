import asyncio
import pathlib
import json
import grpc
import pytest

from ume.snapshot import (
    snapshot_graph_to_file,
    load_graph_into_existing,
)
from ume.replay import build_graph_from_ledger
from ume.event_ledger import EventLedger
from ume.graph import MockGraph
from ume.grpc_server import UMEServicer
from ume_client import ume_pb2_grpc
from ume_client.async_client import AsyncUMEClient


class DummyQE:
    def execute_cypher(self, cypher: str) -> list[dict[str, object]]:
        return []


class DummyStore:
    dim = 1

    def query(self, vector: list[float], k: int = 5) -> list[str]:  # pragma: no cover - stub
        return []


def test_snapshot_roundtrip(tmp_path: pathlib.Path) -> None:
    graph = MockGraph()
    graph.add_node("a", {"val": 1})
    path = tmp_path / "snap.json"
    snapshot_graph_to_file(graph, path)
    assert path.is_file()
    graph.clear()
    load_graph_into_existing(graph, path)
    assert graph.get_node("a") == {"val": 1}


def test_load_corrupted_snapshot(tmp_path: pathlib.Path) -> None:
    graph = MockGraph()
    path = tmp_path / "bad.json"
    # Missing closing brace results in JSON error
    path.write_text('{"nodes": {"a": {}}')
    with pytest.raises(json.JSONDecodeError):
        load_graph_into_existing(graph, path)


def test_build_graph_from_ledger_partial(tmp_path: pathlib.Path) -> None:
    ledger = EventLedger(str(tmp_path / "ledger.db"))
    ledger.append(
        0,
        {
            "event_type": "CREATE_NODE",
            "timestamp": 1,
            "node_id": "a",
            "payload": {"node_id": "a"},
        },
    )
    ledger.append(
        1,
        {
            "event_type": "CREATE_NODE",
            "timestamp": 2,
            "node_id": "b",
            "payload": {"node_id": "b"},
        },
    )
    graph = build_graph_from_ledger(ledger, end_offset=0)
    assert set(graph.get_all_node_ids()) == {"a"}


def test_grpc_loadsnapshot_errors(tmp_path: pathlib.Path) -> None:
    ports: list[int] = []
    graph = MockGraph()

    async def _run_server() -> None:
        server = grpc.aio.server()
        svc = UMEServicer(DummyQE(), DummyStore(), graph)
        ume_pb2_grpc.add_UMEServicer_to_server(svc, server)
        ports.append(server.add_insecure_port("localhost:0"))
        await server.start()
        await server.wait_for_termination()

    async def _run_tests(port: int) -> None:
        async with AsyncUMEClient(f"localhost:{port}") as client:
            with pytest.raises(grpc.aio.AioRpcError) as exc:
                await client.load_snapshot(str(tmp_path / "missing.json"))
            assert exc.value.code() == grpc.StatusCode.NOT_FOUND

            bad = tmp_path / "bad.json"
            bad.write_text("{")
            with pytest.raises(grpc.aio.AioRpcError) as exc:
                await client.load_snapshot(str(bad))
            assert exc.value.code() == grpc.StatusCode.INVALID_ARGUMENT

    async def runner() -> None:
        server_task = asyncio.create_task(_run_server())
        while not ports:
            await asyncio.sleep(0.01)
        await _run_tests(ports[0])
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    asyncio.run(runner())

