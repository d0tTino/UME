import asyncio
import os
import sys
from pathlib import Path

import grpc
import pytest

base = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(base / "src" / "ume_client"))
sys.path.insert(0, str(base / "src"))

# Ensure required configuration is present for importing ume.grpc_server
os.environ.setdefault("UME_AUDIT_SIGNING_KEY", "test-key")

from ume.grpc_server import serve  # noqa: E402
from ume_client.async_client import AsyncUMEClient  # noqa: E402
from ume.config import settings  # noqa: E402


class DummyQE:
    def execute_cypher(self, cypher: str):
        return []


class DummyStore:
    def query(self, vector, k=5):
        return []


async def _run_server(port_holder: list[int], token: str):
    server = serve(DummyQE(), DummyStore(), port=0, api_token=token)
    port_holder.append(server.add_insecure_port("localhost:0"))
    await server.start()
    try:
        await server.wait_for_termination()
    finally:
        await server.stop(None)


async def _run_tests(port: int):
    # Missing token
    async with AsyncUMEClient(f"localhost:{port}") as client:
        with pytest.raises(grpc.aio.AioRpcError) as exc:
            await client.run_cypher("RETURN 1")
        assert exc.value.code() == grpc.StatusCode.UNAUTHENTICATED

    # Incorrect token
    async with AsyncUMEClient(f"localhost:{port}", token="wrong") as client:
        with pytest.raises(grpc.aio.AioRpcError) as exc:
            await client.run_cypher("RETURN 1")
        assert exc.value.code() == grpc.StatusCode.UNAUTHENTICATED

    # Correct token
    async with AsyncUMEClient(f"localhost:{port}", token=settings.UME_GRPC_TOKEN) as client:
        res = await client.run_cypher("RETURN 1")
        assert res == []


def test_async_client_authentication():
    object.__setattr__(settings, "UME_GRPC_TOKEN", "secret")
    os.environ["UME_GRPC_TOKEN"] = "secret"

    ports: list[int] = []

    async def runner():
        server_task = asyncio.create_task(_run_server(ports, settings.UME_GRPC_TOKEN))
        while not ports:
            await asyncio.sleep(0.01)
        await _run_tests(ports[0])
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    asyncio.run(runner())
