from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Iterable

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

from confluent_kafka import Producer, KafkaException

from ume.config import settings
from ume.event import Event, EventType

logger = logging.getLogger(__name__)


class DevLogHandler(FileSystemEventHandler):
    """Handle file modifications by publishing events to Kafka."""

    def __init__(self, producer: Producer) -> None:
        self.producer = producer

    def on_modified(self, event: FileSystemEvent) -> None:  # pragma: no cover - thin wrapper
        if event.is_directory:
            return
        payload = {"path": event.src_path}
        evt = Event(
            event_type=EventType.CREATE_NODE,
            timestamp=int(time.time()),
            node_id=str(event.src_path),
            payload={"node_id": str(event.src_path), "attributes": payload},
        )
        data = {
            "event_id": evt.event_id,
            "event_type": evt.event_type,
            "timestamp": evt.timestamp,
            "payload": evt.payload,
            "source": evt.source,
            "node_id": evt.node_id,
            "target_node_id": evt.target_node_id,
            "label": evt.label,
        }
        try:
            self.producer.produce(
                settings.KAFKA_RAW_EVENTS_TOPIC,
                json.dumps(data).encode("utf-8"),
            )
        except KafkaException as exc:  # pragma: no cover - logging only
            logger.error("Failed to produce dev log event: %s", exc)


def run_watcher(paths: Iterable[str]) -> None:
    """Start watching given paths until process exit."""

    producer = Producer({"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS})
    observer = Observer()
    handler = DevLogHandler(producer)
    for p in paths:
        observer.schedule(handler, str(Path(p)), recursive=True)
    observer.start()
    logger.info("Watching %s", list(paths))
    try:
        observer.join()
    finally:
        observer.stop()
        observer.join()
