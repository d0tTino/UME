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

TARGET_VERSION = "3.0.0"

_DEPRECATED_EDGE_LABELS = {
    "REMEMBERS",
    "ASSOCIATED_WITH",
    "CAUSES",
    "LINKS_TO",
    "CONNECTS_TO",
    "RELATES_TO",
}


def _migrate_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Transform an event dictionary for ``TARGET_VERSION``."""
    etype = event.get("event_type") or event.get("eventType")
    if etype in {"CREATE_EDGE", "DELETE_EDGE"}:
        label = event.get("label")
        if label == "L":
            label = "LINKS_TO"
            event["label"] = label

        if label == "NEW_LABEL":
            label = "TAGGED_AS"
            event["label"] = label

        if label == "HAS_PERMISSION":
            payload = event.get("payload")
            if not isinstance(payload, dict):
                payload = {}
            attrs = payload.get("attributes")
            if not isinstance(attrs, dict):
                attrs = {}

            perm_level = attrs.get("permission_level")
            if not isinstance(perm_level, str) or not perm_level:
                perm_level = "viewer"
            new_label = "OWNED_BY" if perm_level == "editor" else "SHARED_WITH"

            attrs["permission_level"] = perm_level
            payload["attributes"] = attrs
            event["payload"] = payload
            event["label"] = new_label
            label = new_label

        if label in _DEPRECATED_EDGE_LABELS or label == "TO_DELETE":
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
        if isinstance(evt, dict) and "event" in evt and isinstance(evt["event"], dict):
            evt = evt["event"]
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
