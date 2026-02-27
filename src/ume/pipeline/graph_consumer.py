"""Kafka consumer that applies events to the graph."""

from __future__ import annotations

import json
import logging

from jsonschema import ValidationError
from confluent_kafka import Consumer, KafkaException, KafkaError

from ..config import settings
from ..utils import ssl_config
from ..event import EventError, EventType
from ..events.ingress import ingest_transport_payload
from ..processing import ProcessingError, apply_event_to_graph
from ..policy.pipeline import PolicyContext, PolicyDecision, build_default_policy_pipeline
from ..event_ledger import event_ledger
from .invalid_events import (
    build_rejected_event_ledger_entry,
    outcome_for_policy_decision,
    InvalidEventOutcome,
)
from ..graph_adapter import IGraphAdapter
from ..logging_utils import configure_logging


configure_logging()
logger = logging.getLogger(__name__)

BOOTSTRAP_SERVERS = settings.KAFKA_BOOTSTRAP_SERVERS
NODE_TOPIC = settings.KAFKA_NODE_TOPIC
EDGE_TOPIC = settings.KAFKA_EDGE_TOPIC
DEFAULT_GROUP_ID = settings.KAFKA_GROUP_ID
# Include newly introduced event types such as RESEARCH_JOB_STARTED and
# ENTITY_DISCOVERED so the consumer treats them as first-class events.
VALID_EVENT_TYPES = {e.value for e in EventType}


def run_graph_consumer(
    graph: IGraphAdapter,
    *,
    group_id: str | None = None,
    consumer: Consumer | None = None,
) -> None:
    """Consume events from Kafka and apply them to ``graph``."""

    gid = group_id or DEFAULT_GROUP_ID
    owns_consumer = False
    if consumer is None:
        conf = {
            "bootstrap.servers": BOOTSTRAP_SERVERS,
            "group.id": gid,
            "auto.offset.reset": "earliest",
        }
        conf.update(ssl_config())
        try:
            consumer = Consumer(conf)
        except KafkaException as exc:  # pragma: no cover - network errors
            logger.error("Failed to create Kafka consumer: %s", exc)
            return
        try:
            consumer.subscribe([NODE_TOPIC, EDGE_TOPIC])
        except KafkaException as exc:  # pragma: no cover - network errors
            logger.error("Subscription failed: %s", exc)
            consumer.close()
            return
        owns_consumer = True

    pipeline = build_default_policy_pipeline(redactor=lambda payload: (payload, False))

    def _record_invalid_event(
        *,
        offset: int,
        outcome: InvalidEventOutcome,
        reason: str,
        context: PolicyContext,
    ) -> None:
        try:
            event_ledger.append(
                offset,
                build_rejected_event_ledger_entry(
                    outcome=outcome,
                    reason=reason,
                    source=context.source,
                    canonical=context.canonical_event,
                    event=context.original_event,
                ),
            )
        except ValueError as exc:  # pragma: no cover - unlikely duplicate offset
            logger.error("Ledger append failed: %s", exc)

    logger.info("Graph consumer started with group_id %s", gid)
    try:
        while True:
            try:
                msg = consumer.poll(1.0)
            except KafkaException as exc:  # pragma: no cover - network errors
                logger.error("Poll failed: %s", exc)
                continue
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    logger.error("Kafka error: %s", msg.error())
                continue

            try:
                payload = json.loads(msg.value().decode("utf-8"))
            except (ValueError, json.JSONDecodeError) as exc:
                logger.error("Failed to parse Kafka payload: %s", exc)
                continue

            try:
                canonical, event = ingest_transport_payload(payload, adapter="kafka")
            except (EventError, ValidationError, ValueError) as exc:
                logger.error("Failed to parse Kafka payload: %s", exc)
                _record_invalid_event(
                    offset=msg.offset(),
                    outcome=InvalidEventOutcome.REJECT,
                    reason=f"transport_parse_error:{exc}",
                    context=PolicyContext(
                        source="kafka_graph_consumer",
                        raw_payload=msg.value(),
                        transport_data=payload,
                    ),
                )
                try:
                    event_ledger.update_bookmark(msg.offset())
                except Exception as bookmark_exc:  # pragma: no cover - unexpected errors
                    logger.error("Failed to update bookmark: %s", bookmark_exc)
                continue

            context = PolicyContext(
                source="kafka_graph_consumer",
                raw_payload=msg.value(),
                transport_data=payload,
                canonical_event=canonical,
                original_event=event,
                effective_event=event,
            )
            decision = pipeline.evaluate(context)
            if decision.decision in {PolicyDecision.DENY, PolicyDecision.QUARANTINE}:
                logger.warning("Policy blocked event at consumer: %s", decision.audit_event.reason)
                _record_invalid_event(
                    offset=msg.offset(),
                    outcome=outcome_for_policy_decision(decision.decision),
                    reason=decision.audit_event.reason,
                    context=context,
                )
                try:
                    event_ledger.update_bookmark(msg.offset())
                except Exception as exc:  # pragma: no cover - unexpected errors
                    logger.error("Failed to update bookmark: %s", exc)
                continue

            event = context.effective_event
            if event is None or context.canonical_event is None:
                logger.error("Policy pipeline did not produce a parsed event")
                continue

            if event.event_type not in VALID_EVENT_TYPES:
                _record_invalid_event(
                    offset=msg.offset(),
                    outcome=InvalidEventOutcome.REJECT,
                    reason=f"unknown_event_type:{event.event_type}",
                    context=context,
                )
                try:
                    event_ledger.update_bookmark(msg.offset())
                except Exception as exc:  # pragma: no cover - unexpected errors
                    logger.error("Failed to update bookmark: %s", exc)
                logger.warning("Unknown event type '%s' skipped", event.event_type)
                continue

            try:
                apply_event_to_graph(event, graph)
                pipeline.audit_post_apply(context)
            except ProcessingError as exc:
                _record_invalid_event(
                    offset=msg.offset(),
                    outcome=InvalidEventOutcome.REJECT,
                    reason=f"processing_error:{exc}",
                    context=context,
                )
                logger.error("Event processing failed: %s", exc)
                try:
                    event_ledger.update_bookmark(msg.offset())
                except Exception as bookmark_exc:  # pragma: no cover - unexpected errors
                    logger.error("Failed to update bookmark: %s", bookmark_exc)
                continue
            try:
                event_ledger.update_bookmark(msg.offset())
            except Exception as exc:  # pragma: no cover - unexpected errors
                logger.error("Failed to update bookmark: %s", exc)
    except KeyboardInterrupt:
        logger.info("Graph consumer shutting down")
    finally:
        if owns_consumer:
            consumer.close()
