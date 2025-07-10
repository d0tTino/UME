import asyncio
import sys
from pathlib import Path

import grpc
from fastapi.testclient import TestClient

# Make generated gRPC client importable
base = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(base / "src" / "ume_client"))  # noqa: E402

from google.protobuf import struct_pb2  # noqa: E402
from ume.api import app, configure_graph  # noqa: E402
from ume.config import settings  # noqa: E402
from ume.graph import MockGraph  # noqa: E402
from ume.grpc_server import UMEServicer  # noqa: E402
from ume_client import events_pb2, ume_pb2_grpc  # type: ignore  # noqa: E402
from ume_client.async_client import AsyncUMEClient  # type: ignore  # noqa: E402


def _token(client: TestClient) -> str:
    res = client.post(
        "/auth/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    )
    return res.json()["access_token"]


def _dict_to_envelope(data: dict[str, object]) -> events_pb2.EventEnvelope:
    from ume.services.ingest import validate_event
    evt = validate_event(data)
    struct_payload = struct_pb2.Struct()
    struct_payload.update(evt.payload)
    meta = events_pb2.BaseEvent(
        event_id=evt.event_id,
        event_type=evt.event_type,
        timestamp=evt.timestamp,
        source=evt.source or "",
        node_id=evt.node_id or "",
        target_node_id=evt.target_node_id or "",
        label=evt.label or "",
        payload=struct_payload,
    )
    if evt.event_type == "CREATE_NODE":
        return events_pb2.EventEnvelope(create_node=events_pb2.CreateNode(meta=meta))
    if evt.event_type == "UPDATE_NODE_ATTRIBUTES":
        return events_pb2.EventEnvelope(update_node_attributes=events_pb2.UpdateNodeAttributes(meta=meta))
    if evt.event_type == "CREATE_EDGE":
        return events_pb2.EventEnvelope(create_edge=events_pb2.CreateEdge(meta=meta))
    if evt.event_type == "DELETE_EDGE":
        return events_pb2.EventEnvelope(delete_edge=events_pb2.DeleteEdge(meta=meta))
    raise ValueError(evt.event_type)


class DummyQE:
    def execute_cypher(self, cypher: str):
        return []


class DummyStore:
    pass


async def _run_server(port_holder: list[int], graph: MockGraph):
    server = grpc.aio.server()
    svc = UMEServicer(DummyQE(), DummyStore(), graph)
    ume_pb2_grpc.add_UMEServicer_to_server(svc, server)
    port_holder.append(server.add_insecure_port("localhost:0"))
    await server.start()
    try:
        await server.wait_for_termination()
    finally:
        await server.stop(None)


def test_http_vs_grpc_ingest_consistency():
    if not hasattr(settings, "UME_GRPC_TOKEN"):
        object.__setattr__(settings, "UME_GRPC_TOKEN", None)
    events = [
        {
            "event_type": "CREATE_NODE",
            "timestamp": 1,
            "node_id": "n1",
            "payload": {"node_id": "n1", "attributes": {"name": "Alice"}},
        },
        {
            "event_type": "UPDATE_NODE_ATTRIBUTES",
            "timestamp": 2,
            "node_id": "n1",
            "payload": {"node_id": "n1", "attributes": {"age": 30}},
        },
        {
            "event_type": "CREATE_NODE",
            "timestamp": 3,
            "node_id": "n2",
            "payload": {"node_id": "n2", "attributes": {"name": "Bob"}},
        },
        {
            "event_type": "CREATE_EDGE",
            "timestamp": 4,
            "node_id": "n1",
            "target_node_id": "n2",
            "label": "ASSOCIATED_WITH",
            "payload": {},
        },
    ]

    # HTTP ingestion
    graph_http = MockGraph()
    configure_graph(graph_http)
    client = TestClient(app)
    token = _token(client)
    res = client.post("/events/batch", json=events, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    state_http = graph_http.dump()

    # gRPC ingestion
    graph_grpc = MockGraph()
    ports: list[int] = []

    async def runner():
        server_task = asyncio.create_task(_run_server(ports, graph_grpc))
        while not ports:
            await asyncio.sleep(0.01)
        async with AsyncUMEClient(f"localhost:{ports[0]}") as client:
            for evt in events:
                await client.publish_event(_dict_to_envelope(evt))
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    asyncio.run(runner())
    state_grpc = graph_grpc.dump()

    assert state_http == state_grpc
