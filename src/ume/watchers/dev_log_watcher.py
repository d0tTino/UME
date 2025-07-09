from __future__ import annotations

import json
import logging
import signal
import time
from types import FrameType
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


def run_watcher(paths: Iterable[str], runtime: float | None = None) -> None:
    """Start watching given paths until process exit.

    Parameters
    ----------
    paths:
        Iterable of filesystem paths to watch.
    runtime:
        Optional duration in seconds to run before stopping. ``None`` (default)
        runs indefinitely until interrupted.
    """

    producer = Producer({"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS})
    observer = Observer()
    handler = DevLogHandler(producer)
    watched_paths: list[str] = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            logger.warning("Path %s does not exist, skipping", path)
            continue
        observer.schedule(handler, str(path), recursive=True)
        watched_paths.append(str(path))
    if not watched_paths:
        logger.warning("No existing paths to watch; exiting")
        return
    observer.start()
    logger.info("Watching %s", watched_paths)

    should_stop = False

    def handle_signal(signum: int, _frame: FrameType | None) -> None:
        nonlocal should_stop
        logger.info("Stopping watcher due to signal %s", signum)
        should_stop = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        end_time = None if runtime is None else time.time() + runtime
        while not should_stop:
            if end_time is not None and time.time() >= end_time:
                break
            time.sleep(1)
    except KeyboardInterrupt:  # pragma: no cover - manual interrupt
        logger.info("Stopping watcher due to keyboard interrupt")
        observer.join()
    finally:
        observer.stop()
        producer.flush()
        try:
            observer.join()
        except KeyboardInterrupt:
            observer.join()
            raise
