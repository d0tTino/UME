import asyncio
import sys
from pathlib import Path
import grpc

base = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(base / "src" / "ume_client"))
sys.path.insert(0, str(base / "src"))

from ume_client import ume_pb2_grpc, ume_pb2  # noqa: E402
from ume_client.async_client import AsyncUMEClient  # noqa: E402


class DummyQE:
    def execute_cypher(self, cypher: str):
        return [{"n": 1}, {"n": 2}]


class DummyStore:
    def query(self, vector, k=5):
        return []


class TestServicer(ume_pb2_grpc.UMEServicer):
    async def StreamCypher(self, request, context):
        for rec in DummyQE().execute_cypher(request.cypher):
            struct = ume_pb2.google_dot_protobuf_dot_struct__pb2.Struct()
            struct.update(rec)
            yield ume_pb2.CypherRecord(record=struct)  # type: ignore[attr-defined]


async def _run_server(port_holder: list[int]):
    server = grpc.aio.server()
    ume_pb2_grpc.add_UMEServicer_to_server(TestServicer(), server)
    port = server.add_insecure_port("localhost:0")
    port_holder.append(port)
    await server.start()
    await server.wait_for_termination()


async def _run_test(port: int):
    async with AsyncUMEClient(f"localhost:{port}") as client:
        results = []
        async for rec in client.stream_cypher("return 1"):
            results.append(rec)
        assert results == [{"n": 1}, {"n": 2}]


def test_stream_cypher():
    port_holder: list[int] = []

    async def runner():
        server_task = asyncio.create_task(_run_server(port_holder))
        while not port_holder:
            await asyncio.sleep(0.01)
        await _run_test(port_holder[0])
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    asyncio.run(runner())

