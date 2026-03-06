"""Policy pipeline contracts and default stage implementations.

Public stage contract:
- Inputs: each stage receives ``PolicyContext`` and may rely on fields produced by
  earlier stages (for example ``canonical_event`` and ``effective_event``).
- Side effects: stages should mutate only ``PolicyContext`` and not emit audit logs
  directly; audit emission is centralized in :class:`PolicyPipeline`.
- Decision precedence: terminal decisions are resolved in this order:
  ``DENY``/``QUARANTINE`` then ``REDACTED`` then ``ALLOW``.
- Idempotency: stage implementations are expected to be deterministic and safe to
  run repeatedly for equivalent inputs.
"""

from __future__ import annotations

import json
import logging
import os
import inspect
from hashlib import sha256
from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any, Callable, Dict, List, Optional, Protocol

from jsonschema import ValidationError

from ..consent_ledger import consent_ledger
from ..event import Event, EventError, parse_event
from ..events.contract import canonical_to_camel_dict, canonicalize_event
from ..events.schema_resolution import annotate_canonical_schema
from ..plugins.alignment import PolicyViolationError, get_plugins, load_plugins
from ..schema_utils import validate_event_dict

logger = logging.getLogger(__name__)


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    QUARANTINE = "QUARANTINE"
    REDACTED = "REDACTED"


@dataclass
class PolicyAuditEvent:
    decision: PolicyDecision
    stage: str
    source: str
    reason: str
    event_id: str | None
    event_type: str | None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "timestamp": int(time()),
            "decision": self.decision.value,
            "stage": self.stage,
            "source": self.source,
            "reason": self.reason,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "details": self.details,
        }
        return payload


@dataclass
class PolicyContext:
    source: str
    raw_payload: bytes | None = None
    transport_data: Dict[str, Any] | None = None
    canonical_event: Dict[str, Any] | None = None
    original_event: Event | None = None
    effective_event: Event | None = None
    graph_read_view: Dict[str, Any] | None = None
    redacted: bool = False
    producer_auth: Dict[str, Any] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def event_payload(self) -> Dict[str, Any]:
        if self.canonical_event is None:
            return {}
        payload = self.canonical_event.get("payload")
        if isinstance(payload, dict):
            return payload
        return {}

    @property
    def event(self) -> Event | None:
        """Backward-compatible alias for the effective event."""
        return self.effective_event

    @property
    def policy_input(self) -> Dict[str, Any]:
        event = self.effective_event
        actor: Dict[str, Any] = {}
        if event is not None and isinstance(event.subject_entity, dict):
            actor = dict(event.subject_entity)
        if not actor:
            user_id = self.event_payload.get("user_id")
            if user_id is not None:
                actor = {"id": str(user_id), "type": "user"}

        event_doc: Dict[str, Any] = {}
        if event is not None:
            event_doc = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "timestamp": event.timestamp,
                "node_id": event.node_id,
                "target_node_id": event.target_node_id,
                "label": event.label,
                "payload": event.payload,
                "correlation_id": event.correlation_id,
                "schema_version": event.schema_version,
                "producer_id": event.producer_id,
                "tenant": event.tenant,
                "producer_signature": event.producer_signature,
            }

        source_doc: Dict[str, Any] = {"transport": self.source}
        if event is not None and event.source_service:
            source_doc["service"] = event.source_service

        return {
            "event": event_doc,
            "graph": self.graph_read_view or {},
            "actor": actor,
            "source": source_doc,
            "producer": {
                "authenticated": bool(self.producer_auth.get("authenticated", False)),
                "authorized": bool(self.producer_auth.get("authorized", False)),
                "method": self.producer_auth.get("method"),
                "claims": self.producer_auth.get("claims", {}),
            },
            "metadata": {
                "redacted": self.redacted,
                "canonical_metadata": (self.canonical_event or {}).get("metadata", {}),
            },
        }


@dataclass
class PolicyResult:
    decision: PolicyDecision
    context: PolicyContext
    audit_event: PolicyAuditEvent


class PolicyStage(Protocol):
    name: str

    def run(self, context: PolicyContext) -> Optional[PolicyResult]:
        ...


@dataclass(frozen=True)
class PolicyStageRegistration:
    """Declarative registration record for configurable policy pipelines.

    Contract
    --------
    Stage input:
      * Stages receive a shared :class:`PolicyContext` instance and may mutate it.
      * Input event data is progressively normalized from ``raw_payload`` or
        ``transport_data`` into ``canonical_event`` and ``effective_event``.

    Side effects:
      * Stages should only perform deterministic, idempotent mutations against
        ``PolicyContext`` and avoid externally-visible side effects.
      * Audit/log emission is handled centrally by :class:`PolicyPipeline`.

    Decision precedence:
      * Decision stages are always evaluated before transform stages.
      * Terminal precedence is ``DENY`` / ``QUARANTINE`` > ``REDACTED`` > ``ALLOW``.

    Idempotency:
      * Running the same stage sequence multiple times with equivalent context
        should yield equivalent decisions and equivalent canonical payload hashes.
    """

    name: str
    phase: str
    stage_type: str
    factory: Callable[[], PolicyStage]
    order: int = 100


class StageRegistry:
    """Registry that builds policy stage instances from declarative configuration."""

    def __init__(self) -> None:
        self._registrations: Dict[str, PolicyStageRegistration] = {}
        self._insert_order: Dict[str, int] = {}

    def register(self, registration: PolicyStageRegistration) -> None:
        self._insert_order.setdefault(registration.name, len(self._insert_order))
        self._registrations[registration.name] = registration

    def _ordered(self, registrations: List[PolicyStageRegistration]) -> List[PolicyStageRegistration]:
        return sorted(
            registrations,
            key=lambda item: (item.order, self._insert_order[item.name], item.name),
        )

    def registrations_from_names(self, names: List[str]) -> List[PolicyStageRegistration]:
        stages: List[PolicyStageRegistration] = []
        for name in names:
            registration = self._registrations.get(name)
            if registration is None:
                raise ValueError(f"unknown policy stage: {name}")
            stages.append(registration)
        return self._ordered(stages)

    def resolve_names(self, *, config_path: str | None = None) -> List[str]:
        default = [registration.name for registration in self._ordered(list(self._registrations.values()))]
        configured: List[str] = []
        if config_path:
            with open(config_path, "r", encoding="utf-8") as handle:
                doc = json.load(handle)
            configured = [str(name) for name in doc.get("policy_pipeline", {}).get("stages", [])]

        env_config = os.getenv("UME_POLICY_PIPELINE_STAGES")
        if env_config:
            configured = [name.strip() for name in env_config.split(",") if name.strip()]
        return configured or default


class TransportValidationStage:
    name = "pre_parse_transport"

    def run(self, context: PolicyContext) -> Optional[PolicyResult]:
        try:
            if context.canonical_event is not None and context.effective_event is not None:
                return None
            if context.transport_data is None:
                if context.raw_payload is None:
                    raise ValueError("missing transport payload")
                context.transport_data = json.loads(context.raw_payload.decode("utf-8"))

            canonical = canonicalize_event(context.transport_data)
            canonical, resolution = annotate_canonical_schema(canonical, default_version="1.0.0")
            context.canonical_event = canonical
            context.details.setdefault("active_schema_version", resolution.active_version)
            context.details.setdefault("schema_resolution_source", resolution.source)
            validate_event_dict(canonical_to_camel_dict(context.canonical_event))
            parsed = parse_event(context.canonical_event)
            context.original_event = parsed
            context.effective_event = parsed
        except (ValueError, TypeError, json.JSONDecodeError, ValidationError, EventError) as exc:
            return _result(
                PolicyDecision.QUARANTINE,
                context,
                stage=self.name,
                reason=f"transport_validation_failed: {exc}",
            )
        return None


class ProducerAuthStage:
    name = "pre_apply_producer_auth"

    def run(self, context: PolicyContext) -> Optional[PolicyResult]:
        event = context.effective_event
        if event is None:
            return _result(
                PolicyDecision.QUARANTINE,
                context,
                stage=self.name,
                reason="event_missing_before_producer_auth",
            )

        auth_method = "none"
        claims: Dict[str, Any] = {}
        metadata = (context.canonical_event or {}).get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        producer_id = event.producer_id
        tenant = event.tenant
        signature = event.producer_signature

        if isinstance(signature, str) and signature.startswith("jwt:"):
            auth_method = "jwt"
            token_claims = signature[len("jwt:") :].strip()
            if token_claims:
                for piece in token_claims.split(";"):
                    key, sep, value = piece.partition("=")
                    if sep and key.strip():
                        claims[key.strip()] = value.strip()
                claims.setdefault("sub", producer_id)
                claims.setdefault("tenant", tenant)
        elif isinstance(signature, str) and signature.strip():
            auth_method = "signature"
            claims = {"producer_id": producer_id, "tenant": tenant}
        elif producer_id and tenant:
            auth_method = "acl"
            claims = {"producer_id": producer_id, "tenant": tenant}

        authenticated = bool(producer_id and tenant and auth_method != "none")
        allowed_producer_mapping = context.event_payload.get("acl", {})
        authorized = False
        if authenticated and claims.get("acl_allow") == "true":
            authorized = True
        elif authenticated and isinstance(allowed_producer_mapping, dict):
            allowed = allowed_producer_mapping.get(str(tenant))
            if isinstance(allowed, list):
                authorized = str(producer_id) in {str(item) for item in allowed}

        context.producer_auth = {
            "authenticated": authenticated,
            "authorized": authorized,
            "method": auth_method,
            "claims": claims,
            "producer_id": producer_id,
            "tenant": tenant,
        }
        context.details.update(
            {
                "producer_auth_method": auth_method,
                "producer_authenticated": authenticated,
                "producer_authorized": authorized,
                "producer_id": producer_id,
                "tenant": tenant,
            }
        )

        if not authenticated:
            return _result(
                PolicyDecision.DENY,
                context,
                stage=self.name,
                reason="producer_not_authenticated",
            )
        if not authorized:
            return _result(
                PolicyDecision.DENY,
                context,
                stage=self.name,
                reason="producer_not_authorized",
            )
        return None


class ConsentStage:
    name = "pre_apply_consent"

    def run(self, context: PolicyContext) -> Optional[PolicyResult]:
        payload = context.event_payload
        user_id = payload.get("user_id")
        scope = payload.get("scope")
        if user_id and scope and not consent_ledger.has_consent(str(user_id), str(scope)):
            return _result(
                PolicyDecision.DENY,
                context,
                stage=self.name,
                reason="missing_consent",
                details={"user_id": str(user_id), "scope": str(scope)},
            )
        return None


class AlignmentStage:
    name = "pre_apply_alignment"

    def __init__(self, plugin_provider: Callable[[], List[Any]]):
        self._plugin_provider = plugin_provider

    def run(self, context: PolicyContext) -> Optional[PolicyResult]:
        if context.effective_event is None:
            return _result(
                PolicyDecision.QUARANTINE,
                context,
                stage=self.name,
                reason="event_missing_after_parse",
            )
        try:
            for plugin in self._plugin_provider():
                _validate_with_context(plugin, context)
        except PolicyViolationError as exc:
            return _result(
                PolicyDecision.DENY,
                context,
                stage=self.name,
                reason=str(exc),
            )
        except Exception as exc:  # pragma: no cover - defensive mapping
            return _result(
                PolicyDecision.QUARANTINE,
                context,
                stage=self.name,
                reason=f"alignment_plugin_error: {exc.__class__.__name__}",
            )
        return None


class PiiRedactionStage:
    name = "pre_persist_redaction"

    def __init__(self, redactor: Callable[[Dict[str, object]], tuple[Dict[str, object], bool]]):
        self._redactor = redactor

    def run(self, context: PolicyContext) -> Optional[PolicyResult]:
        if context.canonical_event is None:
            return _result(
                PolicyDecision.QUARANTINE,
                context,
                stage=self.name,
                reason="event_missing_before_redaction",
            )
        payload = context.event_payload
        redacted, was_redacted = self._redactor(dict(payload))
        canonical = {**context.canonical_event, "payload": redacted}
        context.canonical_event = canonical
        context.effective_event = parse_event(canonical)
        context.redacted = was_redacted
        if was_redacted:
            return _result(
                PolicyDecision.REDACTED,
                context,
                stage=self.name,
                reason="payload_redacted",
            )
        return None


class AuditStage:
    name = "post_apply_auditing"

    def run(self, context: PolicyContext) -> Optional[PolicyResult]:
        event = context.effective_event
        audit_event = PolicyAuditEvent(
            decision=PolicyDecision.ALLOW,
            stage=self.name,
            source=context.source,
            reason="mutation_applied",
            event_id=event.event_id if event else None,
            event_type=event.event_type if event else None,
            details={**_context_audit_details(context), **context.details},
        )
        logger.info("policy_audit_event=%s", json.dumps(audit_event.to_dict(), sort_keys=True))
        return PolicyResult(PolicyDecision.ALLOW, context, audit_event)


class PolicyPipeline:
    def __init__(
        self,
        *,
        decision_stages: List[PolicyStage],
        transform_stages: List[PolicyStage],
        post_apply: List[PolicyStage],
    ) -> None:
        self._decision_stages = decision_stages
        self._transform_stages = transform_stages
        self._post_apply = post_apply

    def evaluate(self, context: PolicyContext) -> PolicyResult:
        redaction_result: Optional[PolicyResult] = None
        for stage in self._decision_stages:
            result = stage.run(context)
            if result is None:
                continue
            if result.decision in {PolicyDecision.DENY, PolicyDecision.QUARANTINE}:
                self._emit(result.audit_event)
                return result

        for stage in self._transform_stages:
            result = stage.run(context)
            if result is None:
                continue
            if result.decision in {PolicyDecision.DENY, PolicyDecision.QUARANTINE}:
                self._emit(result.audit_event)
                return result
            if result.decision == PolicyDecision.REDACTED:
                redaction_result = result

        if redaction_result is not None:
            self._emit(redaction_result.audit_event)
            return redaction_result

        allow_result = _result(
            PolicyDecision.ALLOW,
            context,
            stage="pipeline",
            reason="policy_checks_passed",
        )
        self._emit(allow_result.audit_event)
        return allow_result

    def audit_post_apply(self, context: PolicyContext) -> None:
        for stage in self._post_apply:
            result = stage.run(context)
            if result is not None:
                self._emit(result.audit_event)

    @staticmethod
    def _emit(audit_event: PolicyAuditEvent) -> None:
        logger.info("policy_decision=%s", json.dumps(audit_event.to_dict(), sort_keys=True))


def _result(
    decision: PolicyDecision,
    context: PolicyContext,
    *,
    stage: str,
    reason: str,
    details: Dict[str, Any] | None = None,
) -> PolicyResult:
    event = context.effective_event
    merged_details = {
        **_context_audit_details(context),
        **context.details,
        **(details or {}),
    }
    return PolicyResult(
        decision=decision,
        context=context,
        audit_event=PolicyAuditEvent(
            decision=decision,
            stage=stage,
            source=context.source,
            reason=reason,
            event_id=event.event_id if event else None,
            event_type=event.event_type if event else None,
            details=merged_details,
        ),
    )


def _payload_hash(payload: Dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    stable = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(stable.encode("utf-8")).hexdigest()


def _context_audit_details(context: PolicyContext) -> Dict[str, Any]:
    original_payload = None
    effective_payload = None
    if context.original_event is not None:
        original_payload = context.original_event.payload
    if context.canonical_event is not None and isinstance(context.canonical_event.get("payload"), dict):
        effective_payload = context.canonical_event["payload"]

    graph_read_view = context.graph_read_view or {}
    return {
        "original_event_id": context.original_event.event_id if context.original_event else None,
        "original_event_type": context.original_event.event_type if context.original_event else None,
        "effective_event_id": context.effective_event.event_id if context.effective_event else None,
        "effective_event_type": context.effective_event.event_type if context.effective_event else None,
        "original_payload_hash": _payload_hash(original_payload),
        "effective_payload_hash": _payload_hash(effective_payload),
        "redacted": context.redacted,
        "graph_view_mode": graph_read_view.get("mode"),
        "graph_view_nodes": len(graph_read_view.get("nodes", {}))
        if isinstance(graph_read_view.get("nodes"), dict)
        else None,
    }


def _validate_with_context(plugin: Any, context: PolicyContext) -> None:
    validate = getattr(plugin, "validate")
    params = inspect.signature(validate).parameters
    if "policy_input" in params:
        validate(context.effective_event, policy_input=context.policy_input)
        return
    validate(context.effective_event)


def build_default_policy_pipeline(
    *,
    redactor: Callable[[Dict[str, object]], tuple[Dict[str, object], bool]],
    plugin_loader: Callable[[], None] = load_plugins,
    plugin_provider: Callable[[], List[Any]] = get_plugins,
    registry: StageRegistry | None = None,
    config_path: str | None = None,
) -> PolicyPipeline:
    plugin_loader()
    active_registry = registry or _default_stage_registry(
        redactor=redactor,
        plugin_provider=plugin_provider,
    )
    stage_names = active_registry.resolve_names(config_path=config_path)
    registrations = active_registry.registrations_from_names(stage_names)
    decision_stages = [r.factory() for r in registrations if r.stage_type == "decision"]
    transform_stages = [r.factory() for r in registrations if r.stage_type == "transform"]
    post_apply = [r.factory() for r in registrations if r.stage_type == "post_apply"]
    return PolicyPipeline(
        decision_stages=decision_stages,
        transform_stages=transform_stages,
        post_apply=post_apply,
    )


def _default_stage_registry(
    *,
    redactor: Callable[[Dict[str, object]], tuple[Dict[str, object], bool]],
    plugin_provider: Callable[[], List[Any]],
) -> StageRegistry:
    registry = StageRegistry()
    registry.register(
        PolicyStageRegistration(
            name=TransportValidationStage.name,
            phase="pre_parse",
            stage_type="decision",
            order=10,
            factory=lambda: TransportValidationStage(),
        )
    )
    registry.register(
        PolicyStageRegistration(
            name=ProducerAuthStage.name,
            phase="pre_apply",
            stage_type="decision",
            order=20,
            factory=lambda: ProducerAuthStage(),
        )
    )
    registry.register(
        PolicyStageRegistration(
            name=ConsentStage.name,
            phase="pre_apply",
            stage_type="decision",
            order=30,
            factory=lambda: ConsentStage(),
        )
    )
    registry.register(
        PolicyStageRegistration(
            name=AlignmentStage.name,
            phase="pre_apply",
            stage_type="decision",
            order=40,
            factory=lambda: AlignmentStage(plugin_provider),
        )
    )
    registry.register(
        PolicyStageRegistration(
            name=PiiRedactionStage.name,
            phase="pre_persist",
            stage_type="transform",
            order=50,
            factory=lambda: PiiRedactionStage(redactor),
        )
    )
    registry.register(
        PolicyStageRegistration(
            name=AuditStage.name,
            phase="post_apply",
            stage_type="post_apply",
            order=60,
            factory=lambda: AuditStage(),
        )
    )
    return registry
