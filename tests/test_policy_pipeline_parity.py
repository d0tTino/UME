from __future__ import annotations

import json

from ume.graph import MockGraph
from ume.kernel.events import parse_event
from ume.policy.pipeline import (
    PolicyContext,
    PolicyDecision,
    build_default_policy_pipeline,
)


def _canonical_transport_event(
    *,
    event_type: str,
    node_id: str,
    payload: dict[str, object],
) -> dict[str, object]:
    return {
        "metadata": {
            "event_type": event_type,
            "timestamp": 1,
            "producer_id": "producer-1",
            "tenant": "tenant-a",
            "producer_signature": "sig-valid",
        },
        "graph": {"node_id": node_id},
        "payload": payload,
    }


def _context_from_canonical(source: str, event: dict[str, object], *, graph=None) -> PolicyContext:
    parsed = parse_event(event)
    return PolicyContext(
        source=source,
        transport_data=event,
        canonical_event=event,
        original_event=parsed,
        effective_event=parsed,
        graph_adapter=graph,
    )


def _run_api(pipeline, event):
    return pipeline.evaluate(_context_from_canonical("api", event)).decision


def _run_kafka(pipeline, event):
    payload = json.dumps(event).encode("utf-8")
    context = _context_from_canonical("kafka", event)
    context.raw_payload = payload
    return pipeline.evaluate(context).decision


def _run_service(pipeline, event):
    return pipeline.evaluate(_context_from_canonical("service", event)).decision


def test_policy_decision_parity_allow(monkeypatch):
    monkeypatch.setattr("ume.policy.pipeline.load_plugins", lambda: None)
    monkeypatch.setattr("ume.policy.pipeline.get_plugins", lambda: [])
    pipeline = build_default_policy_pipeline(redactor=lambda payload: (payload, False))
    event = _canonical_transport_event(
        event_type="CREATE_NODE",
        node_id="n1",
        payload={"attributes": {"name": "Alice"}, "acl": {"tenant-a": ["producer-1"]}},
    )

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
    event = _canonical_transport_event(
        event_type="CREATE_NODE",
        node_id="n1",
        payload={"user_id": "u1", "scope": "email", "attributes": {"name": "Alice"}, "acl": {"tenant-a": ["producer-1"]}},
    )

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
    event = _canonical_transport_event(
        event_type="CREATE_NODE",
        node_id="n1",
        payload={"email": "user@example.com", "attributes": {"name": "Alice"}, "acl": {"tenant-a": ["producer-1"]}},
    )

    decisions = [
        _run_api(pipeline, event),
        _run_kafka(pipeline, event),
        _run_service(pipeline, event),
    ]
    assert decisions == [PolicyDecision.REDACTED, PolicyDecision.REDACTED, PolicyDecision.REDACTED]
    assert pipeline.evaluate(_context_from_canonical("service", event)).context.redacted is True


def test_policy_parity_alignment_plugins_receive_graph_context(monkeypatch):
    class _GraphAwarePlugin:
        def __init__(self):
            self.seen_graph_node_counts: list[int] = []

        def validate(self, _event, *, policy_input):
            graph_doc = policy_input.get("graph", {})
            self.seen_graph_node_counts.append(len(graph_doc.get("nodes", {})))

    plugin = _GraphAwarePlugin()
    pipeline = build_default_policy_pipeline(
        redactor=lambda payload: (payload, False),
        plugin_loader=lambda: None,
        plugin_provider=lambda: [plugin],
    )
    graph = MockGraph()
    graph.add_node("n1", {"name": "existing"})
    event = _canonical_transport_event(
        event_type="UPDATE_NODE_ATTRIBUTES",
        node_id="n1",
        payload={"attributes": {"name": "Alice"}, "acl": {"tenant-a": ["producer-1"]}},
    )

    decisions = [
        pipeline.evaluate(_context_from_canonical("api", event, graph=graph)).decision,
        pipeline.evaluate(_context_from_canonical("kafka", event, graph=graph)).decision,
        pipeline.evaluate(_context_from_canonical("service", event, graph=graph)).decision,
    ]

    assert decisions == [PolicyDecision.ALLOW, PolicyDecision.ALLOW, PolicyDecision.ALLOW]
    assert plugin.seen_graph_node_counts
    assert all(node_count > 0 for node_count in plugin.seen_graph_node_counts)


def test_policy_context_policy_input_includes_graph_read_view_for_existing_nodes(monkeypatch):
    monkeypatch.setattr("ume.policy.pipeline.load_plugins", lambda: None)
    monkeypatch.setattr("ume.policy.pipeline.get_plugins", lambda: [])
    pipeline = build_default_policy_pipeline(redactor=lambda payload: (payload, False))
    graph = MockGraph()
    graph.add_node("n1", {"name": "existing"})
    event = _canonical_transport_event(
        event_type="UPDATE_NODE_ATTRIBUTES",
        node_id="n1",
        payload={"attributes": {"name": "Alice"}, "acl": {"tenant-a": ["producer-1"]}},
    )

    result = pipeline.evaluate(_context_from_canonical("service", event, graph=graph))

    assert result.decision == PolicyDecision.ALLOW
    assert result.context.policy_input["graph"].get("nodes")
