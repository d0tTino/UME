"""gRPC server exposing core UME APIs."""
# mypy: ignore-errors

from __future__ import annotations

import asyncio
import typing

import grpc
from google.protobuf import struct_pb2

from .query import Neo4jQueryEngine
from .vector_backends import VectorStore
from .audit import get_audit_entries
from .config import settings
from .logging_utils import configure_logging

from ume_client import ume_pb2, ume_pb2_grpc  # type: ignore


class UMEServicer(ume_pb2_grpc.UMEServicer):
    """Implementation of the UME gRPC service."""

    def __init__(self, query_engine: Neo4jQueryEngine, store: VectorStore) -> None:
        self.query_engine = query_engine
        self.store = store

    async def RunCypher(
        self, request: ume_pb2.CypherQuery, context: grpc.aio.ServicerContext
    ) -> ume_pb2.CypherResult:
        records = self.query_engine.execute_cypher(request.cypher)
        result = ume_pb2.CypherResult()
        for rec in records:
            struct = struct_pb2.Struct()
            struct.update(rec)
            result.records.append(struct)
        return result

    async def StreamCypher(
        self, request: ume_pb2.CypherQuery, context: grpc.aio.ServicerContext
    ) -> typing.AsyncIterator[ume_pb2.CypherRecord]:
        records = self.query_engine.execute_cypher(request.cypher)
        for rec in records:
            struct = struct_pb2.Struct()
            struct.update(rec)
            yield ume_pb2.CypherRecord(record=struct)

    async def SearchVectors(
        self,
        request: ume_pb2.VectorSearchRequest,
        context: grpc.aio.ServicerContext,
    ) -> ume_pb2.VectorSearchResponse:
        ids = self.store.query(list(request.vector), k=request.k or 5)
        return ume_pb2.VectorSearchResponse(ids=ids)

    async def GetAuditEntries(
        self, request: ume_pb2.AuditRequest, context: grpc.aio.ServicerContext
    ) -> ume_pb2.AuditResponse:
        entries = get_audit_entries()
        limit = request.limit or len(entries)
        selected = list(reversed(entries[-limit:]))
        return ume_pb2.AuditResponse(
            entries=[
                ume_pb2.AuditEntry(
                    timestamp=e.get("timestamp", 0),
                    user_id=str(e.get("user_id", "")),
                    reason=str(e.get("reason", "")),
                    signature=str(e.get("signature", "")),
                )
                for e in selected
            ]
        )


def serve(query_engine: Neo4jQueryEngine, store: VectorStore, *, port: int = 50051) -> grpc.aio.Server:
    """Start the gRPC server and return it."""
    server = grpc.aio.server()
    try:
        ume_pb2_grpc.add_UMEServicer_to_server(UMEServicer(query_engine, store), server)
    except AttributeError:  # pragma: no cover - support stub servers
        pass
    server.add_insecure_port(f"[::]:{port}")
    return server


async def main() -> None:
    configure_logging()
    qe = Neo4jQueryEngine.from_credentials(
        settings.NEO4J_URI, settings.NEO4J_USER, settings.NEO4J_PASSWORD
    )
    store = VectorStore(
        dim=settings.UME_VECTOR_DIM,
        use_gpu=settings.UME_VECTOR_USE_GPU,
    )
    server = serve(qe, store, port=50051)
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(main())
