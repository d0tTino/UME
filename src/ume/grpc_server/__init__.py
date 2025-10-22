"""gRPC server exposing core UME APIs."""
# mypy: ignore-errors

from __future__ import annotations

import typing
import asyncio
import math
import logging
import time

import grpc
from google.protobuf import struct_pb2, empty_pb2

from ..query import Neo4jQueryEngine
from ..vector_store import VectorStore
from ..audit import get_audit_entries
from ..config import settings
from ..logging_utils import configure_logging
from ..embedding import generate_embedding
from ..metrics import RECALL_SCORE, RECALL_LATENCY_MS
from ..event import EventError
from ..processing import ProcessingError
from ..permissions_adapter import PermissionsGraphAdapter
from ..snapshot import snapshot_graph_to_file, load_graph_into_existing
from ume.services.ingest import ingest_envelope
from ..async_graph_adapter import IAsyncGraphAdapter
from ..event_ledger import event_ledger
from ..rbac_adapter import AccessDeniedError
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

    async def _require_auth(
        self, context: grpc.aio.ServicerContext | None
    ) -> dict[str, str]:
        metadata: dict[str, str] = {}
        if context is not None:
            metadata = {k.lower(): v for k, v in context.invocation_metadata()}

        if self.api_token is None and self.auth_callback is None:
            return metadata
        if self.api_token == "":
            logging.getLogger(__name__).warning(
                "UME_GRPC_TOKEN is empty; rejecting unauthenticated requests"
            )
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid token")
            return metadata
        header = metadata.get("authorization")
        if not header or not header.lower().startswith("bearer "):
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "Missing token")
            return metadata
        token = header.split(" ", 1)[1]
        if self.api_token is not None:
            if token != self.api_token:
                await context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid token")
                return metadata
            return metadata
        if self.auth_callback is not None and not self.auth_callback(token):
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid token")
            return metadata

        return metadata

    async def _get_permissions_graph(
        self,
        metadata: dict[str, str],
        context: grpc.aio.ServicerContext | None,
    ) -> PermissionsGraphAdapter:
        if self.graph is None:
            raise RuntimeError("graph is not configured")

        def _first(keys: tuple[str, ...]) -> str | None:
            for key in keys:
                value = metadata.get(key)
                if value:
                    return value
            return None

        user_id = _first(("ume-user-id", "user-id", "x-ume-user-id"))
        group_id = _first(("ume-group-id", "group-id", "x-ume-group-id"))

        if user_id is None:
            message = "user_id metadata is required for permissions"
            if context is not None:
                await context.abort(grpc.StatusCode.PERMISSION_DENIED, message)
            raise RuntimeError(message)

        base_graph = self.graph
        if isinstance(base_graph, PermissionsGraphAdapter):
            base_graph = base_graph._adapter  # type: ignore[attr-defined]

        if isinstance(base_graph, IAsyncGraphAdapter) or inspect.iscoroutinefunction(
            getattr(base_graph, "get_node", None)
        ):
            if context is not None:
                await context.abort(
                    grpc.StatusCode.UNIMPLEMENTED,
                    "Async graphs are not supported for permission checks",
                )
            raise RuntimeError("Async graphs are not supported for permission checks")

        return PermissionsGraphAdapter(base_graph, user_id=user_id, group_id=group_id)

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

    async def Recall(
        self,
        request: ume_pb2.RecallRequest,
        context: grpc.aio.ServicerContext,
    ) -> ume_pb2.RecallResponse:
        metadata = await self._require_auth(context)

        if not request.query and not request.vector:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "query or vector required")

        vector = list(request.vector)
        if not vector and request.query:
            vector = generate_embedding(request.query)

        if len(vector) != self.store.dim:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid vector dimension")

        if self.graph is None:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "graph not configured")

        permissions_graph = await self._get_permissions_graph(metadata, context)

        start = time.perf_counter()
        ids = self.store.query(vector, k=request.k or 5)
        nodes = []
        for node_id in ids:
            attrs = permissions_graph.get_node(node_id)
            if attrs is not None:
                struct = struct_pb2.Struct()
                struct.update(attrs)
                emb = attrs.get("embedding")
                if isinstance(emb, list) and len(emb) == len(vector):
                    try:
                        RECALL_SCORE.observe(math.dist(vector, emb))
                    except TypeError:
                        pass
                nodes.append(ume_pb2.Node(id=node_id, attributes=struct))
        RECALL_LATENCY_MS.observe((time.perf_counter() - start) * 1000)
        return ume_pb2.RecallResponse(nodes=nodes)

    async def StreamRecall(
        self,
        request: ume_pb2.RecallRequest,
        context: grpc.aio.ServicerContext,
    ) -> typing.AsyncIterator[ume_pb2.Node]:
        metadata = await self._require_auth(context)

        if not request.query and not request.vector:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "query or vector required")

        vector = list(request.vector)
        if not vector and request.query:
            vector = generate_embedding(request.query)

        if len(vector) != self.store.dim:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid vector dimension")

        if self.graph is None:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "graph not configured")

        permissions_graph = await self._get_permissions_graph(metadata, context)

        start = time.perf_counter()
        ids = self.store.query(vector, k=request.k or 5)
        for node_id in ids:
            attrs = permissions_graph.get_node(node_id)
            if attrs is not None:
                struct = struct_pb2.Struct()
                struct.update(attrs)
                emb = attrs.get("embedding")
                if isinstance(emb, list) and len(emb) == len(vector):
                    try:
                        RECALL_SCORE.observe(math.dist(vector, emb))
                    except TypeError:
                        pass
                yield ume_pb2.Node(id=node_id, attributes=struct)
            await asyncio.sleep(0)
        RECALL_LATENCY_MS.observe((time.perf_counter() - start) * 1000)

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
        metadata = await self._require_auth(context)
        if self.graph is None:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "graph not configured")

        try:
            envelope = request.envelope
            permissions_graph = await self._get_permissions_graph(metadata, context)
            if isinstance(self.graph, IAsyncGraphAdapter) or inspect.iscoroutinefunction(
                getattr(self.graph, "add_node", None)
            ):
                await context.abort(
                    grpc.StatusCode.UNIMPLEMENTED,
                    "Async graphs are not supported for permission checks",
                )
            ingest_envelope(envelope, permissions_graph)
        except AccessDeniedError as exc:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(exc))
        except (EventError, ProcessingError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

        return empty_pb2.Empty()

    async def SaveSnapshot(
        self, request: ume_pb2.SnapshotPath, context: grpc.aio.ServicerContext
    ) -> empty_pb2.Empty:
        await self._require_auth(context)
        if self.graph is None:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "graph not configured")
        try:
            snapshot_graph_to_file(self.graph, request.path)
        except Exception as exc:  # pragma: no cover - unexpected errors
            await context.abort(grpc.StatusCode.INTERNAL, str(exc))
        return empty_pb2.Empty()

    async def LoadSnapshot(
        self, request: ume_pb2.SnapshotPath, context: grpc.aio.ServicerContext
    ) -> empty_pb2.Empty:
        await self._require_auth(context)
        if self.graph is None:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "graph not configured")
        try:
            load_graph_into_existing(self.graph, request.path)
        except FileNotFoundError:
            await context.abort(grpc.StatusCode.NOT_FOUND, "Snapshot not found")
        except Exception as exc:  # pragma: no cover - unexpected errors
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return empty_pb2.Empty()

    async def GetBookmark(
        self, request: empty_pb2.Empty, context: grpc.aio.ServicerContext
    ) -> ume_pb2.Bookmark:
        await self._require_auth(context)
        return ume_pb2.Bookmark(offset=event_ledger.last_processed_offset)

    async def SetBookmark(
        self, request: ume_pb2.Bookmark, context: grpc.aio.ServicerContext
    ) -> ume_pb2.Bookmark:
        await self._require_auth(context)
        try:
            event_ledger.update_bookmark(request.offset)
        except ValueError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return ume_pb2.Bookmark(offset=request.offset)


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
