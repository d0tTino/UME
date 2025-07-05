import asyncio
import sys
from pathlib import Path
import grpc
import pytest

base = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(base / "src" / "ume_client"))
sys.path.insert(0, str(base / "src"))

from ume_client import ume_pb2_grpc, ume_pb2  # noqa: E402
from ume_client.async_client import AsyncUMEClient  # noqa: E402


class DummyQE:
    def execute_cypher(self, cypher: str):
        return [{"n": 1}, {"n": 2}]


class DummyStore:
    def __init__(self):
        self.queries = []
        self.ids = ["x", "y"]

    def query(self, vector, k=5):
        self.queries.append((list(vector), k))
        return self.ids


store = DummyStore()

AUDIT_ENTRIES = [
    {"timestamp": 1, "user_id": "u1", "reason": "r1", "signature": "s1"},
    {"timestamp": 2, "user_id": "u2", "reason": "r2", "signature": "s2"},
]


class TestServicer(ume_pb2_grpc.UMEServicer):
    async def StreamCypher(self, request, context):
        for rec in DummyQE().execute_cypher(request.cypher):
            struct = ume_pb2.google_dot_protobuf_dot_struct__pb2.Struct()
            struct.update(rec)
            yield ume_pb2.CypherRecord(record=struct)  # type: ignore[attr-defined]

    async def SearchVectors(self, request, context):
        ids = store.query(list(request.vector), k=request.k or 5)
        return ume_pb2.VectorSearchResponse(ids=ids)

    async def GetAuditEntries(self, request, context):
        limit = request.limit or len(AUDIT_ENTRIES)
        selected = list(reversed(AUDIT_ENTRIES[-limit:]))
        return ume_pb2.AuditResponse(
            entries=[
                ume_pb2.AuditEntry(
                    timestamp=e["timestamp"],
                    user_id=e["user_id"],
                    reason=e["reason"],
                    signature=e["signature"],
                )
                for e in selected
            ]
        )


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


async def _run_search_test(port: int):
    store.queries.clear()
    async with AsyncUMEClient(f"localhost:{port}") as client:
        ids = await client.search_vectors([1.0, 2.0], k=2)
        assert ids == ["x", "y"]
        assert store.queries == [([1.0, 2.0], 2)]


async def _run_audit_test(port: int):
    async with AsyncUMEClient(f"localhost:{port}") as client:
        entries = await client.get_audit_entries(limit=1)
        assert entries == [AUDIT_ENTRIES[-1]]


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


def test_search_vectors_async():
    port_holder: list[int] = []

    async def runner():
        server_task = asyncio.create_task(_run_server(port_holder))
        while not port_holder:
            await asyncio.sleep(0.01)
        await _run_search_test(port_holder[0])
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    asyncio.run(runner())


def test_get_audit_entries_async():
    port_holder: list[int] = []

    async def runner():
        server_task = asyncio.create_task(_run_server(port_holder))
        while not port_holder:
            await asyncio.sleep(0.01)
        await _run_audit_test(port_holder[0])
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    asyncio.run(runner())


class ErrorServicer(TestServicer):
    async def StreamCypher(self, request, context):
        if not request.cypher:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "empty query")
        for rec in DummyQE().execute_cypher(request.cypher):
            struct = ume_pb2.google_dot_protobuf_dot_struct__pb2.Struct()
            struct.update(rec)
            yield ume_pb2.CypherRecord(record=struct)

    async def SearchVectors(self, request, context):
        if not request.vector:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "empty vector")
        ids = store.query(list(request.vector), k=request.k or 5)
        return ume_pb2.VectorSearchResponse(ids=ids)


async def _run_error_server(port_holder: list[int]):
    server = grpc.aio.server()
    svc = ErrorServicer()
    ume_pb2_grpc.add_UMEServicer_to_server(svc, server)
    port = server.add_insecure_port("localhost:0")
    port_holder.append(port)
    await server.start()
    await server.wait_for_termination()


async def _run_error_test(port: int):
    async with AsyncUMEClient(f"localhost:{port}") as client:
        with pytest.raises(grpc.aio.AioRpcError) as exc:
            async for _ in client.stream_cypher(""):
                pass
        assert exc.value.code() == grpc.StatusCode.INVALID_ARGUMENT


async def _run_malformed_search_test(port: int):
    async with AsyncUMEClient(f"localhost:{port}") as client:
        with pytest.raises(grpc.aio.AioRpcError) as exc:
            await client.search_vectors([])
        assert exc.value.code() == grpc.StatusCode.INVALID_ARGUMENT


def test_server_error_and_malformed_request():
    port_holder: list[int] = []

    async def runner():
        server_task = asyncio.create_task(_run_error_server(port_holder))
        while not port_holder:
            await asyncio.sleep(0.01)
        await _run_error_test(port_holder[0])
        await _run_malformed_search_test(port_holder[0])
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    asyncio.run(runner())


class CancelServicer(TestServicer):
    def __init__(self) -> None:
        super().__init__()
        self.cancelled = False

    async def StreamCypher(self, request, context):
        context.add_done_callback(lambda *_: setattr(self, "cancelled", True))
        for rec in DummyQE().execute_cypher(request.cypher):
            struct = ume_pb2.google_dot_protobuf_dot_struct__pb2.Struct()
            struct.update(rec)
            yield ume_pb2.CypherRecord(record=struct)
            await asyncio.sleep(0.01)
            if not context.is_active():
                self.cancelled = True
                return


async def _run_cancel_server(port_holder: list[int], svc_holder: list[CancelServicer]):
    server = grpc.aio.server()
    svc = CancelServicer()
    svc_holder.append(svc)
    ume_pb2_grpc.add_UMEServicer_to_server(svc, server)
    port = server.add_insecure_port("localhost:0")
    port_holder.append(port)
    await server.start()
    await server.wait_for_termination()


async def _run_cancel_test(port: int):
    async with AsyncUMEClient(f"localhost:{port}") as client:
        gen = client.stream_cypher("return 1")
        results = []
        async for rec in gen:
            results.append(rec)
            break
        await gen.aclose()
        assert results == [{"n": 1}]


def test_stream_cypher_client_cancel():
    port_holder: list[int] = []
    svc_holder: list[CancelServicer] = []

    async def runner():
        server_task = asyncio.create_task(_run_cancel_server(port_holder, svc_holder))
        while not port_holder:
            await asyncio.sleep(0.01)
        await _run_cancel_test(port_holder[0])
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    asyncio.run(runner())
    assert svc_holder[0].cancelled

