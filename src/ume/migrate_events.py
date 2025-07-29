"""Migrate stored events to the latest schema version."""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any, Dict, Iterable, Optional

from .config import settings
from .event_ledger import event_ledger, EventLedger
from .schema_utils import validate_event_dict
from .utils import ssl_config

try:
    from confluent_kafka import Consumer, KafkaError, KafkaException
except Exception:  # pragma: no cover - optional kafka
    Consumer = None
    KafkaError = None
    KafkaException = Exception

logger = logging.getLogger(__name__)

TARGET_VERSION = "2.0.0"


def _migrate_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Transform an event dictionary for ``TARGET_VERSION``."""
    etype = event.get("event_type")
    if etype in {"CREATE_EDGE", "DELETE_EDGE"}:
        label = event.get("label")
        if label == "L":
            event["label"] = "LINKS_TO"
        elif label == "TO_DELETE":
            return None
    return event


def _iter_ledger_events(ledger: EventLedger) -> Iterable[Dict[str, Any]]:
    for _, data in ledger.range():
        yield data


def _iter_kafka_events() -> Iterable[Dict[str, Any]]:
    if Consumer is None:
        raise RuntimeError("confluent-kafka is not installed")

    conf = {
        "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "group.id": "ume_migrate_events",
        "auto.offset.reset": "earliest",
    }
    conf.update(ssl_config())
    consumer = Consumer(conf)
    consumer.subscribe([settings.KAFKA_NODE_TOPIC, settings.KAFKA_EDGE_TOPIC])
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                break
            if msg.error():
                if KafkaError is None or msg.error().code() != KafkaError._PARTITION_EOF:
                    logger.warning("Kafka error: %s", msg.error())
                continue
            try:
                data = json.loads(msg.value().decode("utf-8"))
            except json.JSONDecodeError:
                logger.warning("Skipping malformed message")
                continue
            if isinstance(data, dict) and "event" in data:
                data = data["event"]
            yield data
    finally:
        consumer.close()


def migrate_events(source: str = "ledger") -> Iterable[Dict[str, Any]]:
    """Yield migrated events from ``source``."""
    if source == "kafka":
        events = _iter_kafka_events()
    else:
        events = _iter_ledger_events(event_ledger)

    for evt in events:
        new_evt = _migrate_event(evt)
        if new_evt is None:
            continue
        envelope = {"schema_version": TARGET_VERSION, "event": new_evt}
        try:
            validate_event_dict(envelope)
        except Exception as exc:  # pragma: no cover - shouldn't happen
            logger.warning("Invalid event skipped: %s", exc)
            continue
        yield envelope


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=["ledger", "kafka"],
        default="ledger",
        help="Read events from the local ledger or Kafka",
    )
    parser.add_argument(
        "--output",
        type=argparse.FileType("w"),
        default="-",
        help="File to write migrated events (default: stdout)",
    )
    args = parser.parse_args()

    for env in migrate_events(args.source):
        json.dump(env, args.output)
        args.output.write("\n")


if __name__ == "__main__":  # pragma: no cover - script entry point
    main()
