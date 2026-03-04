"""Shared mutation orchestration used across CLI, API, and Kafka entry points."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from ..event import EventError
from ..events.ingress import IngressAdapter
from ..events.versioning import resolve_schema_version
from ..graph_adapter import IGraphAdapter
from ..pipeline.core import (
    EventPipelineOrchestrator,
    PipelineEnvelope,
    PipelineOutcome,
    apply_classification,
)
from ..policy.pipeline import PolicyDecision
from ..processing import DEFAULT_VERSION, apply_event_to_graph
from ..schema_manager import DEFAULT_SCHEMA_MANAGER


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


_orchestrator = EventPipelineOrchestrator()


def _fallback_schema_version() -> str:
    try:
        return DEFAULT_SCHEMA_MANAGER.get_schema().version
    except Exception:  # pragma: no cover - schema resources missing
        return ""


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
    orchestrator: EventPipelineOrchestrator | None = None,
) -> PipelineEnvelope:
    active_orchestrator = orchestrator or _orchestrator
    envelope = active_orchestrator.run(
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
    orchestrator: EventPipelineOrchestrator | None = None,
) -> PipelineEnvelope:
    active_orchestrator = orchestrator or _orchestrator
    envelope = await active_orchestrator.run_async(
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
) -> Callable[[Any], dict[str, Any]]:
    def _project(context: Any) -> dict[str, Any]:
        canonical = context.canonical_event
        event = context.effective_event
        if canonical is None or event is None:
            raise EventError("missing_canonical_or_event")
        effective_version = resolve_schema_version(
            canonical,
            explicit_version=schema_version,
            fallback_version=_fallback_schema_version(),
            default_version=DEFAULT_VERSION,
        )
        details = apply_classification(context) if classify else {}
        apply_event_to_graph(event, graph, schema_version=effective_version)
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
