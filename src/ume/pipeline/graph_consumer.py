"""Kafka consumer that applies events to the graph."""

from __future__ import annotations

import json
import logging

from confluent_kafka import Consumer, KafkaException, KafkaError

from ..config import settings
from ..event import EventType
from ..event_ledger import event_ledger
from ..graph_adapter import IGraphAdapter
from ..logging_utils import configure_logging
from ..processing import apply_event_to_graph
from ..utils import ssl_config
from .core import EventPipelineOrchestrator, PipelineEnvelope, PipelineOutcome
from .invalid_events import build_rejected_event_ledger_entry, outcome_for_pipeline_outcome


configure_logging()
logger = logging.getLogger(__name__)

BOOTSTRAP_SERVERS = settings.KAFKA_BOOTSTRAP_SERVERS
NODE_TOPIC = settings.KAFKA_NODE_TOPIC
EDGE_TOPIC = settings.KAFKA_EDGE_TOPIC
DEFAULT_GROUP_ID = settings.KAFKA_GROUP_ID
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

    orchestrator = EventPipelineOrchestrator()

    def _record_invalid_event(*, offset: int, envelope: PipelineEnvelope) -> None:
        try:
            event_ledger.append(
                offset,
                build_rejected_event_ledger_entry(
                    outcome=outcome_for_pipeline_outcome(envelope.outcome),
                    reason=envelope.reason,
                    source=envelope.source,
                    canonical=envelope.canonical_event,
                    event=envelope.event,
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

            def _project(context):
                event = context.effective_event
                if event is None:
                    raise ValueError("effective_event_missing")
                if event.event_type not in VALID_EVENT_TYPES:
                    raise ValueError(f"unknown_event_type:{event.event_type}")
                apply_event_to_graph(event, graph, schema_version=event.schema_version)
                return {}

            envelope = orchestrator.run(
                payload,
                source="kafka_graph_consumer",
                adapter="kafka",
                raw_payload=msg.value(),
                projector=_project,
            )

            if envelope.outcome in {PipelineOutcome.REJECTED, PipelineOutcome.QUARANTINED}:
                _record_invalid_event(offset=msg.offset(), envelope=envelope)
                try:
                    event_ledger.update_bookmark(msg.offset())
                except Exception as exc:  # pragma: no cover - unexpected errors
                    logger.error("Failed to update bookmark: %s", exc)
                logger.warning("Event rejected at %s stage: %s", envelope.stage, envelope.reason)
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
