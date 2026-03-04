"""Kafka consumer that projects sanitized events into the graph."""

from __future__ import annotations

import json
import logging

from confluent_kafka import Consumer, KafkaError, KafkaException

from .config import settings
from .utils import ssl_config, event_to_snake
from .event import parse_event, EventError
from .events.contract import canonicalize_event
from .events.types import EventType
from .processing import apply_event_to_graph, ProcessingError
from .graph_adapter import IGraphAdapter
from .logging_utils import configure_logging


configure_logging()
logger = logging.getLogger(__name__)

BOOTSTRAP_SERVERS = settings.KAFKA_BOOTSTRAP_SERVERS
TOPIC = settings.KAFKA_CLEAN_EVENTS_TOPIC
GROUP_ID = settings.KAFKA_GROUP_ID

VALID_EVENT_TYPES = {e.value for e in EventType}

def run_projection_engine(
    graph: IGraphAdapter,
    *,
    group_id: str | None = None,
    consumer: Consumer | None = None,
) -> None:
    """Consume sanitized events and update ``graph`` accordingly."""
    gid = group_id or GROUP_ID
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
            consumer.subscribe([TOPIC])
        except KafkaException as exc:  # pragma: no cover - network errors
            logger.error("Failed to start projection consumer: %s", exc)
            return
        owns_consumer = True

    logger.info("Projection engine started with group_id %s", gid)
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
                event = parse_event(canonicalize_event(data))
            except (json.JSONDecodeError, EventError) as exc:
                logger.error("Invalid event skipped: %s", exc)
                continue

            if event.event_type not in VALID_EVENT_TYPES:
                logger.warning("Unknown event type '%s' skipped", event.event_type)
                continue

            try:
                apply_event_to_graph(event, graph, schema_version=event.schema_version)
            except ProcessingError as exc:
                logger.error("Event processing failed: %s", exc)
    except KeyboardInterrupt:  # pragma: no cover - manual interrupt
        logger.info("Projection engine shutting down")
    finally:
        if owns_consumer:
            consumer.close()

def main() -> None:
    from .resources import create_graph

    graph = create_graph()
    run_projection_engine(graph)


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()
