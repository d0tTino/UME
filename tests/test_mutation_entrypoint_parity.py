from __future__ import annotations

import pytest

pytest.importorskip("google.protobuf.json_format")

from ume.event import EventError
from ume.graph import MockGraph
from ume.pipeline.core import PipelineEnvelope
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


def _route_payload(adapter: str, event: dict[str, object]) -> dict[str, object]:
    if adapter == "grpc":
        return ingest_service.envelope_to_event_dict(ingest_service.dict_to_envelope(event))
    return event


def _process_for_graph(event: dict[str, object], *, source: str, adapter: str):
    graph = MockGraph()
    envelope = DEFAULT_EVENT_PROCESSOR.mutate_graph(
        _route_payload(adapter, event),
        graph=graph,
        source=source,
        adapter=adapter,
    )
    return envelope, graph.dump()


ROUTE_MATRIX: tuple[tuple[str, str], ...] = (
    ("cli_prompt", "cli"),
    ("kafka_graph_consumer", "kafka"),
    ("graph_routes", "default"),
    ("grpc_server", "grpc"),
)


def _assert_equivalent_outcomes(envelopes: list[PipelineEnvelope]) -> None:
    baseline = envelopes[0]
    for envelope in envelopes[1:]:
        assert envelope.outcome == baseline.outcome
        assert envelope.stage == baseline.stage
        assert envelope.reason == baseline.reason
        assert envelope.event_type == baseline.event_type


def test_mutation_routes_allow_parity_matrix() -> None:
    event = _base_event()

    outputs = [_process_for_graph(event, source=source, adapter=adapter) for source, adapter in ROUTE_MATRIX]

    envelopes = [output[0] for output in outputs]
    graph_dumps = [output[1] for output in outputs]
    _assert_equivalent_outcomes(envelopes)
    assert graph_dumps[1:] == [graph_dumps[0]] * (len(graph_dumps) - 1)


def test_mutation_routes_policy_deny_parity_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ume.policy.pipeline.consent_ledger.has_consent", lambda *_: False)
    event = _base_event()
    event["payload"] = {
        "user_id": "u1",
        "scope": "email",
        "attributes": {"name": "Alice"},
    }

    envelopes = [
        _process_for_graph(event, source=source, adapter=adapter)[0]
        for source, adapter in ROUTE_MATRIX
    ]

    _assert_equivalent_outcomes(envelopes)
    assert all(categorize_envelope_error(envelope) == MutationErrorCategory.POLICY_DENY for envelope in envelopes)

    with pytest.raises(EventError) as exc:
        ingest_service.ingest_event(event, MockGraph())
    assert str(exc.value).startswith("policy_deny:")


def test_mutation_routes_validation_parity_matrix() -> None:
    invalid_event = {"eventType": "CREATE_NODE", "payload": {"attributes": {"x": 1}}}

    envelopes = [
        _process_for_graph(invalid_event, source=source, adapter=adapter)[0]
        for source, adapter in ROUTE_MATRIX
    ]

    _assert_equivalent_outcomes(envelopes)
    assert all(categorize_envelope_error(envelope) == MutationErrorCategory.VALIDATION for envelope in envelopes)

    with pytest.raises(EventError) as exc:
        ingest_service.ingest_event(invalid_event, MockGraph())
    assert str(exc.value).startswith("validation:")
