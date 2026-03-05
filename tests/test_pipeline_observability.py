from __future__ import annotations

import pytest

from ume.metrics import (
    PIPELINE_INGRESS_TOTAL,
    PIPELINE_POLICY_OUTCOMES_TOTAL,
    PIPELINE_STAGE_LATENCY_SECONDS,
)
from ume.pipeline.core import EventPipelineOrchestrator, PipelineOutcome
from ume.policy.pipeline import build_default_policy_pipeline


def _base_event() -> dict[str, object]:
    return {
        "eventType": "CREATE_NODE",
        "timestamp": 1,
        "nodeId": "n1",
        "metadata": {"correlationIds": {"correlationId": "corr-123"}},
        "payload": {"attributes": {"name": "alice"}},
    }


@pytest.fixture(autouse=True)
def _reset_pipeline_metrics() -> None:
    PIPELINE_INGRESS_TOTAL.clear()
    PIPELINE_POLICY_OUTCOMES_TOTAL.clear()
    PIPELINE_STAGE_LATENCY_SECONDS.clear()




def _hist_count(metric, **labels: str) -> float:
    for collected in metric.collect():
        for sample in collected.samples:
            if not sample.name.endswith("_count"):
                continue
            if all(sample.labels.get(k) == v for k, v in labels.items()):
                return float(sample.value)
    return 0.0

def _counter_total(metric, **labels: str) -> float:
    total = 0.0
    for collected in metric.collect():
        for sample in collected.samples:
            if not sample.name.endswith("_total"):
                continue
            if all(sample.labels.get(k) == v for k, v in labels.items()):
                total += float(sample.value)
    return total


def test_pipeline_smoke_emits_metrics_for_allow_deny_quarantine_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_orchestrator = EventPipelineOrchestrator(
        policy_pipeline=build_default_policy_pipeline(redactor=lambda payload: (payload, False))
    )
    allow_envelope = allow_orchestrator.run(_base_event(), source="smoke", adapter="default")
    assert allow_envelope.outcome is PipelineOutcome.APPLIED

    monkeypatch.setattr("ume.policy.pipeline.consent_ledger.has_consent", lambda *_: False)
    deny_event = _base_event()
    deny_event["payload"] = {"user_id": "u1", "scope": "email", "attributes": {"name": "alice"}}
    deny_envelope = allow_orchestrator.run(deny_event, source="smoke", adapter="default")
    assert deny_envelope.outcome is PipelineOutcome.REJECTED

    class _BrokenPlugin:
        def validate(self, _event) -> None:
            raise RuntimeError("downstream")

    quarantine_orchestrator = EventPipelineOrchestrator(
        policy_pipeline=build_default_policy_pipeline(
            redactor=lambda payload: (payload, False),
            plugin_loader=lambda: None,
            plugin_provider=lambda: [_BrokenPlugin()],
        )
    )
    quarantine_envelope = quarantine_orchestrator.run(_base_event(), source="smoke", adapter="default")
    assert quarantine_envelope.outcome is PipelineOutcome.QUARANTINED

    redacted_orchestrator = EventPipelineOrchestrator(
        policy_pipeline=build_default_policy_pipeline(
            redactor=lambda payload: ({**payload, "attributes": {"name": "<REDACTED>"}}, True)
        )
    )
    redacted_envelope = redacted_orchestrator.run(_base_event(), source="smoke", adapter="default")
    assert redacted_envelope.outcome is PipelineOutcome.REDACTED

    assert _counter_total(PIPELINE_INGRESS_TOTAL, source="smoke", adapter="default", event_type="CREATE_NODE") >= 3
    assert _counter_total(PIPELINE_POLICY_OUTCOMES_TOTAL, source="smoke", decision="ALLOW", event_type="CREATE_NODE") >= 1
    assert _counter_total(PIPELINE_POLICY_OUTCOMES_TOTAL, source="smoke", decision="DENY", event_type="CREATE_NODE") >= 1
    assert _counter_total(PIPELINE_POLICY_OUTCOMES_TOTAL, source="smoke", decision="QUARANTINE", event_type="CREATE_NODE") >= 1
    assert _counter_total(PIPELINE_POLICY_OUTCOMES_TOTAL, source="smoke", decision="REDACTED", event_type="CREATE_NODE") >= 1
    assert _hist_count(PIPELINE_STAGE_LATENCY_SECONDS, source="smoke", stage="policy", outcome="quarantined") >= 1
