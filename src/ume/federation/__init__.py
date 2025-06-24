"""Utilities for syncing data between UME clusters."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
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


class MirrorMakerDriver:
    """Run Kafka MirrorMaker 2 to replicate topics between clusters."""

    def __init__(self, source_bootstrap: str, target_bootstrap: str, topics: list[str]):
        self.source_bootstrap = source_bootstrap
        self.target_bootstrap = target_bootstrap
        self.topics = topics
        self._process: subprocess.Popen[bytes] | None = None
        self._config_file: Path | None = None

    def _create_config(self) -> Path:
        tmp = tempfile.NamedTemporaryFile("w", delete=False, suffix=".properties")
        tmp.write(
            """clusters = source,target
source.bootstrap.servers={source}
target.bootstrap.servers={target}

source->target.enabled=true
source->target.topics={topics}
""".format(
                source=self.source_bootstrap,
                target=self.target_bootstrap,
                topics=",".join(self.topics),
            )
        )
        tmp.close()
        return Path(tmp.name)

    def start(self) -> None:
        if self._process:
            raise RuntimeError("MirrorMaker already running")
        self._config_file = self._create_config()
        cmd = [
            "docker",
            "run",
            "--rm",
            "--network=host",
            "-v",
            f"{self._config_file}:/etc/mm2.properties:ro",
            "confluentinc/cp-kafka:latest",
            "bash",
            "-c",
            "connect-mirror-maker /etc/mm2.properties",
        ]
        self._process = subprocess.Popen(cmd)

    def stop(self) -> None:
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except Exception:
                self._process.kill()
        if self._config_file and self._config_file.exists():
            os.unlink(self._config_file)
        self._process = None
        self._config_file = None

    def status(self) -> str:
        if not self._process:
            return "stopped"
        return "running" if self._process.poll() is None else "stopped"


__all__ = ["ClusterReplicator", "MirrorMakerDriver"]
