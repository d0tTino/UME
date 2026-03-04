"""Canonical event processing entrypoint for CLI/API/Kafka/gRPC integrations."""

from __future__ import annotations

from typing import Any, Callable

from ..event import Event, EventError
from ..events.ingress import IngressAdapter
from ..graph_adapter import IGraphAdapter
from ..pipeline.core import EventPipelineOrchestrator, PipelineEnvelope
from .mutate import (
    MutationError,
    build_graph_projector,
    raise_for_rejected_outcome,
    run_mutation,
    run_mutation_async,
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
        return run_mutation(
            payload,
            source=source,
            adapter=adapter,
            raw_payload=raw_payload,
            projector=projector,
            orchestrator=self._orchestrator,
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
        return await run_mutation_async(
            payload,
            source=source,
            adapter=adapter,
            raw_payload=raw_payload,
            projector=projector,
            orchestrator=self._orchestrator,
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
        return self.process_payload(
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
