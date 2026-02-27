"""Core event orchestrator shared by API, Kafka, and stream runtimes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping

from ..classification import classify_event
from ..event import Event
from ..events.ingress import ingest_transport_payload, IngressAdapter
from ..policy.pipeline import (
    PolicyContext,
    PolicyDecision,
    PolicyPipeline,
    build_default_policy_pipeline,
)
from ..processing import ProcessingError


class PipelineOutcome(str, Enum):
    APPLIED = "applied"
    REJECTED = "rejected"
    QUARANTINED = "quarantined"
    REDACTED = "redacted"


@dataclass
class PipelineEnvelope:
    """Shared orchestration result used for observability and DLQ routing."""

    outcome: PipelineOutcome
    source: str
    stage: str
    reason: str
    canonical_event: dict[str, Any] | None = None
    event: Event | None = None
    policy_decision: PolicyDecision | None = None
    redacted: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def event_id(self) -> str | None:
        return self.event.event_id if self.event is not None else None

    @property
    def event_type(self) -> str | None:
        return self.event.event_type if self.event is not None else None


Projector = Callable[[PolicyContext], dict[str, Any] | None]
Auditor = Callable[[PipelineEnvelope], None]


class EventPipelineOrchestrator:
    """Decode → normalize → validate → policy → project → audit."""

    def __init__(
        self,
        *,
        policy_pipeline: PolicyPipeline | None = None,
    ) -> None:
        self._policy_pipeline = policy_pipeline or build_default_policy_pipeline(
            redactor=lambda payload: (payload, False)
        )

    def run(
        self,
        payload: Mapping[str, Any],
        *,
        source: str,
        adapter: IngressAdapter = "default",
        raw_payload: bytes | None = None,
        projector: Projector | None = None,
        auditor: Auditor | None = None,
    ) -> PipelineEnvelope:
        # decode
        try:
            decoded = dict(payload)
        except Exception as exc:
            return PipelineEnvelope(
                outcome=PipelineOutcome.REJECTED,
                source=source,
                stage="decode",
                reason=f"decode_failed:{exc}",
            )

        # normalize + validate
        try:
            canonical, event = ingest_transport_payload(decoded, adapter=adapter)
        except Exception as exc:
            return PipelineEnvelope(
                outcome=PipelineOutcome.QUARANTINED,
                source=source,
                stage="validate",
                reason=f"transport_validation_failed:{exc}",
                details={"raw_payload_present": raw_payload is not None},
            )

        # policy
        context = PolicyContext(
            source=source,
            raw_payload=raw_payload,
            transport_data=decoded,
            canonical_event=canonical,
            original_event=event,
            effective_event=event,
        )
        policy_result = self._policy_pipeline.evaluate(context)
        if policy_result.decision == PolicyDecision.DENY:
            return PipelineEnvelope(
                outcome=PipelineOutcome.REJECTED,
                source=source,
                stage="policy",
                reason=policy_result.audit_event.reason,
                canonical_event=context.canonical_event,
                event=context.effective_event,
                policy_decision=policy_result.decision,
            )
        if policy_result.decision == PolicyDecision.QUARANTINE:
            return PipelineEnvelope(
                outcome=PipelineOutcome.QUARANTINED,
                source=source,
                stage="policy",
                reason=policy_result.audit_event.reason,
                canonical_event=context.canonical_event,
                event=context.effective_event,
                policy_decision=policy_result.decision,
            )

        provisional_outcome = PipelineOutcome.REDACTED if policy_result.decision == PolicyDecision.REDACTED else PipelineOutcome.APPLIED

        # project
        if context.effective_event is None:
            return PipelineEnvelope(
                outcome=PipelineOutcome.QUARANTINED,
                source=source,
                stage="project",
                reason="effective_event_missing",
                canonical_event=context.canonical_event,
                policy_decision=policy_result.decision,
            )

        details: dict[str, Any] = {}
        if projector is not None:
            try:
                projected = projector(context)
                if projected:
                    details.update(projected)
            except ProcessingError as exc:
                return PipelineEnvelope(
                    outcome=PipelineOutcome.REJECTED,
                    source=source,
                    stage="project",
                    reason=f"processing_error:{exc}",
                    canonical_event=context.canonical_event,
                    event=context.effective_event,
                    policy_decision=policy_result.decision,
                )
            except Exception as exc:
                return PipelineEnvelope(
                    outcome=PipelineOutcome.REJECTED,
                    source=source,
                    stage="project",
                    reason=f"projection_failed:{exc}",
                    canonical_event=context.canonical_event,
                    event=context.effective_event,
                    policy_decision=policy_result.decision,
                )

        # audit
        self._policy_pipeline.audit_post_apply(context)
        envelope = PipelineEnvelope(
            outcome=provisional_outcome,
            source=source,
            stage="audit",
            reason="mutation_applied",
            canonical_event=context.canonical_event,
            event=context.effective_event,
            policy_decision=policy_result.decision,
            redacted=provisional_outcome == PipelineOutcome.REDACTED,
            details=details,
        )
        if auditor is not None:
            auditor(envelope)
        return envelope


def apply_classification(context: PolicyContext) -> dict[str, Any]:
    """Annotate event payload with classification metadata."""

    event = context.effective_event
    if event is None:
        return {}
    tag_results = classify_event(event)
    event.payload["classification"] = [
        {
            "tag": r.tag,
            "confidence": r.confidence,
            "domain": r.domain,
            "subdomain": r.subdomain,
            "sensitivity": r.sensitivity,
        }
        for r in tag_results
    ]
    if tag_results:
        attributes = event.payload.setdefault("attributes", {})
        attributes["tags"] = [r.tag for r in tag_results]
        attributes["tag_confidence"] = [r.confidence for r in tag_results]
        for r in tag_results:
            if r.domain and "domain" not in attributes:
                attributes["domain"] = r.domain
            if r.subdomain and "subdomain" not in attributes:
                attributes["subdomain"] = r.subdomain
            if r.sensitivity and "sensitivity" not in attributes:
                attributes["sensitivity"] = r.sensitivity
    return {"classification_count": len(tag_results)}
