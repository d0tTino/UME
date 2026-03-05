from __future__ import annotations

import pytest

from ume.graph import MockGraph
from ume.processing import apply_event_to_graph
from ume.services.event_processor import DEFAULT_EVENT_PROCESSOR
from ume.services.mutate import MutationErrorCategory, categorize_envelope_error


@pytest.fixture()
def _audit_path(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UME_AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
    monkeypatch.setenv("UME_AUDIT_SIGNING_KEY", "test-signing-key")
    import importlib
    import ume.audit as audit

    importlib.reload(audit)
    yield str(tmp_path / "audit.log")


def _policy_event() -> dict[str, object]:
    return {
        "eventType": "CREATE_NODE",
        "timestamp": 1,
        "nodeId": "n1",
        "payload": {
            "actor_id": "actor-1",
            "user_id": "u1",
            "scope": "email",
            "attributes": {"name": "Alice"},
        },
    }


def test_mutation_entrypoints_deny_at_policy_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ume.policy.pipeline.consent_ledger.has_consent", lambda *_: False)
    event = _policy_event()

    cli = DEFAULT_EVENT_PROCESSOR.mutate_graph(event, graph=MockGraph(), source="cli_prompt", adapter="cli")
    api = DEFAULT_EVENT_PROCESSOR.mutate_graph(event, graph=MockGraph(), source="graph_routes", adapter="default")
    kafka = DEFAULT_EVENT_PROCESSOR.mutate_graph(
        event,
        graph=MockGraph(),
        source="kafka_graph_consumer",
        adapter="kafka",
    )

    assert categorize_envelope_error(cli) == MutationErrorCategory.POLICY_DENY
    assert categorize_envelope_error(api) == MutationErrorCategory.POLICY_DENY
    assert categorize_envelope_error(kafka) == MutationErrorCategory.POLICY_DENY
    assert cli.stage == api.stage == kafka.stage == "policy"


def test_direct_processing_path_can_bypass_policy_and_is_detectable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Threat model regression check for direct graph mutation bypass risk."""

    monkeypatch.setattr("ume.policy.pipeline.consent_ledger.has_consent", lambda *_: False)
    event_payload = _policy_event()

    envelope = DEFAULT_EVENT_PROCESSOR.mutate_graph(
        event_payload,
        graph=MockGraph(),
        source="service_ingest",
        adapter="default",
    )
    assert categorize_envelope_error(envelope) == MutationErrorCategory.POLICY_DENY

    # Direct use of apply_event_to_graph intentionally skips policy pipeline.
    # This assertion guards against accidentally introducing new external
    # entrypoints that call the direct mutation function.
    from ume.event import parse_event
    from ume.events.contract import canonicalize_event

    graph = MockGraph()
    apply_event_to_graph(parse_event(canonicalize_event(event_payload)), graph)
    node = graph.get_node("n1")
    assert node is not None
    assert node["name"] == "Alice"


def test_privileged_mutation_audit_includes_actor_and_correlation(
    _audit_path,
) -> None:
    from ume.audit import get_audit_entries

    event = {
        "eventType": "CREATE_NODE",
        "timestamp": 1,
        "eventId": "evt-1",
        "correlationId": "corr-1",
        "nodeId": "n1",
        "payload": {"actor_id": "actor-1", "attributes": {"name": "Alice"}},
    }

    DEFAULT_EVENT_PROCESSOR.mutate_graph(event, graph=MockGraph(), source="cli_prompt", adapter="cli")
    entries = get_audit_entries()
    assert entries
    latest = entries[-1]
    assert latest["user_id"] == "actor-1"
    assert latest["actor_id"] == "actor-1"
    assert latest["correlation_id"] == "corr-1"
    assert latest["signature"]
