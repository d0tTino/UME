from __future__ import annotations

import time

from ume.event_ledger import EventLedger
from ume.graph import MockGraph
from ume.services import mutate
from ume.event import Event
from ume.vector_outbox import VectorOutboxDispatcher, replay_vector_index_from_ledger_outbox


class _FlakyStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[float]]] = []
        self._fail_once = True

    def add(self, item_id: str, vector: list[float], *, persist: bool = False) -> None:
        self.calls.append((item_id, list(vector)))
        if self._fail_once:
            self._fail_once = False
            raise RuntimeError("inject-vector-write-failure")


class _RecordingStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[float]]] = []

    def add(self, item_id: str, vector: list[float], *, persist: bool = False) -> None:
        self.calls.append((item_id, list(vector)))


def test_outbox_record_created_after_successful_graph_mutation(monkeypatch, tmp_path) -> None:
    ledger = EventLedger(str(tmp_path / "ledger.db"))
    graph = MockGraph()
    monkeypatch.setattr(mutate, "event_ledger", ledger)

    projector = mutate.build_graph_projector(graph, classify=False)
    event = Event(
        event_type="CREATE_NODE",
        timestamp=1700000000,
        payload={"node_id": "n1", "attributes": {"embedding": [0.1, 0.2], "name": "alpha"}},
        event_id="evt-graph-1",
        node_id="n1",
        schema_version="1.0.0",
    )

    class _Ctx:
        canonical_event = {"metadata": {"schema_version": "1.0.0"}}
        effective_event = event
        details: dict[str, object] = {}

    projector(_Ctx())

    pending = ledger.get_pending_vector_outbox(limit=10, now_ts=time.time())
    assert len(pending) == 1
    assert pending[0].node_id == "n1"
    assert pending[0].embedding == [0.1, 0.2]
    ledger.close()


def test_outbox_retry_and_idempotency_with_failure_injection(tmp_path, monkeypatch) -> None:
    ledger = EventLedger(str(tmp_path / "ledger.db"))
    ledger.enqueue_vector_outbox(
        ledger_offset=10,
        event_id="evt-1",
        node_id="n1",
        embedding=[1.0, 2.0],
        idempotency_key="evt-1:n1",
        created_at=100.0,
    )
    # duplicate key must not create a second record
    ledger.enqueue_vector_outbox(
        ledger_offset=10,
        event_id="evt-1",
        node_id="n1",
        embedding=[1.0, 2.0],
        idempotency_key="evt-1:n1",
        created_at=100.0,
    )

    store = _FlakyStore()
    dispatcher = VectorOutboxDispatcher(ledger, store)

    monkeypatch.setattr("ume.vector_outbox.time.time", lambda: 101.0)
    assert dispatcher.process_available() == 1

    records = ledger.get_pending_vector_outbox(limit=10, now_ts=101.0)
    assert records == []

    monkeypatch.setattr("ume.vector_outbox.time.time", lambda: 200.0)
    assert dispatcher.process_available() == 1

    assert len(store.calls) == 2
    replayable = ledger.iter_vector_outbox_for_replay()
    assert len(replayable) == 1
    assert replayable[0].attempts == 1
    ledger.close()


def test_replay_vector_index_from_ledger_outbox_is_deterministic(tmp_path) -> None:
    ledger = EventLedger(str(tmp_path / "ledger.db"))
    ledger.enqueue_vector_outbox(
        ledger_offset=1,
        event_id="evt-1",
        node_id="n1",
        embedding=[1.0, 0.0],
        idempotency_key="evt-1:n1",
        created_at=1.0,
    )
    ledger.enqueue_vector_outbox(
        ledger_offset=2,
        event_id="evt-2",
        node_id="n2",
        embedding=[0.0, 1.0],
        idempotency_key="evt-2:n2",
        created_at=2.0,
    )
    ledger.mark_vector_outbox_delivered(1, delivered_at=3.0)
    ledger.mark_vector_outbox_delivered(2, delivered_at=4.0)

    store = _RecordingStore()
    count = replay_vector_index_from_ledger_outbox(ledger, store)

    assert count == 2
    assert store.calls == [("n1", [1.0, 0.0]), ("n2", [0.0, 1.0])]
    ledger.close()
