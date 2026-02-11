from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any, Callable, Dict, List, Optional, Protocol

from jsonschema import ValidationError

from ..consent_ledger import consent_ledger
from ..event import Event, EventError, parse_event
from ..events.contract import canonical_to_camel_dict, canonicalize_event
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
    event: Event | None = None
    redacted: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def event_payload(self) -> Dict[str, Any]:
        if self.canonical_event is None:
            return {}
        payload = self.canonical_event.get("payload")
        if isinstance(payload, dict):
            return payload
        return {}


@dataclass
class PolicyResult:
    decision: PolicyDecision
    context: PolicyContext
    audit_event: PolicyAuditEvent


class PolicyStage(Protocol):
    name: str

    def run(self, context: PolicyContext) -> Optional[PolicyResult]:
        ...


class TransportValidationStage:
    name = "pre_parse_transport"

    def run(self, context: PolicyContext) -> Optional[PolicyResult]:
        try:
            if context.transport_data is None:
                if context.raw_payload is None:
                    raise ValueError("missing transport payload")
                context.transport_data = json.loads(context.raw_payload.decode("utf-8"))

            context.canonical_event = canonicalize_event(context.transport_data)
            validate_event_dict(canonical_to_camel_dict(context.canonical_event))
            context.event = parse_event(context.canonical_event)
        except (ValueError, TypeError, json.JSONDecodeError, ValidationError, EventError) as exc:
            return _result(
                PolicyDecision.QUARANTINE,
                context,
                stage=self.name,
                reason=f"transport_validation_failed: {exc}",
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
        if context.event is None:
            return _result(
                PolicyDecision.QUARANTINE,
                context,
                stage=self.name,
                reason="event_missing_after_parse",
            )
        try:
            for plugin in self._plugin_provider():
                plugin.validate(context.event)
        except PolicyViolationError as exc:
            return _result(
                PolicyDecision.DENY,
                context,
                stage=self.name,
                reason=str(exc),
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
        context.canonical_event["payload"] = redacted
        if context.event is not None:
            object.__setattr__(context.event, "payload", redacted)
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
        event = context.event
        audit_event = PolicyAuditEvent(
            decision=PolicyDecision.ALLOW,
            stage=self.name,
            source=context.source,
            reason="mutation_applied",
            event_id=event.event_id if event else None,
            event_type=event.event_type if event else None,
            details=context.details,
        )
        logger.info("policy_audit_event=%s", json.dumps(audit_event.to_dict(), sort_keys=True))
        return PolicyResult(PolicyDecision.ALLOW, context, audit_event)


class PolicyPipeline:
    def __init__(
        self,
        *,
        pre_parse: List[PolicyStage],
        pre_apply: List[PolicyStage],
        pre_persist: List[PolicyStage],
        post_apply: List[PolicyStage],
    ) -> None:
        self._pre_parse = pre_parse
        self._pre_apply = pre_apply
        self._pre_persist = pre_persist
        self._post_apply = post_apply

    def evaluate(self, context: PolicyContext) -> PolicyResult:
        redaction_result: Optional[PolicyResult] = None
        for stage in [*self._pre_parse, *self._pre_apply, *self._pre_persist]:
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
    event = context.event
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
            details=details or {},
        ),
    )


def build_default_policy_pipeline(
    *,
    redactor: Callable[[Dict[str, object]], tuple[Dict[str, object], bool]],
    plugin_loader: Callable[[], None] = load_plugins,
    plugin_provider: Callable[[], List[Any]] = get_plugins,
) -> PolicyPipeline:
    plugin_loader()
    return PolicyPipeline(
        pre_parse=[TransportValidationStage()],
        pre_apply=[ConsentStage(), AlignmentStage(plugin_provider)],
        pre_persist=[PiiRedactionStage(redactor)],
        post_apply=[AuditStage()],
    )
