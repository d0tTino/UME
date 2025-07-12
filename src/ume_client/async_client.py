"""Async helper client for the UME gRPC service."""

from __future__ import annotations

import grpc

from . import ume_pb2, ume_pb2_grpc, events_pb2


class AsyncUMEClient:
    """Convenience wrapper around the generated gRPC stub."""

    def __init__(self, target: str, token: str | None = None) -> None:
        self._channel = grpc.aio.insecure_channel(target)
        self._stub = ume_pb2_grpc.UMEStub(self._channel)
        self._metadata: tuple[tuple[str, str], ...] | None = (
            (("authorization", f"Bearer {token}"),)
        ) if token is not None else None

    async def run_cypher(self, cypher: str):
        request = ume_pb2.CypherQuery(cypher=cypher)
        response = await self._stub.RunCypher(request, metadata=self._metadata)
        return [dict(r) for r in response.records]

    async def stream_cypher(self, cypher: str):
        request = ume_pb2.CypherQuery(cypher=cypher)
        async for rec in self._stub.StreamCypher(request, metadata=self._metadata):
            yield dict(rec.record)

    async def search_vectors(self, vector: list[float], k: int = 5):
        request = ume_pb2.VectorSearchRequest(vector=vector, k=k)
        response = await self._stub.SearchVectors(request, metadata=self._metadata)
        return list(response.ids)

    async def recall(
        self,
        *,
        query: str | None = None,
        vector: list[float] | None = None,
        k: int = 5,
    ) -> list[dict[str, object]]:
        request = ume_pb2.RecallRequest(query=query or "", vector=vector or [], k=k)
        response = await self._stub.Recall(request, metadata=self._metadata)
        return [
            {"id": n.id, "attributes": dict(n.attributes)} for n in response.nodes
        ]

    async def get_audit_entries(self, limit: int = 10):
        request = ume_pb2.AuditRequest(limit=limit)
        response = await self._stub.GetAuditEntries(request, metadata=self._metadata)
        return [
            {
                "timestamp": e.timestamp,
                "user_id": e.user_id,
                "reason": e.reason,
                "signature": e.signature,
            }
            for e in response.entries
        ]

    async def publish_event(self, envelope: events_pb2.EventEnvelope) -> None:
        request = ume_pb2.PublishEventRequest(envelope=envelope)
        await self._stub.PublishEvent(request, metadata=self._metadata)

    async def close(self) -> None:
        await self._channel.close()

    async def __aenter__(self) -> "AsyncUMEClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()
