from __future__ import annotations

import json

from ume.policy.pipeline import (
    PolicyContext,
    PolicyDecision,
    build_default_policy_pipeline,
)


def _run_api(pipeline, event):
    return pipeline.evaluate(PolicyContext(source="api", transport_data=event)).decision


def _run_kafka(pipeline, event):
    payload = json.dumps(event).encode("utf-8")
    return pipeline.evaluate(PolicyContext(source="kafka", raw_payload=payload)).decision


def _run_service(pipeline, event):
    return pipeline.evaluate(PolicyContext(source="service", transport_data=event)).decision


def test_policy_decision_parity_allow(monkeypatch):
    monkeypatch.setattr("ume.policy.pipeline.load_plugins", lambda: None)
    monkeypatch.setattr("ume.policy.pipeline.get_plugins", lambda: [])
    pipeline = build_default_policy_pipeline(redactor=lambda payload: (payload, False))
    event = {
        "eventType": "CREATE_NODE",
        "timestamp": 1,
        "nodeId": "n1",
        "payload": {"attributes": {"name": "Alice"}},
    }

    decisions = {
        _run_api(pipeline, event),
        _run_kafka(pipeline, event),
        _run_service(pipeline, event),
    }
    assert decisions == {PolicyDecision.ALLOW}


def test_policy_decision_parity_deny_for_consent(monkeypatch):
    monkeypatch.setattr("ume.policy.pipeline.load_plugins", lambda: None)
    monkeypatch.setattr("ume.policy.pipeline.get_plugins", lambda: [])
    monkeypatch.setattr("ume.policy.pipeline.consent_ledger.has_consent", lambda *_: False)
    pipeline = build_default_policy_pipeline(redactor=lambda payload: (payload, False))
    event = {
        "eventType": "CREATE_NODE",
        "timestamp": 1,
        "nodeId": "n1",
        "payload": {"user_id": "u1", "scope": "email", "attributes": {"name": "Alice"}},
    }

    decisions = {
        _run_api(pipeline, event),
        _run_kafka(pipeline, event),
        _run_service(pipeline, event),
    }
    assert decisions == {PolicyDecision.DENY}


def test_policy_decision_parity_redacted(monkeypatch):
    monkeypatch.setattr("ume.policy.pipeline.load_plugins", lambda: None)
    monkeypatch.setattr("ume.policy.pipeline.get_plugins", lambda: [])

    def _redactor(payload):
        return ({**payload, "email": "<REDACTED>"}, True)

    pipeline = build_default_policy_pipeline(redactor=_redactor)
    event = {
        "eventType": "CREATE_NODE",
        "timestamp": 1,
        "nodeId": "n1",
        "payload": {"email": "user@example.com", "attributes": {"name": "Alice"}},
    }

    decisions = [
        _run_api(pipeline, event),
        _run_kafka(pipeline, event),
        _run_service(pipeline, event),
    ]
    assert decisions == [PolicyDecision.REDACTED, PolicyDecision.REDACTED, PolicyDecision.REDACTED]
    assert pipeline.evaluate(PolicyContext(source="service", transport_data=event)).context.redacted is True
