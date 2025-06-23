"""Utilities for syncing data between UME clusters."""

from __future__ import annotations

import json
import logging
import time
from threading import Event as ThreadEvent

from confluent_kafka import Consumer, Producer

from ume.config import Settings
from ume.event import Event

logger = logging.getLogger(__name__)


class ClusterReplicator:
    """Replicate raw events from a local cluster to a peer."""

    def __init__(self, local_settings: Settings, peer_bootstrap: str) -> None:
        self._local_settings = local_settings
        self._consumer = Consumer(
            {
                "bootstrap.servers": local_settings.KAFKA_BOOTSTRAP_SERVERS,
                "group.id": "ume_federation",
                "auto.offset.reset": "earliest",
            }
        )
        self._consumer.subscribe([local_settings.KAFKA_RAW_EVENTS_TOPIC])
        self._producer = Producer({"bootstrap.servers": peer_bootstrap})
        self._topic = local_settings.KAFKA_RAW_EVENTS_TOPIC
        self._stop = ThreadEvent()

    def replicate_once(self) -> None:
        """Replicate any available events once."""
        while True:
            msg = self._consumer.poll(0.1)
            if msg is None:
                break
            if msg.error():
                logger.error("Consumer error: %s", msg.error())
                continue
            try:
                data = json.loads(msg.value().decode("utf-8"))
                Event(**data)  # validate basic schema
            except Exception as exc:  # pragma: no cover - validation errors
                logger.warning("Invalid event skipped: %s", exc)
                continue
            self._producer.produce(self._topic, msg.value())
        self._producer.flush()

    def run(self, interval: float = 1.0) -> None:
        """Run continuously until :meth:`stop` is called."""
        while not self._stop.is_set():
            self.replicate_once()
            time.sleep(interval)

    def stop(self) -> None:
        self._stop.set()
        self._producer.flush()
        self._consumer.close()
