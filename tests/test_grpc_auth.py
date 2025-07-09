import asyncio
import sys
from pathlib import Path

import grpc
import pytest

base = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(base / "src" / "ume_client"))
sys.path.insert(0, str(base / "src"))

from ume_client import ume_pb2_grpc, ume_pb2  # noqa: E402
from tests.test_grpc_service_unit import UMEServicer  # noqa: E402


class DummyQE:
    def execute_cypher(self, cypher: str):
        return []


class DummyStore:
    pass


async def _run_server(port_holder: list[int], svc_holder: list[UMEServicer]):
    server = grpc.aio.server()
    svc = UMEServicer(DummyQE(), DummyStore(), api_token="secret")
    svc_holder.append(svc)
    ume_pb2_grpc.add_UMEServicer_to_server(svc, server)
    port_holder.append(server.add_insecure_port("localhost:0"))
    await server.start()
    try:
        await server.wait_for_termination()
    finally:
        await server.stop(None)


async def _run_tests(port: int):
    channel = grpc.aio.insecure_channel(f"localhost:{port}")
    stub = ume_pb2_grpc.UMEStub(channel)
    with pytest.raises(grpc.aio.AioRpcError) as exc:
        await stub.RunCypher(ume_pb2.CypherQuery(cypher="RETURN 1"))
    assert exc.value.code() == grpc.StatusCode.UNAUTHENTICATED

    res = await stub.RunCypher(
        ume_pb2.CypherQuery(cypher="RETURN 1"),
        metadata=[("authorization", "Bearer secret")],
    )
    assert len(res.records) == 0
    await channel.close()


def test_grpc_authentication():
    ports: list[int] = []
    svcs: list[UMEServicer] = []

    async def runner():
        task = asyncio.create_task(_run_server(ports, svcs))
        while not ports:
            await asyncio.sleep(0.01)
        await _run_tests(ports[0])
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(runner())
