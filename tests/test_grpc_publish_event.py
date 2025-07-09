import asyncio
import sys
import importlib.util
from pathlib import Path

import grpc
import pytest

base = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(base / "src" / "ume_client"))
sys.path.insert(0, str(base / "src"))

from ume_client import ume_pb2_grpc  # noqa: E402
from ume_client.async_client import AsyncUMEClient  # noqa: E402
from ume.graph import MockGraph  # noqa: E402
from tests.test_grpc_service_unit import UMEServicer  # noqa: E402
spec_ev = importlib.util.spec_from_file_location("events_pb2", base / "src" / "ume_client" / "events_pb2.py")
assert spec_ev and spec_ev.loader
events_pb2 = importlib.util.module_from_spec(spec_ev)
spec_ev.loader.exec_module(events_pb2)
sys.modules["events_pb2"] = events_pb2


class DummyQE:
    def execute_cypher(self, cypher: str):
        return []


class DummyStore:
    pass


def _build_envelope(node_id: str | None):
    payload = events_pb2.google_dot_protobuf_dot_struct__pb2.Struct()
    if node_id is not None:
        payload.update({"node_id": node_id, "attributes": {"name": "x"}})
    base_evt = events_pb2.BaseEvent(
        event_id="e1",
        event_type="CREATE_NODE",
        timestamp=1,
        node_id=node_id or "",
        payload=payload,
    )
    return events_pb2.EventEnvelope(create_node=events_pb2.CreateNode(meta=base_evt))


async def _run_server(port_holder: list[int], svc_holder: list[UMEServicer]):
    server = grpc.aio.server()
    svc = UMEServicer(DummyQE(), DummyStore(), MockGraph())
    svc_holder.append(svc)
    ume_pb2_grpc.add_UMEServicer_to_server(svc, server)
    port = server.add_insecure_port("localhost:0")
    port_holder.append(port)
    await server.start()
    await server.wait_for_termination()


async def _run_success_test(port: int, svc: UMEServicer):
    env = _build_envelope("n1")
    async with AsyncUMEClient(f"localhost:{port}") as client:
        await client.publish_event(env)
    assert svc.graph.node_exists("n1")


async def _run_error_test(port: int):
    env = _build_envelope(None)
    async with AsyncUMEClient(f"localhost:{port}") as client:
        with pytest.raises(grpc.aio.AioRpcError) as exc:
            await client.publish_event(env)
        assert exc.value.code() == grpc.StatusCode.INVALID_ARGUMENT


def test_publish_event():
    port_holder: list[int] = []
    svc_holder: list[UMEServicer] = []

    async def runner():
        server_task = asyncio.create_task(_run_server(port_holder, svc_holder))
        while not port_holder:
            await asyncio.sleep(0.01)
        await _run_success_test(port_holder[0], svc_holder[0])
        await _run_error_test(port_holder[0])
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    asyncio.run(runner())
