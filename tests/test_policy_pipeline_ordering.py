from __future__ import annotations

import json

from ume.policy.pipeline import (
    PolicyContext,
    PolicyDecision,
    build_default_policy_pipeline,
)
from ume.config import settings


def _event(payload: dict[str, object] | None = None) -> dict[str, object]:
    event_payload = dict(payload or {"attributes": {"name": "Alice"}})
    event_payload.setdefault("node_id", "n1")
    event_payload.setdefault("acl", {"tenant-a": ["producer-1"]})
    return {
        "eventType": "CREATE_NODE",
        "timestamp": 1,
        "nodeId": "n1",
        "producerId": "producer-1",
        "tenant": "tenant-a",
        "signature": "sig-valid",
        "payload": event_payload,
    }


def test_deny_precedence_over_redaction(monkeypatch) -> None:
    monkeypatch.setattr("ume.policy.pipeline.load_plugins", lambda: None)
    monkeypatch.setattr("ume.policy.pipeline.get_plugins", lambda: [])
    monkeypatch.setattr("ume.policy.pipeline.consent_ledger.has_consent", lambda *_: False)

    pipeline = build_default_policy_pipeline(
        redactor=lambda payload: ({**payload, "email": "<REDACTED>"}, True)
    )
    result = pipeline.evaluate(
        PolicyContext(
            source="service",
            transport_data=_event({"user_id": "u1", "scope": "email", "email": "user@example.com"}),
        )
    )

    assert result.decision == PolicyDecision.DENY
    assert result.audit_event.stage == "pre_apply_consent"


def test_alignment_plugin_exception_maps_to_quarantine(monkeypatch) -> None:
    monkeypatch.setattr("ume.policy.pipeline.load_plugins", lambda: None)

    class ExplodingPlugin:
        def validate(self, _event) -> None:
            raise RuntimeError("boom")

    monkeypatch.setattr("ume.policy.pipeline.get_plugins", lambda: [ExplodingPlugin()])

    pipeline = build_default_policy_pipeline(
        redactor=lambda payload: (payload, False),
        plugin_provider=lambda: [ExplodingPlugin()],
    )
    result = pipeline.evaluate(PolicyContext(source="service", transport_data=_event()))

    assert result.decision == PolicyDecision.QUARANTINE
    assert result.audit_event.reason == "alignment_plugin_error: RuntimeError"


def test_stage_registry_from_config_and_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("ume.policy.pipeline.load_plugins", lambda: None)
    monkeypatch.setattr("ume.policy.pipeline.get_plugins", lambda: [])

    config = tmp_path / "policy.json"
    config.write_text(
        json.dumps(
            {
                "policy_pipeline": {
                    "stages": [
                        "pre_parse_transport",
                        "pre_apply_producer_auth",
                        "pre_persist_redaction",
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    pipeline = build_default_policy_pipeline(
        redactor=lambda payload: ({**payload, "email": "<REDACTED>"}, True),
        config_path=str(config),
    )
    result = pipeline.evaluate(
        PolicyContext(source="service", transport_data=_event({"email": "user@example.com"}))
    )
    assert result.decision == PolicyDecision.REDACTED

    monkeypatch.setenv("UME_POLICY_PIPELINE_STAGES", "pre_parse_transport")
    env_pipeline = build_default_policy_pipeline(
        redactor=lambda payload: ({**payload, "email": "<REDACTED>"}, True),
    )
    env_result = env_pipeline.evaluate(
        PolicyContext(source="service", transport_data=_event({"email": "user@example.com"}))
    )
    assert env_result.decision == PolicyDecision.ALLOW


def test_alignment_plugin_receives_structured_policy_input(monkeypatch) -> None:
    monkeypatch.setattr("ume.policy.pipeline.load_plugins", lambda: None)

    class CapturingPlugin:
        def __init__(self) -> None:
            self.last_input = None

        def validate(self, _event, *, policy_input=None) -> None:
            self.last_input = policy_input

    plugin = CapturingPlugin()
    pipeline = build_default_policy_pipeline(
        redactor=lambda payload: (payload, False),
        plugin_provider=lambda: [plugin],
    )

    context = PolicyContext(source="service", transport_data=_event({"user_id": "u1"}))
    context.graph_read_view = {
        "mode": "snapshot",
        "nodes": {"n1": {"type": "person"}},
        "edges": [],
    }
    result = pipeline.evaluate(context)

    assert result.decision == PolicyDecision.ALLOW
    assert plugin.last_input["event"]["event_type"] == "CREATE_NODE"
    assert plugin.last_input["graph"]["nodes"]["n1"]["type"] == "person"
    assert plugin.last_input["actor"]["id"] == "u1"


def test_producer_auth_denies_unauthenticated_producer(monkeypatch) -> None:
    monkeypatch.setattr("ume.policy.pipeline.load_plugins", lambda: None)
    monkeypatch.setattr("ume.policy.pipeline.get_plugins", lambda: [])

    event = _event()
    event.pop("signature", None)
    event.pop("producerId", None)

    pipeline = build_default_policy_pipeline(redactor=lambda payload: (payload, False))
    result = pipeline.evaluate(PolicyContext(source="service", transport_data=event))

    assert result.decision == PolicyDecision.DENY
    assert result.audit_event.stage == "pre_apply_producer_auth"
    assert result.audit_event.reason == "producer_not_authenticated"


def test_policy_input_contains_authenticated_producer_claims(monkeypatch) -> None:
    monkeypatch.setattr("ume.policy.pipeline.load_plugins", lambda: None)

    class CapturingPlugin:
        def __init__(self) -> None:
            self.last_input = None

        def validate(self, _event, *, policy_input=None) -> None:
            self.last_input = policy_input

    plugin = CapturingPlugin()
    pipeline = build_default_policy_pipeline(
        redactor=lambda payload: (payload, False),
        plugin_provider=lambda: [plugin],
    )

    event = _event({"attributes": {"name": "Alice"}, "acl": {"tenant-a": ["producer-1"]}})
    event["signature"] = "jwt:sub=producer-1;tenant=tenant-a;acl_allow=true"
    result = pipeline.evaluate(PolicyContext(source="service", transport_data=event))

    assert result.decision == PolicyDecision.ALLOW
    assert plugin.last_input["producer"]["authenticated"] is True
    assert plugin.last_input["producer"]["authorized"] is True
    assert plugin.last_input["producer"]["claims"]["sub"] == "producer-1"


def test_producer_auth_profile_cli_local_dev_allows_missing_credentials(monkeypatch) -> None:
    monkeypatch.setattr("ume.policy.pipeline.load_plugins", lambda: None)
    monkeypatch.setattr("ume.policy.pipeline.get_plugins", lambda: [])
    monkeypatch.setattr(settings, "UME_AUTH_PROFILE_CLI", "local-dev")

    event = _event()
    event.pop("signature", None)
    event.pop("producerId", None)

    pipeline = build_default_policy_pipeline(redactor=lambda payload: (payload, False))
    result = pipeline.evaluate(
        PolicyContext(source="cli_prompt", adapter="cli", transport_data=event)
    )

    assert result.decision == PolicyDecision.ALLOW
    assert result.context.details["producer_auth_profile"] == "local-dev"


def test_producer_auth_profile_kafka_signed_requires_signature(monkeypatch) -> None:
    monkeypatch.setattr("ume.policy.pipeline.load_plugins", lambda: None)
    monkeypatch.setattr("ume.policy.pipeline.get_plugins", lambda: [])
    monkeypatch.setattr(settings, "UME_AUTH_PROFILE_KAFKA", "signed")

    event = _event()
    event.pop("signature", None)

    pipeline = build_default_policy_pipeline(redactor=lambda payload: (payload, False))
    result = pipeline.evaluate(
        PolicyContext(source="kafka_ingest", adapter="kafka", transport_data=event)
    )

    assert result.decision == PolicyDecision.DENY
    assert result.audit_event.reason == "producer_not_authenticated"
