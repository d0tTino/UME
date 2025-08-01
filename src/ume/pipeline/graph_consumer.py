"""Kafka consumer that applies events to the graph."""

from __future__ import annotations

import json
import logging

from confluent_kafka import Consumer, KafkaException, KafkaError
from jsonschema import ValidationError

from ..config import settings
from ..utils import ssl_config, event_to_snake
from ..event import parse_event, EventError, EventType
from ..processing import apply_event_to_graph, ProcessingError
from ..schema_utils import validate_event_dict
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
                data_camel = json.loads(msg.value().decode("utf-8"))
                data = event_to_snake(data_camel)
                validation_data = dict(data)
                if "event_type" in validation_data:
                    validation_data["eventType"] = validation_data.pop("event_type")
                validate_event_dict(validation_data)
                payload = data["event"] if "event" in data else data
                event = parse_event(payload)
            except (json.JSONDecodeError, EventError) as exc:
                logger.error("Invalid event skipped: %s", exc)
                continue

            if event.event_type not in VALID_EVENT_TYPES:
                try:
                    event_ledger.append(msg.offset(), payload)
                except ValueError as exc:  # pragma: no cover - unlikely duplicate offset
                    logger.error("Ledger append failed: %s", exc)
                try:
                    event_ledger.update_bookmark(msg.offset())
                except Exception as exc:  # pragma: no cover - unexpected errors
                    logger.error("Failed to update bookmark: %s", exc)
                logger.warning("Unknown event type '%s' skipped", event.event_type)
                continue

            try:
                validate_event_dict(data)
            except ValidationError as exc:
                logger.error("Invalid event skipped: %s", exc)
                continue

            try:
                apply_event_to_graph(event, graph)
            except ProcessingError as exc:
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
