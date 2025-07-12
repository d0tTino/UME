import asyncio
import sys
from pathlib import Path
import grpc
import pytest

base = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(base / "src" / "ume_client"))

from ume_client import ume_pb2_grpc, ume_pb2  # noqa: E402
from ume_client.async_client import AsyncUMEClient  # noqa: E402

class DummyStore:
    def __init__(self) -> None:
        self.dim = 2
        self.queries: list[tuple[list[float], int]] = []

    def query(self, vector: list[float], k: int = 5) -> list[str]:
        self.queries.append((list(vector), k))
        return ["a"]

store = DummyStore()
GRAPH = {"a": {"val": 1}}

class RecallServicer(ume_pb2_grpc.UMEServicer):
    def __init__(self, graph: dict[str, dict[str, object]] | None = None) -> None:
        self.graph = graph

    async def Recall(self, request, context):
        if not request.query and not request.vector:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "query or vector required")

        vector = list(request.vector)
        if not vector and request.query:
            vector = [1.0, 0.0]
        if len(vector) != store.dim:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid vector dimension")

        if self.graph is None:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "graph not configured")

        ids = store.query(vector, k=request.k or 5)
        nodes = []
        for nid in ids:
            attrs = self.graph.get(nid) if self.graph else None
            if attrs is not None:
                struct = ume_pb2.google_dot_protobuf_dot_struct__pb2.Struct()
                struct.update(attrs)
                nodes.append(ume_pb2.Node(id=nid, attributes=struct))
        return ume_pb2.RecallResponse(nodes=nodes)

async def _run_server(port_holder: list[int]):
    server = grpc.aio.server()
    ume_pb2_grpc.add_UMEServicer_to_server(RecallServicer(GRAPH), server)
    port = server.add_insecure_port("localhost:0")
    port_holder.append(port)
    await server.start()
    await server.wait_for_termination()

async def _run_recall_test(port: int):
    store.queries.clear()
    async with AsyncUMEClient(f"localhost:{port}") as client:
        nodes = await client.recall(query="foo", k=1)
        assert nodes == [{"id": "a", "attributes": {"val": 1}}]
        assert store.queries == [([1.0, 0.0], 1)]

async def _run_bad_vector_test(port: int):
    async with AsyncUMEClient(f"localhost:{port}") as client:
        with pytest.raises(grpc.aio.AioRpcError) as exc:
            await client.recall(vector=[0.0])
        assert exc.value.code() == grpc.StatusCode.INVALID_ARGUMENT

async def _run_empty_request_test(port: int):
    async with AsyncUMEClient(f"localhost:{port}") as client:
        with pytest.raises(grpc.aio.AioRpcError) as exc:
            await client.recall()
        assert exc.value.code() == grpc.StatusCode.INVALID_ARGUMENT


async def _run_missing_graph_test():
    server = grpc.aio.server()
    ume_pb2_grpc.add_UMEServicer_to_server(RecallServicer(None), server)
    port = server.add_insecure_port("localhost:0")
    await server.start()
    try:
        async with AsyncUMEClient(f"localhost:{port}") as client:
            with pytest.raises(grpc.aio.AioRpcError) as exc:
                await client.recall(query="foo")
            assert exc.value.code() == grpc.StatusCode.FAILED_PRECONDITION
    finally:
        await server.stop(None)


def test_grpc_recall():
    port_holder: list[int] = []

    async def runner():
        server_task = asyncio.create_task(_run_server(port_holder))
        while not port_holder:
            await asyncio.sleep(0.01)
        await _run_recall_test(port_holder[0])
        await _run_bad_vector_test(port_holder[0])
        await _run_empty_request_test(port_holder[0])
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    asyncio.run(runner())
    asyncio.run(_run_missing_graph_test())

