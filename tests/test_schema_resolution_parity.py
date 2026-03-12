from __future__ import annotations

from ume.event_ledger import EventLedger
from ume.events.contract import canonicalize_event
from ume.events.legacy_transform import apply_legacy_transform
from ume.graph import MockGraph
from ume.replay import replay_from_ledger
from ume.services.event_processor import DEFAULT_EVENT_PROCESSOR


SCHEMA_VERSIONS = ("1.0.0", "2.0.0", "3.0.0")


def _create_node_event(node_id: str, version: str) -> dict[str, object]:
    return {
        "eventType": "CREATE_NODE",
        "timestamp": 1,
        "node_id": node_id,
        "schemaVersion": version,
        "payload": {
            "node_id": node_id,
            "attributes": {"type": "Document", "version": version},
        },
    }


def test_mixed_version_live_ingestion_uses_single_resolution_path() -> None:
    graph = MockGraph()

    for idx, schema_version in enumerate(SCHEMA_VERSIONS, start=1):
        payload = _create_node_event(f"live-{idx}", schema_version)
        envelope = DEFAULT_EVENT_PROCESSOR.mutate_graph(
            payload,
            graph=graph,
            source="graph_routes",
            adapter="default",
        )
        assert envelope.event is not None
        assert envelope.event.schema_version == schema_version



def test_mixed_version_replay_matches_live_ingestion_path(tmp_path) -> None:
    live_graph = MockGraph()
    replay_graph = MockGraph()
    ledger = EventLedger(str(tmp_path / "schema-parity.sqlite"))

    events = [_create_node_event(f"shared-{idx}", version) for idx, version in enumerate(SCHEMA_VERSIONS, start=1)]

    for offset, payload in enumerate(events):
        DEFAULT_EVENT_PROCESSOR.mutate_graph(
            payload,
            graph=live_graph,
            source="service_ingest",
            adapter="default",
        )
        ledger.append(offset, payload)

    replay_from_ledger(replay_graph, ledger)

    assert replay_graph.dump() == live_graph.dump()
    ledger.close()


def test_historical_events_are_normalized_once_then_replayed_uniformly(tmp_path) -> None:
    graph = MockGraph()
    replay_graph = MockGraph()
    ledger = EventLedger(str(tmp_path / "legacy-normalized.sqlite"))

    historical = {
        "schemaVersion": "1.0.0",
        "event": {
            "eventId": "evt-legacy-1",
            "eventType": "CREATE_NODE",
            "timestamp": 1,
            "sourceService": "legacy",
            "nodeId": "legacy-1",
            "payload": {"node_id": "legacy-1", "attributes": {"kind": "legacy"}},
        },
    }

    normalized_external = apply_legacy_transform(historical)
    canonical = canonicalize_event(normalized_external)

    DEFAULT_EVENT_PROCESSOR.mutate_graph(
        normalized_external,
        graph=graph,
        source="service_ingest",
        adapter="default",
    )
    ledger.append(0, normalized_external)
    replay_from_ledger(replay_graph, ledger)

    assert canonical["graph"]["node_id"] == "legacy-1"
    assert replay_graph.dump() == graph.dump()
    ledger.close()
