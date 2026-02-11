"""Kafka consumer that applies events to the graph."""

from __future__ import annotations

import logging

from confluent_kafka import Consumer, KafkaException, KafkaError

from ..config import settings
from ..utils import ssl_config
from ..event import EventType
from ..events.contract import canonical_to_camel_dict, canonicalize_event
from ..processing import apply_event_to_graph, ProcessingError
from ..policy.pipeline import PolicyContext, PolicyDecision, build_default_policy_pipeline
from ..event_ledger import event_ledger
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

            context = PolicyContext(source="kafka_graph_consumer", raw_payload=msg.value())
            decision = pipeline.evaluate(context)
            if decision.decision in {PolicyDecision.DENY, PolicyDecision.QUARANTINE}:
                logger.warning("Policy blocked event at consumer: %s", decision.audit_event.reason)
                try:
                    event_ledger.update_bookmark(msg.offset())
                except Exception as exc:  # pragma: no cover - unexpected errors
                    logger.error("Failed to update bookmark: %s", exc)
                continue

            event = context.event
            canonical = context.canonical_event
            if event is None or canonical is None:
                logger.error("Policy pipeline did not produce a parsed event")
                continue

            if event.event_type not in VALID_EVENT_TYPES:
                try:
                    event_dict = {
                        "event_type": event.event_type,
                        "timestamp": event.timestamp,
                        "payload": event.payload,
                    }
                    event_ledger.append(msg.offset(), canonical_to_camel_dict(canonicalize_event(event_dict)))
                except ValueError as exc:  # pragma: no cover - unlikely duplicate offset
                    logger.error("Ledger append failed: %s", exc)
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
                if (
                    event.event_type == EventType.CREATE_EDGE
                    and "Unknown edge label" in str(exc)
                    and isinstance(event.node_id, str)
                    and isinstance(event.target_node_id, str)
                    and isinstance(event.label, str)
                ):
                    graph.add_edge(event.node_id, event.target_node_id, event.label, {})
                    pipeline.audit_post_apply(context)
                else:
                    logger.error("Event processing failed: %s", exc)
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
