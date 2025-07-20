import asyncio
import pathlib
import json
import grpc
import pytest

from ume.snapshot import (
    snapshot_graph_to_file,
    load_graph_into_existing,
)
from ume.replay import build_graph_from_ledger, replay_from_ledger
from ume.event_ledger import EventLedger
from ume.persistent_graph import PersistentGraph
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


def test_grpc_bookmark_persistence(tmp_path: pathlib.Path, monkeypatch) -> None:
    path = str(tmp_path / "ledger.db")
    ledger = EventLedger(path)
    for i in range(3):
        ledger.append(
            i,
            {
                "event_type": "CREATE_NODE",
                "timestamp": i,
                "node_id": f"n{i}",
                "payload": {"node_id": f"n{i}"},
            },
        )
    monkeypatch.setattr("ume.grpc_server.event_ledger", ledger)

    async def _run_server(port_holder: list[int]) -> None:
        server = grpc.aio.server()
        svc = UMEServicer(DummyQE(), DummyStore())
        ume_pb2_grpc.add_UMEServicer_to_server(svc, server)
        port_holder.append(server.add_insecure_port("localhost:0"))
        await server.start()
        await server.wait_for_termination()

    async def _set_bookmark(port: int) -> None:
        async with AsyncUMEClient(f"localhost:{port}") as client:
            off = await client.set_bookmark(1)
            assert off == 1

    ports: list[int] = []

    async def runner() -> None:
        server_task = asyncio.create_task(_run_server(ports))
        while not ports:
            await asyncio.sleep(0.01)
        await _set_bookmark(ports[0])
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    asyncio.run(runner())

    ledger.close()
    ledger2 = EventLedger(path)
    monkeypatch.setattr("ume.grpc_server.event_ledger", ledger2)

    async def _run_server2(port_holder: list[int]) -> None:
        server = grpc.aio.server()
        svc = UMEServicer(DummyQE(), DummyStore())
        ume_pb2_grpc.add_UMEServicer_to_server(svc, server)
        port_holder.append(server.add_insecure_port("localhost:0"))
        await server.start()
        await server.wait_for_termination()

    async def _get_bookmark(port: int) -> None:
        async with AsyncUMEClient(f"localhost:{port}") as client:
            off = await client.get_bookmark()
            assert off == 1

    ports2: list[int] = []

    async def runner2() -> None:
        server_task = asyncio.create_task(_run_server2(ports2))
        while not ports2:
            await asyncio.sleep(0.01)
        await _get_bookmark(ports2[0])
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    asyncio.run(runner2())

    g = PersistentGraph(":memory:")
    replay_from_ledger(g, ledger2, start_offset=ledger2.last_processed_offset + 1)
    assert set(g.get_all_node_ids()) == {"n2"}

