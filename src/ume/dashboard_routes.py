from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any, AsyncGenerator, Dict, List

from fastapi import APIRouter, Depends, Header, Query
from sse_starlette.sse import EventSourceResponse

from .audit import get_audit_entries
from .graph_adapter import IGraphAdapter
from .api_deps import get_current_role, get_graph, get_vector_store
from .event_ledger import event_ledger
from .realtime_contracts import DashboardDigestEvent, GraphDigestControlEvent
from .realtime_digest import to_graph_digest
from .vector_store import VectorStore
from .config import settings

router = APIRouter(prefix="/dashboard")


@router.get("/stats")
def dashboard_stats(
    _: str = Depends(get_current_role),
    graph: IGraphAdapter = Depends(get_graph),
    store: VectorStore = Depends(get_vector_store),
) -> Dict[str, Any]:
    node_count = len(graph.get_all_node_ids())
    edge_count = len(graph.get_all_edges())
    index_size = len(getattr(store, "idx_to_id", []))
    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "vector_index_size": index_size,
    }


@router.get("/recent_events")
def dashboard_recent_events(
    limit: int = 10,
    _: str = Depends(get_current_role),
) -> List[Dict[str, Any]]:
    entries = get_audit_entries()
    return list(reversed(entries[-limit:]))


@router.get("/transport_features")
def dashboard_transport_features(_: str = Depends(get_current_role)) -> Dict[str, Any]:
    return {
        "realtime_dashboard_stream": settings.UME_ENABLE_DASHBOARD_STREAM,
        "dashboard_stream_transport": settings.UME_DASHBOARD_STREAM_TRANSPORT,
        "rest_fallback_enabled": settings.UME_DASHBOARD_REST_FALLBACK,
    }


def _redaction_count() -> int:
    entries = get_audit_entries()
    return sum(1 for e in entries if "payload_redacted" in str(e.get("reason", "")))


def _dashboard_snapshot(cursor_offset: int) -> DashboardDigestEvent:
    node_count = len(get_graph().get_all_node_ids())
    edge_count = len(get_graph().get_all_edges())
    index_size = len(getattr(get_vector_store(), "idx_to_id", []))
    recent_batch = event_ledger.range(start=max(cursor_offset - 9, 0), end=cursor_offset, limit=10)
    recent_events = [to_graph_digest(offset, event) for offset, event in recent_batch]
    return DashboardDigestEvent(
        cursor_offset=cursor_offset,
        stats={
            "node_count": node_count,
            "edge_count": edge_count,
            "vector_index_size": index_size,
        },
        recent_events=recent_events,
        redacted_count=_redaction_count(),
    )


@router.get("/stream")
async def dashboard_stream(
    cursor: int | None = Query(None, ge=0, description="Start streaming from this ledger offset"),
    last_event_id: int | None = Query(None, ge=0, alias="lastEventId"),
    last_event_id_header: int | None = Header(None, alias="Last-Event-ID"),
    max_events: int | None = Query(None, ge=1, description="Optional cap for emitted digest events"),
    _: str = Depends(get_current_role),
) -> EventSourceResponse:
    queue: asyncio.Queue[dict[str, str]] = asyncio.Queue(maxsize=64)
    dropped_events = 0
    stop_event = asyncio.Event()

    resume_from = last_event_id_header if last_event_id_header is not None else last_event_id
    start_offset = max((cursor if cursor is not None else 0), (resume_from + 1) if resume_from is not None else 0)

    async def _producer() -> None:
        nonlocal dropped_events
        next_offset = start_offset
        emitted = 0
        heartbeat_interval_s = 5.0
        last_heartbeat = time.monotonic()

        while not stop_event.is_set():
            batch = event_ledger.range(start=next_offset, limit=100)
            if batch:
                for offset, _ in batch:
                    frame = {
                        "event": "dashboard_digest",
                        "id": str(offset),
                        "data": _dashboard_snapshot(offset).model_dump_json(),
                    }
                    if queue.full():
                        try:
                            queue.get_nowait()
                            dropped_events += 1
                        except asyncio.QueueEmpty:
                            pass
                    await queue.put(frame)
                    next_offset = offset + 1
                    emitted += 1
                    if max_events is not None and emitted >= max_events:
                        stop_event.set()
                        break
                if dropped_events > 0:
                    ctrl = GraphDigestControlEvent(
                        kind="backpressure",
                        cursor_offset=next_offset - 1,
                        dropped_events=dropped_events,
                    )
                    await queue.put({"event": "control", "data": ctrl.model_dump_json()})
                    dropped_events = 0
                last_heartbeat = time.monotonic()
            else:
                now = time.monotonic()
                if now - last_heartbeat >= heartbeat_interval_s:
                    heartbeat = GraphDigestControlEvent(
                        kind="heartbeat",
                        cursor_offset=max(next_offset - 1, -1),
                    )
                    await queue.put({"event": "control", "data": heartbeat.model_dump_json()})
                    last_heartbeat = now
                await asyncio.sleep(0.1)

    async def _gen() -> AsyncGenerator[dict[str, str], None]:
        producer_task = asyncio.create_task(_producer())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.2)
                except asyncio.TimeoutError:
                    if stop_event.is_set() and queue.empty():
                        break
                    continue
                yield event
                await asyncio.sleep(0)
                if stop_event.is_set() and queue.empty():
                    break
        finally:
            stop_event.set()
            producer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await producer_task

    return EventSourceResponse(_gen())
