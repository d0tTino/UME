"""Canonical event processing entrypoint for CLI/API/Kafka/gRPC integrations."""

from __future__ import annotations

from typing import Any, Callable

from ..audit import log_audit_entry
from ..kernel.events import Event, EventError
from ..events.ingress import IngressAdapter
from ..kernel.graph_adapter import IGraphAdapter
from ..pipeline.core import EventPipelineOrchestrator, PipelineEnvelope
from .mutate import (
    MutationError,
    build_graph_projector,
    raise_for_rejected_outcome,
)


class EventProcessorService:
    """Single service boundary for canonical event processing."""

    def __init__(self, *, orchestrator: EventPipelineOrchestrator | None = None) -> None:
        self._orchestrator = orchestrator or EventPipelineOrchestrator()

    def process_payload(
        self,
        payload: dict[str, Any],
        *,
        source: str,
        adapter: IngressAdapter = "default",
        raw_payload: bytes | None = None,
        projector: Callable[[Any], dict[str, Any] | None] | None = None,
    ) -> PipelineEnvelope:
        return self._orchestrator.run(
            payload,
            source=source,
            adapter=adapter,
            raw_payload=raw_payload,
            projector=projector,
        )

    async def process_payload_async(
        self,
        payload: dict[str, Any],
        *,
        source: str,
        adapter: IngressAdapter = "default",
        raw_payload: bytes | None = None,
        projector: Callable[[Any], Any] | None = None,
    ) -> PipelineEnvelope:
        return await self._orchestrator.run_async(
            payload,
            source=source,
            adapter=adapter,
            raw_payload=raw_payload,
            projector=projector,
        )

    def mutate_graph(
        self,
        payload: dict[str, Any],
        *,
        graph: IGraphAdapter,
        source: str,
        adapter: IngressAdapter = "default",
        raw_payload: bytes | None = None,
        schema_version: str | None = None,
        classify: bool = False,
    ) -> PipelineEnvelope:
        envelope = self.process_payload(
            payload,
            source=source,
            adapter=adapter,
            raw_payload=raw_payload,
            projector=build_graph_projector(
                graph,
                schema_version=schema_version,
                classify=classify,
            ),
        )
        self._audit_privileged_mutation(envelope)
        return envelope

    @staticmethod
    def _audit_privileged_mutation(envelope: PipelineEnvelope) -> None:
        event = envelope.event
        actor_id = "unknown"
        correlation_id: str | None = None
        if event is not None:
            subject = event.subject_entity or {}
            actor_id = str(subject.get("id") or event.payload.get("actor_id") or actor_id)
            correlation_id = event.correlation_id
        log_audit_entry(
            user_id=actor_id,
            reason=f"privileged_mutation {envelope.outcome.value} {envelope.stage}:{envelope.reason}",
            actor_id=actor_id,
            correlation_id=correlation_id,
            metadata={
                "source": envelope.source,
                "stage": envelope.stage,
                "outcome": envelope.outcome.value,
                "event_type": envelope.event_type,
            },
        )

    def mutate_graph_or_raise(self, *args: Any, **kwargs: Any) -> PipelineEnvelope:
        envelope = self.mutate_graph(*args, **kwargs)
        raise_for_rejected_outcome(envelope)
        return envelope

    def validate_or_raise(
        self,
        payload: dict[str, Any],
        *,
        source: str,
        adapter: IngressAdapter = "default",
    ) -> Event:
        envelope = self.process_payload(payload, source=source, adapter=adapter)
        try:
            raise_for_rejected_outcome(envelope)
        except MutationError as exc:
            raise EventError(str(exc)) from exc
        if envelope.event is None:
            raise EventError("missing_event")
        return envelope.event

DEFAULT_EVENT_PROCESSOR = EventProcessorService()
