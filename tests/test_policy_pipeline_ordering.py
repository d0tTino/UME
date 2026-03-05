from __future__ import annotations

import json

from ume.policy.pipeline import (
    PolicyContext,
    PolicyDecision,
    build_default_policy_pipeline,
)


def _event(payload: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "eventType": "CREATE_NODE",
        "timestamp": 1,
        "nodeId": "n1",
        "payload": payload or {"attributes": {"name": "Alice"}},
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
