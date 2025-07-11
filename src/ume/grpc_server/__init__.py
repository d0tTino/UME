"""gRPC server exposing core UME APIs."""
# mypy: ignore-errors

from __future__ import annotations

import typing
import asyncio

import grpc
from google.protobuf import struct_pb2, empty_pb2
from google.protobuf.json_format import MessageToDict

from ..query import Neo4jQueryEngine
from ..vector_store import VectorStore
from ..audit import get_audit_entries
from ..config import settings
from ..logging_utils import configure_logging
from ..event import EventError
from ..processing import ProcessingError
from ume.services.ingest import ingest_event
from ..async_graph_adapter import (
    IAsyncGraphAdapter,
    ingest_event_async,
)
import inspect

from ume_client import ume_pb2, ume_pb2_grpc  # type: ignore


class UMEServicer(ume_pb2_grpc.UMEServicer):
    """Implementation of the UME gRPC service."""

    def __init__(
        self,
        query_engine: Neo4jQueryEngine,
        store: VectorStore,
        graph: typing.Optional[typing.Any] = None,
        *,
        api_token: str | None = None,
        auth_callback: typing.Optional[typing.Callable[[str], bool]] = None,
    ) -> None:
        self.query_engine = query_engine
        self.store = store
        self.graph = graph
        self.api_token = api_token if api_token is not None else settings.UME_GRPC_TOKEN
        self.auth_callback = auth_callback

    async def _require_auth(self, context: grpc.aio.ServicerContext) -> None:
        if self.api_token is None and self.auth_callback is None:
            return
        metadata = {k.lower(): v for k, v in context.invocation_metadata()}
        header = metadata.get("authorization")
        if not header or not header.lower().startswith("bearer "):
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "Missing token")
            return
        token = header.split(" ", 1)[1]
        if self.api_token is not None:
            if token != self.api_token:
                await context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid token")
                return
            return
        if self.auth_callback is not None and not self.auth_callback(token):
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid token")
            return

    async def RunCypher(
        self, request: ume_pb2.CypherQuery, context: grpc.aio.ServicerContext
    ) -> ume_pb2.CypherResult:
        await self._require_auth(context)
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
        await self._require_auth(context)
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
        await self._require_auth(context)
        ids = self.store.query(list(request.vector), k=request.k or 5)
        return ume_pb2.VectorSearchResponse(ids=ids)

    async def GetAuditEntries(
        self, request: ume_pb2.AuditRequest, context: grpc.aio.ServicerContext
    ) -> ume_pb2.AuditResponse:
        await self._require_auth(context)
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

    async def PublishEvent(
        self, request: ume_pb2.PublishEventRequest, context: grpc.aio.ServicerContext
    ) -> empty_pb2.Empty:
        await self._require_auth(context)
        if self.graph is None:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "graph not configured")

        try:
            envelope = request.envelope
            if envelope.HasField("create_node"):
                meta = envelope.create_node.meta
            elif envelope.HasField("update_node_attributes"):
                meta = envelope.update_node_attributes.meta
            elif envelope.HasField("create_edge"):
                meta = envelope.create_edge.meta
            elif envelope.HasField("delete_edge"):
                meta = envelope.delete_edge.meta
            else:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Envelope missing payload")
                return empty_pb2.Empty()  # Unreachable but satisfies type checkers

            event_dict = {
                "event_id": meta.event_id,
                "event_type": meta.event_type,
                "timestamp": meta.timestamp,
                "payload": MessageToDict(meta.payload),
                "source": meta.source or None,
                "node_id": meta.node_id or None,
                "target_node_id": meta.target_node_id or None,
                "label": meta.label or None,
            }
            if isinstance(self.graph, IAsyncGraphAdapter) or inspect.iscoroutinefunction(getattr(self.graph, "add_node", None)):
                await ingest_event_async(event_dict, self.graph)  # type: ignore[arg-type]
            else:
                ingest_event(event_dict, self.graph)
        except (EventError, ProcessingError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

        return empty_pb2.Empty()


class AsyncServer:
    """Wrapper around :class:`grpc.aio.Server` with async context management."""

    def __init__(self, server: grpc.aio.Server) -> None:
        self.server = server

    def add_insecure_port(self, addr: str) -> int:
        return self.server.add_insecure_port(addr)

    def add_generic_rpc_handlers(self, handlers: typing.Any) -> None:
        self.server.add_generic_rpc_handlers(handlers)

    async def start(self) -> None:
        await self.server.start()

    async def wait_for_termination(self) -> None:
        await self.server.wait_for_termination()

    async def stop(self, grace: float | None = None) -> None:
        await self.server.stop(grace)

    async def __aenter__(self) -> "AsyncServer":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop(None)


def serve(
    query_engine: Neo4jQueryEngine,
    store: VectorStore,
    *,
    port: int = 50051,
    graph: typing.Optional[typing.Any] = None,
    api_token: str | None = None,
    auth_callback: typing.Optional[typing.Callable[[str], bool]] = None,
) -> AsyncServer:
    """Start the gRPC server and return a wrapper object."""
    server = grpc.aio.server()
    try:
        ume_pb2_grpc.add_UMEServicer_to_server(
            UMEServicer(
                query_engine,
                store,
                graph,
                api_token=api_token,
                auth_callback=auth_callback,
            ),
            server,
        )
    except AttributeError:  # pragma: no cover - support stub servers
        pass
    server.add_insecure_port(f"[::]:{port}")
    return AsyncServer(server)


async def main() -> None:
    """Run the gRPC server using default configuration."""
    configure_logging()
    qe = Neo4jQueryEngine.from_credentials(
        settings.NEO4J_URI, settings.NEO4J_USER, settings.NEO4J_PASSWORD
    )
    store = VectorStore(dim=settings.UME_VECTOR_DIM, use_gpu=settings.UME_VECTOR_USE_GPU)
    server = serve(
        qe,
        store,
        port=50051,
        api_token=settings.UME_GRPC_TOKEN,
    )
    await server.start()
    try:
        await server.wait_for_termination()
    except asyncio.CancelledError:
        await server.stop(None)
        raise


__all__ = ["UMEServicer", "AsyncServer", "serve", "main"]
