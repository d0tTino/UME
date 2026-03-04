from __future__ import annotations

import pytest

pytest.importorskip("google.protobuf.json_format")

from ume.event import EventError
from ume.graph import MockGraph
import ume.services.ingest as ingest_service
from ume.services.mutate import (
    MutationErrorCategory,
    build_graph_projector,
    categorize_envelope_error,
    run_mutation,
)


def _base_event() -> dict[str, object]:
    return {
        "eventType": "CREATE_NODE",
        "timestamp": 1,
        "nodeId": "n1",
        "payload": {"attributes": {"name": "Alice"}},
    }


def test_cli_kafka_allow_parity() -> None:
    cli_graph = MockGraph()
    kafka_graph = MockGraph()
    event = _base_event()

    cli_envelope = run_mutation(
        event,
        source="cli_prompt",
        adapter="cli",
        projector=build_graph_projector(cli_graph, classify=False),
    )
    kafka_envelope = run_mutation(
        event,
        source="kafka_graph_consumer",
        adapter="kafka",
        projector=build_graph_projector(kafka_graph, classify=False),
    )

    assert cli_envelope.outcome.value == kafka_envelope.outcome.value
    assert cli_graph.dump() == kafka_graph.dump()


def test_cli_kafka_api_policy_deny_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ume.policy.pipeline.consent_ledger.has_consent", lambda *_: False)
    event = _base_event()
    event["payload"] = {
        "user_id": "u1",
        "scope": "email",
        "attributes": {"name": "Alice"},
    }

    cli_envelope = run_mutation(
        event,
        source="cli_prompt",
        adapter="cli",
        projector=build_graph_projector(MockGraph(), classify=False),
    )
    kafka_envelope = run_mutation(
        event,
        source="kafka_graph_consumer",
        adapter="kafka",
        projector=build_graph_projector(MockGraph(), classify=False),
    )

    assert categorize_envelope_error(cli_envelope) == MutationErrorCategory.POLICY_DENY
    assert categorize_envelope_error(kafka_envelope) == MutationErrorCategory.POLICY_DENY

    with pytest.raises(EventError) as exc:
        ingest_service.ingest_event(event, MockGraph())
    assert str(exc.value).startswith("policy_deny:")


def test_cli_kafka_api_validation_parity() -> None:
    invalid_event = {"eventType": "CREATE_NODE", "payload": {"attributes": {"x": 1}}}

    cli_envelope = run_mutation(
        invalid_event,
        source="cli_prompt",
        adapter="cli",
        projector=build_graph_projector(MockGraph(), classify=False),
    )
    kafka_envelope = run_mutation(
        invalid_event,
        source="kafka_graph_consumer",
        adapter="kafka",
        projector=build_graph_projector(MockGraph(), classify=False),
    )

    assert categorize_envelope_error(cli_envelope) == MutationErrorCategory.VALIDATION
    assert categorize_envelope_error(kafka_envelope) == MutationErrorCategory.VALIDATION

    with pytest.raises(EventError) as exc:
        ingest_service.ingest_event(invalid_event, MockGraph())
    assert str(exc.value).startswith("validation:")
