from __future__ import annotations

import pytest

pytest.importorskip("google.protobuf.json_format")

from ume.async_graph_adapter import AsyncGraphAdapterWrapper
from ume.event import EventError
from ume.graph import MockGraph
from ume.pipeline.core import EventPipelineOrchestrator
from ume.policy.pipeline import build_default_policy_pipeline
from ume.services import ingest as ingest_service
import ume.async_graph_adapter as async_adapter


def _base_event() -> dict[str, object]:
    return {
        "eventType": "CREATE_NODE",
        "timestamp": 1,
        "nodeId": "n1",
        "payload": {"attributes": {"name": "Alice", "email": "a@example.com"}},
    }


def _set_orchestrators(monkeypatch: pytest.MonkeyPatch, *, pipeline) -> None:
    monkeypatch.setattr("ume.policy.pipeline.load_plugins", lambda: None)
    monkeypatch.setattr("ume.policy.pipeline.get_plugins", lambda: [])
    orchestrator = EventPipelineOrchestrator(policy_pipeline=pipeline)
    monkeypatch.setattr(ingest_service, "_orchestrator", orchestrator)
    monkeypatch.setattr(async_adapter, "_orchestrator", orchestrator)


@pytest.mark.asyncio
async def test_ingest_parity_deny(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ume.policy.pipeline.consent_ledger.has_consent", lambda *_: False)
    pipeline = build_default_policy_pipeline(redactor=lambda payload: (payload, False))
    _set_orchestrators(monkeypatch, pipeline=pipeline)

    event = _base_event()
    event["payload"] = {
        "user_id": "u1",
        "scope": "email",
        "attributes": {"name": "Alice"},
    }

    sync_graph = MockGraph()
    async_graph = AsyncGraphAdapterWrapper(MockGraph())

    with pytest.raises(EventError):
        ingest_service.ingest_event(event, sync_graph)
    with pytest.raises(EventError):
        await async_adapter.ingest_event_async(event, async_graph)


@pytest.mark.asyncio
async def test_ingest_parity_quarantine(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = build_default_policy_pipeline(redactor=lambda payload: (payload, False))
    _set_orchestrators(monkeypatch, pipeline=pipeline)

    invalid_event = {"eventType": "CREATE_NODE", "payload": {"attributes": {"x": 1}}}

    with pytest.raises(EventError):
        ingest_service.ingest_event(invalid_event, MockGraph())
    with pytest.raises(EventError):
        await async_adapter.ingest_event_async(invalid_event, AsyncGraphAdapterWrapper(MockGraph()))


@pytest.mark.asyncio
async def test_ingest_parity_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    def _redactor(payload):
        attributes = dict(payload.get("attributes", {}))
        if "email" in attributes:
            attributes["email"] = "<REDACTED>"
        return ({**payload, "attributes": attributes}, True)

    pipeline = build_default_policy_pipeline(redactor=_redactor)
    _set_orchestrators(monkeypatch, pipeline=pipeline)

    event = _base_event()
    sync_graph = MockGraph()
    async_graph = AsyncGraphAdapterWrapper(MockGraph())

    ingest_service.ingest_event(event, sync_graph)
    await async_adapter.ingest_event_async(event, async_graph)

    assert sync_graph.get_node("n1") == {"name": "Alice", "email": "<REDACTED>"}
    assert await async_graph.get_node("n1") == {"name": "Alice", "email": "<REDACTED>"}
