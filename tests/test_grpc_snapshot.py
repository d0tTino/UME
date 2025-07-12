import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "ume_client"))

from ume_client.async_client import AsyncUMEClient  # noqa: E402
from ume.graph import MockGraph  # noqa: E402
from ume.grpc_server import serve  # noqa: E402


class DummyQE:
    def execute_cypher(self, cypher: str):
        return []


class DummyStore:
    pass


async def _run_server(graph: MockGraph, port_holder: list[int]):
    server = serve(DummyQE(), DummyStore(), graph=graph, port=0)
    port_holder.append(server.add_insecure_port("localhost:0"))
    await server.start()
    await server.wait_for_termination()


async def _run_roundtrip(port: int, tmp_path: Path, graph: MockGraph):
    path = tmp_path / "snap.json"
    async with AsyncUMEClient(f"localhost:{port}") as client:
        await client.save_snapshot(str(path))
        assert path.is_file()
        graph.clear()
        await client.load_snapshot(str(path))
        assert set(graph.get_all_node_ids()) == {"a", "b"}
        assert ("a", "b", "L") in graph.get_all_edges()


def test_grpc_snapshot_roundtrip(tmp_path: Path):
    graph = MockGraph()
    graph.add_node("a", {"x": 1})
    graph.add_node("b", {"y": 2})
    graph.add_edge("a", "b", "L")
    ports: list[int] = []

    async def runner():
        server_task = asyncio.create_task(_run_server(graph, ports))
        while not ports:
            await asyncio.sleep(0.01)
        await _run_roundtrip(ports[0], tmp_path, graph)
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    asyncio.run(runner())
