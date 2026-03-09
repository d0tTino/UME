from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass

from .event import Event
from .event_ledger import EventLedger
from .metrics import (
    VECTOR_OUTBOX_DELIVERY_ERRORS_TOTAL,
    VECTOR_OUTBOX_DELIVERY_LATENCY_SECONDS,
    VECTOR_OUTBOX_DELIVERED_TOTAL,
    VECTOR_OUTBOX_LAG_SECONDS,
    VECTOR_OUTBOX_PENDING,
)
from .vector_store import VectorBackend


@dataclass(frozen=True)
class VectorOutboxRecord:
    id: int
    ledger_offset: int | None
    event_id: str
    node_id: str
    embedding: list[float]
    idempotency_key: str
    attempts: int
    available_at: float


def _extract_vector_write(event: Event) -> tuple[str, list[float]] | None:
    if event.event_type not in {"CREATE_NODE", "UPDATE_NODE_ATTRIBUTES"}:
        return None
    payload = event.payload
    node_id = event.node_id or payload.get("node_id")
    attrs = payload.get("attributes")
    if not isinstance(node_id, str) or not isinstance(attrs, dict):
        return None
    emb = attrs.get("embedding")
    if not isinstance(emb, list):
        return None
    vector: list[float] = []
    for val in emb:
        if not isinstance(val, (float, int)):
            return None
        vector.append(float(val))
    return node_id, vector


class VectorOutboxDispatcher:
    def __init__(
        self,
        ledger: EventLedger,
        store: VectorBackend,
        *,
        poll_interval_seconds: float = 0.25,
        max_batch_size: int = 100,
    ) -> None:
        self._ledger = ledger
        self._store = store
        self._poll_interval_seconds = poll_interval_seconds
        self._max_batch_size = max_batch_size
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            processed = self.process_available()
            if processed == 0:
                self._stop_event.wait(self._poll_interval_seconds)

    def process_available(self) -> int:
        now = time.time()
        records = self._ledger.get_pending_vector_outbox(limit=self._max_batch_size, now_ts=now)
        if not records:
            self._refresh_metrics(now)
            return 0
        for record in records:
            self._deliver(record, now)
        self._refresh_metrics(time.time())
        return len(records)

    def _deliver(self, record: VectorOutboxRecord, now: float) -> None:
        try:
            self._store.add(record.node_id, record.embedding)
        except Exception as exc:
            self._ledger.fail_vector_outbox_delivery(
                record_id=record.id,
                error=str(exc),
                now_ts=now,
            )
            VECTOR_OUTBOX_DELIVERY_ERRORS_TOTAL.inc()
            return
        self._ledger.mark_vector_outbox_delivered(record.id, delivered_at=now)
        created = self._ledger.vector_outbox_created_at(record.id)
        if created is not None:
            VECTOR_OUTBOX_DELIVERY_LATENCY_SECONDS.observe(max(now - created, 0.0))
        VECTOR_OUTBOX_DELIVERED_TOTAL.inc()

    def _refresh_metrics(self, now: float) -> None:
        pending = self._ledger.vector_outbox_pending_count(now_ts=now)
        VECTOR_OUTBOX_PENDING.set(float(pending))
        lag = self._ledger.vector_outbox_max_lag_seconds(now_ts=now)
        VECTOR_OUTBOX_LAG_SECONDS.set(lag)


def enqueue_vector_outbox_event(
    ledger: EventLedger,
    event: Event,
    *,
    ledger_offset: int | None,
) -> bool:
    extracted = _extract_vector_write(event)
    if extracted is None:
        return False
    node_id, embedding = extracted
    unique_key = f"{event.event_id}:{node_id}"
    if not event.event_id:
        unique_key = str(uuid.uuid4())
    ledger.enqueue_vector_outbox(
        ledger_offset=ledger_offset,
        event_id=event.event_id,
        node_id=node_id,
        embedding=embedding,
        idempotency_key=unique_key,
    )
    return True


def replay_vector_index_from_ledger_outbox(
    ledger: EventLedger,
    store: VectorBackend,
    *,
    end_offset: int | None = None,
) -> int:
    """Deterministically rebuild vector index by reprocessing delivered outbox records."""
    count = 0
    for record in ledger.iter_vector_outbox_for_replay(end_offset=end_offset):
        store.add(record.node_id, record.embedding)
        count += 1
    return count
