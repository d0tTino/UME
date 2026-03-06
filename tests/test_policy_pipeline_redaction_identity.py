from __future__ import annotations

from ume.events.ingress import ingest_transport_payload
from ume.policy.pipeline import PolicyContext, PolicyDecision, build_default_policy_pipeline


def test_redaction_builds_new_effective_event_without_mutating_original_event(monkeypatch) -> None:
    monkeypatch.setattr("ume.policy.pipeline.load_plugins", lambda: None)
    monkeypatch.setattr("ume.policy.pipeline.get_plugins", lambda: [])

    event_data = {
        "eventType": "CREATE_NODE",
        "timestamp": 1,
        "nodeId": "n1",
        "producerId": "producer-1",
        "tenant": "tenant-a",
        "signature": "sig-valid",
        "payload": {"email": "user@example.com", "attributes": {"name": "Alice"}, "acl": {"tenant-a": ["producer-1"]}},
    }
    canonical, event = ingest_transport_payload(event_data)
    original_payload_copy = dict(event.payload)

    def _redactor(payload: dict[str, object]) -> tuple[dict[str, object], bool]:
        return ({**payload, "email": "<REDACTED>"}, True)

    context = PolicyContext(
        source="service",
        canonical_event=canonical,
        original_event=event,
        effective_event=event,
    )
    result = build_default_policy_pipeline(redactor=_redactor).evaluate(context)

    assert result.decision == PolicyDecision.REDACTED
    assert result.context.original_event is event
    assert id(result.context.original_event) == id(event)
    assert event.payload == original_payload_copy

    assert result.context.effective_event is not None
    assert result.context.effective_event is not event
    assert result.context.effective_event.payload["email"] == "<REDACTED>"


def test_redaction_audit_details_include_hashes_not_raw_payload(monkeypatch) -> None:
    monkeypatch.setattr("ume.policy.pipeline.load_plugins", lambda: None)
    monkeypatch.setattr("ume.policy.pipeline.get_plugins", lambda: [])

    def _redactor(payload: dict[str, object]) -> tuple[dict[str, object], bool]:
        return ({**payload, "email": "<REDACTED>"}, True)

    event_data = {
        "eventType": "CREATE_NODE",
        "timestamp": 1,
        "nodeId": "n1",
        "producerId": "producer-1",
        "tenant": "tenant-a",
        "signature": "sig-valid",
        "payload": {"email": "user@example.com", "attributes": {"name": "Alice"}, "acl": {"tenant-a": ["producer-1"]}},
    }
    result = build_default_policy_pipeline(redactor=_redactor).evaluate(
        PolicyContext(source="service", transport_data=event_data)
    )

    details = result.audit_event.details
    assert details["redacted"] is True
    assert details["original_payload_hash"]
    assert details["effective_payload_hash"]
    assert details["original_payload_hash"] != details["effective_payload_hash"]
    assert "email" not in details
    assert "user@example.com" not in str(details)
