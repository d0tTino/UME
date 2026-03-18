"""Core event orchestrator shared by API, Kafka, and stream runtimes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import logging
from time import perf_counter
from typing import Any, Awaitable, Callable, Mapping

from ..kernel.events import Event
from ..events.ingress import ingest_transport_payload, IngressAdapter
from ..metrics import (
    PIPELINE_APPLY_FAILURES_TOTAL,
    PIPELINE_INGRESS_TOTAL,
    PIPELINE_POLICY_OUTCOMES_TOTAL,
    PIPELINE_STAGE_LATENCY_SECONDS,
)
from ..kernel.policy import (
    PolicyContext,
    PolicyDecision,
    PolicyPipeline,
    build_default_policy_pipeline,
)
from ..kernel.processing import ProcessingError
from ..tracing import tracer

logger = logging.getLogger(__name__)


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
AsyncProjector = Callable[[PolicyContext], Awaitable[dict[str, Any] | None]]
AsyncAuditor = Callable[[PipelineEnvelope], Awaitable[None]]


def _safe_id_label(value: str | None) -> str:
    if not value:
        return "none"
    digest = sha256(value.encode("utf-8")).hexdigest()
    return f"h:{digest[:12]}"


def _correlation_from_payload(payload: Mapping[str, Any] | None) -> str | None:
    if payload is None:
        return None
    metadata = payload.get("metadata")
    if not isinstance(metadata, Mapping):
        return None
    correlation_ids = metadata.get("correlation_ids")
    if not isinstance(correlation_ids, Mapping):
        return None
    raw = correlation_ids.get("correlation_id")
    return str(raw) if raw is not None else None


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

    def _base_context(
        self,
        *,
        source: str,
        raw_payload: bytes | None,
        decoded: dict[str, Any],
        canonical: dict[str, Any],
        event: Event,
    ) -> PolicyContext:
        metadata = canonical.get("metadata", {}) if isinstance(canonical, Mapping) else {}
        active_schema = metadata.get("schema_version") if isinstance(metadata, Mapping) else None
        resolution_source = metadata.get("schema_resolution_source") if isinstance(metadata, Mapping) else None
        context = PolicyContext(
            source=source,
            raw_payload=raw_payload,
            transport_data=decoded,
            canonical_event=canonical,
            original_event=event,
            effective_event=event,
        )
        if active_schema is not None:
            context.details["active_schema_version"] = str(active_schema)
        if resolution_source is not None:
            context.details["schema_resolution_source"] = str(resolution_source)
        return context

    def _stage_labels(
        self,
        *,
        context: PolicyContext | None = None,
        event: Event | None = None,
        canonical: Mapping[str, Any] | None = None,
    ) -> tuple[str, str]:
        active_event = context.effective_event if context is not None else event
        correlation_id = (
            (context.effective_event.correlation_id if context and context.effective_event else None)
            or (event.correlation_id if event else None)
            or _correlation_from_payload(canonical)
        )
        return _safe_id_label(active_event.event_id if active_event else None), _safe_id_label(correlation_id)

    def _record_stage_latency(
        self,
        *,
        source: str,
        stage: str,
        outcome: PipelineOutcome,
        start: float,
        event_ref: str,
        correlation_ref: str,
    ) -> None:
        PIPELINE_STAGE_LATENCY_SECONDS.labels(
            source=source,
            stage=stage,
            outcome=outcome.value,
            event_ref=event_ref,
            correlation_ref=correlation_ref,
        ).observe(max(perf_counter() - start, 0.0))

    def _emit_pipeline_log(self, *, stage: str, source: str, outcome: PipelineOutcome, reason: str, event: Event | None, correlation_id: str | None) -> None:
        logger.info(
            "pipeline_stage=%s source=%s outcome=%s reason=%s event_id=%s correlation_id=%s",
            stage,
            source,
            outcome.value,
            reason,
            event.event_id if event else None,
            correlation_id,
        )

    def _decode(self, payload: Mapping[str, Any], *, source: str) -> tuple[dict[str, Any] | None, PipelineEnvelope | None]:
        try:
            return dict(payload), None
        except Exception as exc:
            return None, PipelineEnvelope(
                outcome=PipelineOutcome.REJECTED,
                source=source,
                stage="decode",
                reason=f"decode_failed:{exc}",
            )

    def _normalize(
        self,
        decoded: dict[str, Any],
        *,
        source: str,
        adapter: IngressAdapter,
        raw_payload: bytes | None,
    ) -> tuple[dict[str, Any] | None, Event | None, PipelineEnvelope | None]:
        try:
            canonical, event = ingest_transport_payload(decoded, adapter=adapter)
            return canonical, event, None
        except Exception as exc:
            return None, None, PipelineEnvelope(
                outcome=PipelineOutcome.QUARANTINED,
                source=source,
                stage="validate",
                reason=f"transport_validation_failed:{exc}",
                details={"raw_payload_present": raw_payload is not None},
            )

    def _policy(
        self,
        context: PolicyContext,
        *,
        source: str,
    ) -> tuple[PipelineEnvelope | None, PipelineOutcome, PolicyDecision]:
        policy_result = self._policy_pipeline.evaluate(context)
        PIPELINE_POLICY_OUTCOMES_TOTAL.labels(
            source=source,
            decision=policy_result.decision.value,
            event_type=context.effective_event.event_type if context.effective_event else "unknown",
            event_ref=_safe_id_label(context.effective_event.event_id if context.effective_event else None),
            correlation_ref=_safe_id_label(context.effective_event.correlation_id if context.effective_event else None),
        ).inc()
        if policy_result.decision == PolicyDecision.DENY:
            return PipelineEnvelope(
                outcome=PipelineOutcome.REJECTED,
                source=source,
                stage="policy",
                reason=policy_result.audit_event.reason,
                canonical_event=context.canonical_event,
                event=context.effective_event,
                policy_decision=policy_result.decision,
            ), PipelineOutcome.REJECTED, PolicyDecision.DENY
        if policy_result.decision == PolicyDecision.QUARANTINE:
            return PipelineEnvelope(
                outcome=PipelineOutcome.QUARANTINED,
                source=source,
                stage="policy",
                reason=policy_result.audit_event.reason,
                canonical_event=context.canonical_event,
                event=context.effective_event,
                policy_decision=policy_result.decision,
            ), PipelineOutcome.QUARANTINED, PolicyDecision.QUARANTINE
        return None, (
            PipelineOutcome.REDACTED
            if policy_result.decision == PolicyDecision.REDACTED
            else PipelineOutcome.APPLIED
        ), policy_result.decision

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
        with tracer.start_as_current_span("ume.pipeline.run") as span:
            if hasattr(span, "set_attribute"):
                span.set_attribute("ume.source", source)
                span.set_attribute("ume.adapter", adapter)

            decode_start = perf_counter()
            decoded, decode_error = self._decode(payload, source=source)
            if decode_error is not None:
                self._record_stage_latency(source=source, stage="decode", outcome=decode_error.outcome, start=decode_start, event_ref="none", correlation_ref="none")
                self._emit_pipeline_log(stage="decode", source=source, outcome=decode_error.outcome, reason=decode_error.reason, event=None, correlation_id=None)
                return decode_error
            assert decoded is not None
            self._record_stage_latency(source=source, stage="decode", outcome=PipelineOutcome.APPLIED, start=decode_start, event_ref="none", correlation_ref="none")

            normalize_start = perf_counter()
            canonical, event, normalize_error = self._normalize(
                decoded, source=source, adapter=adapter, raw_payload=raw_payload
            )
            if normalize_error is not None:
                event_ref, correlation_ref = self._stage_labels(canonical=decoded)
                self._record_stage_latency(source=source, stage="validate", outcome=normalize_error.outcome, start=normalize_start, event_ref=event_ref, correlation_ref=correlation_ref)
                self._emit_pipeline_log(stage="validate", source=source, outcome=normalize_error.outcome, reason=normalize_error.reason, event=None, correlation_id=None)
                return normalize_error
            assert canonical is not None and event is not None
            event_ref, correlation_ref = self._stage_labels(event=event, canonical=canonical)
            self._record_stage_latency(source=source, stage="validate", outcome=PipelineOutcome.APPLIED, start=normalize_start, event_ref=event_ref, correlation_ref=correlation_ref)
            PIPELINE_INGRESS_TOTAL.labels(
                source=source,
                adapter=adapter,
                event_type=event.event_type,
                event_ref=event_ref,
                correlation_ref=correlation_ref,
            ).inc()

            context = self._base_context(
                source=source,
                raw_payload=raw_payload,
                decoded=decoded,
                canonical=canonical,
                event=event,
            )
            if hasattr(span, "set_attribute"):
                span.set_attribute("ume.event_id", event.event_id)
                if event.correlation_id:
                    span.set_attribute("ume.correlation_id", event.correlation_id)

            policy_start = perf_counter()
            policy_error, provisional_outcome, policy_decision = self._policy(context, source=source)
            event_ref, correlation_ref = self._stage_labels(context=context)
            if policy_error is not None:
                self._record_stage_latency(source=source, stage="policy", outcome=policy_error.outcome, start=policy_start, event_ref=event_ref, correlation_ref=correlation_ref)
                self._emit_pipeline_log(stage="policy", source=source, outcome=policy_error.outcome, reason=policy_error.reason, event=context.effective_event, correlation_id=context.effective_event.correlation_id if context.effective_event else None)
                return policy_error
            self._record_stage_latency(source=source, stage="policy", outcome=provisional_outcome, start=policy_start, event_ref=event_ref, correlation_ref=correlation_ref)

            if context.effective_event is None:
                envelope = PipelineEnvelope(
                    outcome=PipelineOutcome.QUARANTINED,
                    source=source,
                    stage="project",
                    reason="effective_event_missing",
                    canonical_event=context.canonical_event,
                    policy_decision=policy_decision,
                )
                PIPELINE_APPLY_FAILURES_TOTAL.labels(
                    source=source,
                    stage="project",
                    error_category="effective_event_missing",
                    event_type="unknown",
                    event_ref=event_ref,
                    correlation_ref=correlation_ref,
                ).inc()
                return envelope

            details: dict[str, Any] = {}
            if projector is not None:
                project_start = perf_counter()
                try:
                    projected = projector(context)
                    if projected:
                        details.update(projected)
                except ProcessingError as exc:
                    PIPELINE_APPLY_FAILURES_TOTAL.labels(
                        source=source,
                        stage="project",
                        error_category="processing_error",
                        event_type=context.effective_event.event_type,
                        event_ref=event_ref,
                        correlation_ref=correlation_ref,
                    ).inc()
                    failure = PipelineEnvelope(
                        outcome=PipelineOutcome.REJECTED,
                        source=source,
                        stage="project",
                        reason=f"processing_error:{exc}",
                        canonical_event=context.canonical_event,
                        event=context.effective_event,
                        policy_decision=policy_decision,
                    )
                    self._record_stage_latency(source=source, stage="project", outcome=failure.outcome, start=project_start, event_ref=event_ref, correlation_ref=correlation_ref)
                    return failure
                except Exception as exc:
                    PIPELINE_APPLY_FAILURES_TOTAL.labels(
                        source=source,
                        stage="project",
                        error_category="projection_failed",
                        event_type=context.effective_event.event_type,
                        event_ref=event_ref,
                        correlation_ref=correlation_ref,
                    ).inc()
                    failure = PipelineEnvelope(
                        outcome=PipelineOutcome.REJECTED,
                        source=source,
                        stage="project",
                        reason=f"projection_failed:{exc}",
                        canonical_event=context.canonical_event,
                        event=context.effective_event,
                        policy_decision=policy_decision,
                    )
                    self._record_stage_latency(source=source, stage="project", outcome=failure.outcome, start=project_start, event_ref=event_ref, correlation_ref=correlation_ref)
                    return failure
                self._record_stage_latency(source=source, stage="project", outcome=provisional_outcome, start=project_start, event_ref=event_ref, correlation_ref=correlation_ref)

            self._policy_pipeline.audit_post_apply(context)
            envelope = PipelineEnvelope(
                outcome=provisional_outcome,
                source=source,
                stage="audit",
                reason="mutation_applied",
                canonical_event=context.canonical_event,
                event=context.effective_event,
                policy_decision=policy_decision,
                redacted=provisional_outcome == PipelineOutcome.REDACTED,
                details=details,
            )
            self._emit_pipeline_log(
                stage="audit",
                source=source,
                outcome=envelope.outcome,
                reason=envelope.reason,
                event=context.effective_event,
                correlation_id=context.effective_event.correlation_id,
            )
            if auditor is not None:
                auditor(envelope)
            return envelope

    async def run_async(
        self,
        payload: Mapping[str, Any],
        *,
        source: str,
        adapter: IngressAdapter = "default",
        raw_payload: bytes | None = None,
        projector: AsyncProjector | None = None,
        auditor: AsyncAuditor | None = None,
    ) -> PipelineEnvelope:
        decode_start = perf_counter()
        decoded, decode_error = self._decode(payload, source=source)
        if decode_error is not None:
            self._record_stage_latency(source=source, stage="decode", outcome=decode_error.outcome, start=decode_start, event_ref="none", correlation_ref="none")
            return decode_error
        assert decoded is not None
        self._record_stage_latency(source=source, stage="decode", outcome=PipelineOutcome.APPLIED, start=decode_start, event_ref="none", correlation_ref="none")

        normalize_start = perf_counter()
        canonical, event, normalize_error = self._normalize(
            decoded, source=source, adapter=adapter, raw_payload=raw_payload
        )
        if normalize_error is not None:
            event_ref, correlation_ref = self._stage_labels(canonical=decoded)
            self._record_stage_latency(source=source, stage="validate", outcome=normalize_error.outcome, start=normalize_start, event_ref=event_ref, correlation_ref=correlation_ref)
            return normalize_error
        assert canonical is not None and event is not None
        event_ref, correlation_ref = self._stage_labels(event=event, canonical=canonical)
        self._record_stage_latency(source=source, stage="validate", outcome=PipelineOutcome.APPLIED, start=normalize_start, event_ref=event_ref, correlation_ref=correlation_ref)
        PIPELINE_INGRESS_TOTAL.labels(source=source, adapter=adapter, event_type=event.event_type, event_ref=event_ref, correlation_ref=correlation_ref).inc()

        context = self._base_context(source=source, raw_payload=raw_payload, decoded=decoded, canonical=canonical, event=event)
        policy_start = perf_counter()
        policy_error, provisional_outcome, policy_decision = self._policy(context, source=source)
        event_ref, correlation_ref = self._stage_labels(context=context)
        if policy_error is not None:
            self._record_stage_latency(source=source, stage="policy", outcome=policy_error.outcome, start=policy_start, event_ref=event_ref, correlation_ref=correlation_ref)
            return policy_error
        self._record_stage_latency(source=source, stage="policy", outcome=provisional_outcome, start=policy_start, event_ref=event_ref, correlation_ref=correlation_ref)

        if context.effective_event is None:
            PIPELINE_APPLY_FAILURES_TOTAL.labels(source=source, stage="project", error_category="effective_event_missing", event_type="unknown", event_ref=event_ref, correlation_ref=correlation_ref).inc()
            return PipelineEnvelope(
                outcome=PipelineOutcome.QUARANTINED,
                source=source,
                stage="project",
                reason="effective_event_missing",
                canonical_event=context.canonical_event,
                policy_decision=policy_decision,
            )

        details: dict[str, Any] = {}
        if projector is not None:
            project_start = perf_counter()
            try:
                projected = await projector(context)
                if projected:
                    details.update(projected)
            except ProcessingError as exc:
                PIPELINE_APPLY_FAILURES_TOTAL.labels(source=source, stage="project", error_category="processing_error", event_type=context.effective_event.event_type, event_ref=event_ref, correlation_ref=correlation_ref).inc()
                failure = PipelineEnvelope(
                    outcome=PipelineOutcome.REJECTED,
                    source=source,
                    stage="project",
                    reason=f"processing_error:{exc}",
                    canonical_event=context.canonical_event,
                    event=context.effective_event,
                    policy_decision=policy_decision,
                )
                self._record_stage_latency(source=source, stage="project", outcome=failure.outcome, start=project_start, event_ref=event_ref, correlation_ref=correlation_ref)
                return failure
            except Exception as exc:
                PIPELINE_APPLY_FAILURES_TOTAL.labels(source=source, stage="project", error_category="projection_failed", event_type=context.effective_event.event_type, event_ref=event_ref, correlation_ref=correlation_ref).inc()
                failure = PipelineEnvelope(
                    outcome=PipelineOutcome.REJECTED,
                    source=source,
                    stage="project",
                    reason=f"projection_failed:{exc}",
                    canonical_event=context.canonical_event,
                    event=context.effective_event,
                    policy_decision=policy_decision,
                )
                self._record_stage_latency(source=source, stage="project", outcome=failure.outcome, start=project_start, event_ref=event_ref, correlation_ref=correlation_ref)
                return failure
            self._record_stage_latency(source=source, stage="project", outcome=provisional_outcome, start=project_start, event_ref=event_ref, correlation_ref=correlation_ref)

        self._policy_pipeline.audit_post_apply(context)
        envelope = PipelineEnvelope(
            outcome=provisional_outcome,
            source=source,
            stage="audit",
            reason="mutation_applied",
            canonical_event=context.canonical_event,
            event=context.effective_event,
            policy_decision=policy_decision,
            redacted=provisional_outcome == PipelineOutcome.REDACTED,
            details=details,
        )
        if auditor is not None:
            await auditor(envelope)
        return envelope
