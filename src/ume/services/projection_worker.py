"""Dedicated worker for projecting clean events into the graph."""

from __future__ import annotations

import json
import logging

from confluent_kafka import Consumer, KafkaError, KafkaException

from ..config import settings
from ..events.types import EventType
from ..kernel.graph_adapter import IGraphAdapter
from ..logging_utils import configure_logging
from ..pipeline.core import EventPipelineOrchestrator, PipelineOutcome
from ..resources import create_graph
from ..utils import ssl_config
from .event_processor import EventProcessorService
from .mutate import build_graph_projector


configure_logging()
logger = logging.getLogger(__name__)

BOOTSTRAP_SERVERS = settings.KAFKA_BOOTSTRAP_SERVERS
TOPIC = settings.KAFKA_CLEAN_EVENTS_TOPIC
GROUP_ID = settings.KAFKA_GROUP_ID
VALID_EVENT_TYPES = {event_type.value for event_type in EventType}


def run_projection_worker(
    graph: IGraphAdapter,
    *,
    group_id: str | None = None,
    consumer: Consumer | None = None,
    orchestrator: EventPipelineOrchestrator | None = None,
) -> None:
    """Consume clean events and project graph mutations using the orchestrator pipeline."""

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
            logger.error("Failed to start projection worker: %s", exc)
            return
        owns_consumer = True

    processor = EventProcessorService(orchestrator=orchestrator)
    projector = build_graph_projector(graph, classify=False)

    logger.info("Projection worker started with group_id %s", gid)
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

            envelope = processor.process_payload(
                payload,
                source="projection_worker",
                adapter="kafka",
                raw_payload=msg.value(),
                projector=projector,
            )
            if envelope.event and envelope.event.event_type not in VALID_EVENT_TYPES:
                envelope.outcome = PipelineOutcome.REJECTED
                envelope.stage = "project"
                envelope.reason = f"unknown_event_type:{envelope.event.event_type}"

            if envelope.outcome in {PipelineOutcome.REJECTED, PipelineOutcome.QUARANTINED}:
                logger.warning(
                    "Event rejected at %s stage [%s]: %s",
                    envelope.stage,
                    envelope.details.get("error_category", "processing_failure"),
                    envelope.reason,
                )
                continue
    except KeyboardInterrupt:  # pragma: no cover - manual interrupt
        logger.info("Projection worker shutting down")
    finally:
        if owns_consumer:
            consumer.close()


def main() -> None:
    """Bootstrap runtime resources and run the projection worker."""

    graph = create_graph()
    run_projection_worker(graph)


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()
