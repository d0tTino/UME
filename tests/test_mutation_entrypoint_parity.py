from __future__ import annotations

import pytest

pytest.importorskip("google.protobuf.json_format")

from ume.event import EventError
from ume.graph import MockGraph
from ume.services.event_processor import DEFAULT_EVENT_PROCESSOR
import ume.services.ingest as ingest_service
from ume.services.mutate import MutationErrorCategory, categorize_envelope_error


def _base_event() -> dict[str, object]:
    return {
        "eventType": "CREATE_NODE",
        "timestamp": 1,
        "nodeId": "n1",
        "payload": {"attributes": {"name": "Alice"}},
    }


def _process_for_graph(event: dict[str, object], *, source: str, adapter: str):
    graph = MockGraph()
    envelope = DEFAULT_EVENT_PROCESSOR.mutate_graph(
        event,
        graph=graph,
        source=source,
        adapter=adapter,
    )
    return envelope, graph.dump()


def test_cli_kafka_grpc_allow_parity() -> None:
    event = _base_event()

    cli_envelope, cli_dump = _process_for_graph(event, source="cli_prompt", adapter="cli")
    kafka_envelope, kafka_dump = _process_for_graph(
        event,
        source="kafka_graph_consumer",
        adapter="kafka",
    )

    grpc_envelope, grpc_dump = _process_for_graph(
        ingest_service.envelope_to_event_dict(ingest_service.dict_to_envelope(event)),
        source="grpc_server",
        adapter="grpc",
    )

    assert cli_envelope.outcome.value == kafka_envelope.outcome.value == grpc_envelope.outcome.value
    assert cli_dump == kafka_dump == grpc_dump


def test_cli_kafka_grpc_policy_deny_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ume.policy.pipeline.consent_ledger.has_consent", lambda *_: False)
    event = _base_event()
    event["payload"] = {
        "user_id": "u1",
        "scope": "email",
        "attributes": {"name": "Alice"},
    }

    cli_envelope, _ = _process_for_graph(event, source="cli_prompt", adapter="cli")
    kafka_envelope, _ = _process_for_graph(event, source="kafka_graph_consumer", adapter="kafka")
    grpc_envelope, _ = _process_for_graph(
        ingest_service.envelope_to_event_dict(ingest_service.dict_to_envelope(event)),
        source="grpc_server",
        adapter="grpc",
    )

    assert categorize_envelope_error(cli_envelope) == MutationErrorCategory.POLICY_DENY
    assert categorize_envelope_error(kafka_envelope) == MutationErrorCategory.POLICY_DENY
    assert categorize_envelope_error(grpc_envelope) == MutationErrorCategory.POLICY_DENY

    with pytest.raises(EventError) as exc:
        ingest_service.ingest_event(event, MockGraph())
    assert str(exc.value).startswith("policy_deny:")


def test_cli_kafka_grpc_validation_parity() -> None:
    invalid_event = {"eventType": "CREATE_NODE", "payload": {"attributes": {"x": 1}}}

    cli_envelope, _ = _process_for_graph(invalid_event, source="cli_prompt", adapter="cli")
    kafka_envelope, _ = _process_for_graph(
        invalid_event,
        source="kafka_graph_consumer",
        adapter="kafka",
    )
    grpc_envelope, _ = _process_for_graph(
        invalid_event,
        source="grpc_server",
        adapter="grpc",
    )

    assert categorize_envelope_error(cli_envelope) == MutationErrorCategory.VALIDATION
    assert categorize_envelope_error(kafka_envelope) == MutationErrorCategory.VALIDATION
    assert categorize_envelope_error(grpc_envelope) == MutationErrorCategory.VALIDATION

    with pytest.raises(EventError) as exc:
        ingest_service.ingest_event(invalid_event, MockGraph())
    assert str(exc.value).startswith("validation:")
