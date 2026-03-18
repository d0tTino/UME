"""Shared mutation orchestration used across CLI, API, and Kafka entry points."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from ..kernel.events import EventError
from ..event_ledger import event_ledger
from ..domains.classification import apply_classification
from ..domains.extensions import DomainExtension, run_domain_extensions
from ..events.ingress import IngressAdapter
from ..events.schema_resolution import resolve_active_schema
from ..config import settings
from ..kernel.graph_adapter import IGraphAdapter
from ..pipeline.core import (
    PipelineEnvelope,
    PipelineOutcome,
)
from ..kernel.policy import PolicyDecision
from ..policy.graph_view import build_graph_read_view
from ..kernel.processing import DEFAULT_VERSION, apply_event_to_graph
from ..vector_outbox import enqueue_vector_outbox_event
from ..deprecations import warn_deprecated


class MutationErrorCategory(str, Enum):
    VALIDATION = "validation"
    POLICY_DENY = "policy_deny"
    PROCESSING_FAILURE = "processing_failure"


@dataclass
class MutationError(Exception):
    """Unified mutation error surfaced across transport entry points."""

    category: MutationErrorCategory
    reason: str
    stage: str
    source: str

    def __str__(self) -> str:
        return f"{self.category.value}:{self.reason}"



def categorize_envelope_error(envelope: PipelineEnvelope) -> MutationErrorCategory:
    if envelope.stage in {"decode", "validate"}:
        return MutationErrorCategory.VALIDATION
    if envelope.stage == "policy" and envelope.policy_decision in {
        PolicyDecision.DENY,
        PolicyDecision.QUARANTINE,
    }:
        return MutationErrorCategory.POLICY_DENY
    return MutationErrorCategory.PROCESSING_FAILURE


def _annotate_error(envelope: PipelineEnvelope) -> PipelineEnvelope:
    if envelope.outcome in {PipelineOutcome.REJECTED, PipelineOutcome.QUARANTINED}:
        envelope.details["error_category"] = categorize_envelope_error(envelope).value
    return envelope


def raise_for_rejected_outcome(envelope: PipelineEnvelope) -> None:
    if envelope.outcome not in {PipelineOutcome.REJECTED, PipelineOutcome.QUARANTINED}:
        return
    category = categorize_envelope_error(envelope)
    raise MutationError(
        category=category,
        reason=envelope.reason,
        stage=envelope.stage,
        source=envelope.source,
    )


def run_mutation(
    payload: dict[str, Any],
    *,
    source: str,
    adapter: IngressAdapter = "default",
    raw_payload: bytes | None = None,
    projector: Callable[[Any], dict[str, Any] | None] | None = None,
    orchestrator: Any | None = None,
) -> PipelineEnvelope:
    warn_deprecated("ume.services.mutate.run_mutation", stacklevel=2)
    if orchestrator is not None:
        warn_deprecated(
            "ume.services.mutate.run_mutation",
            detail="The orchestrator parameter is ignored; use EventProcessorService directly for orchestrator injection.",
            stacklevel=2,
        )
    from .event_processor import DEFAULT_EVENT_PROCESSOR

    envelope = DEFAULT_EVENT_PROCESSOR.process_payload(
        payload,
        source=source,
        adapter=adapter,
        raw_payload=raw_payload,
        projector=projector,
    )
    return _annotate_error(envelope)


async def run_mutation_async(
    payload: dict[str, Any],
    *,
    source: str,
    adapter: IngressAdapter = "default",
    raw_payload: bytes | None = None,
    projector: Callable[[Any], Any] | None = None,
    orchestrator: Any | None = None,
) -> PipelineEnvelope:
    warn_deprecated("ume.services.mutate.run_mutation_async", stacklevel=2)
    if orchestrator is not None:
        warn_deprecated(
            "ume.services.mutate.run_mutation_async",
            detail="The orchestrator parameter is ignored; use EventProcessorService directly for orchestrator injection.",
            stacklevel=2,
        )
    from .event_processor import DEFAULT_EVENT_PROCESSOR

    envelope = await DEFAULT_EVENT_PROCESSOR.process_payload_async(
        payload,
        source=source,
        adapter=adapter,
        raw_payload=raw_payload,
        projector=projector,
    )
    return _annotate_error(envelope)


def build_graph_projector(
    graph: IGraphAdapter,
    *,
    schema_version: str | None = None,
    classify: bool = True,
    domain_extensions: list[DomainExtension] | None = None,
) -> Callable[[Any], dict[str, Any]]:
    active_extensions: list[DomainExtension] = list(domain_extensions or [])
    if classify:
        active_extensions.append(apply_classification)

    def _project(context: Any) -> dict[str, Any]:
        canonical = context.canonical_event
        event = context.effective_event
        if canonical is None or event is None:
            raise EventError("missing_canonical_or_event")
        context.graph_read_view = build_graph_read_view(
            graph,
            event=event,
            max_snapshot_nodes=settings.UME_POLICY_GRAPH_MAX_SNAPSHOT_NODES,
            neighborhood_depth=settings.UME_POLICY_GRAPH_NEIGHBORHOOD_DEPTH,
            max_neighborhood_nodes=settings.UME_POLICY_GRAPH_MAX_NEIGHBORHOOD_NODES,
        )
        resolution = resolve_active_schema(
            canonical,
            explicit_version=schema_version,
            default_version=DEFAULT_VERSION,
        )
        effective_version = resolution.active_version
        context.details.setdefault("active_schema_version", effective_version)
        context.details.setdefault("schema_resolution_source", resolution.source)
        details = run_domain_extensions(context, active_extensions)
        apply_event_to_graph(event, graph, schema_version=effective_version)
        enqueue_vector_outbox_event(
            event_ledger,
            event,
            ledger_offset=None,
        )
        return {**details, "schema_version": effective_version}

    return _project


async def apply_event_to_async_graph(
    context: Any,
    graph: Any,
    *,
    schema_version: str,
) -> dict[str, Any]:
    event = context.effective_event
    if event is None:
        raise EventError("effective_event_missing")
    await asyncio.to_thread(apply_event_to_graph, event, graph, schema_version=schema_version)
    return {"schema_version": schema_version}
