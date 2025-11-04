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
from .schema_manager import DEFAULT_SCHEMA_MANAGER

try:
    from confluent_kafka import Consumer, KafkaError, KafkaException
except Exception:  # pragma: no cover - optional kafka
    Consumer = None
    KafkaError = None
    KafkaException = Exception

logger = logging.getLogger(__name__)

TARGET_VERSION = "3.0.0"

try:
    TARGET_SCHEMA = DEFAULT_SCHEMA_MANAGER.get_schema(TARGET_VERSION)
except Exception:  # pragma: no cover - optional schema resources missing
    TARGET_SCHEMA = None

_DEPRECATED_EDGE_LABELS = {
    "REMEMBERS",
    "ASSOCIATED_WITH",
    "CAUSES",
    "LINKS_TO",
    "CONNECTS_TO",
    "RELATES_TO",
}

_EDGE_FALLBACKS: Dict[str, Dict[str, Any]] = {
    "OWNED_BY": {
        "permission_level": "editor",
        "accepted_values": ("viewer", "editor"),
        "schema_version": TARGET_VERSION,
    },
    "SHARED_WITH": {
        "permission_level": "viewer",
        "accepted_values": ("viewer", "editor"),
        "schema_version": TARGET_VERSION,
    },
    "TAGGED_AS": {"permission_level": None, "accepted_values": (), "schema_version": TARGET_VERSION},
    "INVITES": {"permission_level": None, "accepted_values": (), "schema_version": TARGET_VERSION},
    "CONSIDERS": {
        "permission_level": None,
        "accepted_values": (),
        "schema_version": TARGET_VERSION,
    },
}


def _ensure_payload(event: Dict[str, Any]) -> Dict[str, Any]:
    payload = event.get("payload")
    if not isinstance(payload, dict):
        payload = {}
        event["payload"] = payload
    return payload


def _extract_edge_attributes(payload: Dict[str, Any]) -> tuple[Dict[str, Any], Optional[str]]:
    raw_attrs = payload.get("attributes")
    permission_hint: Optional[str] = None
    if isinstance(raw_attrs, dict):
        attr_dict = dict(raw_attrs)
        perm_val = attr_dict.get("permission_level")
        if isinstance(perm_val, str) and perm_val.strip():
            permission_hint = perm_val.strip()
    elif isinstance(raw_attrs, str):
        attr_dict = {}
        if raw_attrs.strip():
            permission_hint = raw_attrs.strip()
    else:
        attr_dict = {}
    if permission_hint is None:
        raw_perm = payload.get("permission_level")
        if isinstance(raw_perm, str) and raw_perm.strip():
            permission_hint = raw_perm.strip()
    attr_dict.pop("version", None)
    attr_dict.pop("schema_version", None)
    return attr_dict, permission_hint


def _edge_metadata(label: str) -> Optional[tuple[Optional[str], tuple[str, ...], str]]:
    if TARGET_SCHEMA is not None and label in TARGET_SCHEMA.edge_labels:
        edge_def = TARGET_SCHEMA.edge_labels[label]
        return (
            edge_def.permission_level,
            edge_def.permission_level_values,
            edge_def.version,
        )
    fallback = _EDGE_FALLBACKS.get(label)
    if fallback is not None:
        return (
            fallback.get("permission_level"),
            tuple(fallback.get("accepted_values", ())),
            str(fallback.get("schema_version", TARGET_VERSION)),
        )
    return None


def _apply_edge_defaults(
    attrs: Dict[str, Any], label: str
) -> Dict[str, Any]:
    metadata = _edge_metadata(label)
    if metadata is None:
        return attrs

    updated_attrs = dict(attrs)
    perm_default, accepted_values, schema_version = metadata
    perm_value = updated_attrs.get("permission_level")
    if perm_default is not None:
        if not isinstance(perm_value, str) or not perm_value.strip():
            perm_value = perm_default
        else:
            accepted = set(accepted_values)
            if accepted and perm_value not in accepted:
                perm_value = perm_default
        updated_attrs["permission_level"] = perm_value
    else:
        if not perm_value:
            updated_attrs.pop("permission_level", None)

    updated_attrs["schema_version"] = schema_version
    return updated_attrs


def _normalize_permission_value(value: Optional[str]) -> Optional[str]:
    if isinstance(value, str):
        trimmed = value.strip()
        if trimmed:
            return trimmed
    return None


def _migrate_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Transform an event dictionary for ``TARGET_VERSION``."""

    etype = event.get("event_type") or event.get("eventType")
    if etype not in {"CREATE_EDGE", "DELETE_EDGE"}:
        return event

    label = event.get("label")
    if not isinstance(label, str):
        return event

    if label == "TO_DELETE":
        return None
    if label == "L":
        label = "LINKS_TO"

    payload = _ensure_payload(event)
    attrs, perm_hint = _extract_edge_attributes(payload)

    if label == "NEW_LABEL":
        label = "TAGGED_AS"
    elif label == "HAS_PERMISSION":
        perm_value = attrs.get("permission_level")
        normalized_perm = _normalize_permission_value(
            perm_value if isinstance(perm_value, str) else perm_hint
        )
        if normalized_perm is not None:
            attrs["permission_level"] = normalized_perm
        else:
            attrs.pop("permission_level", None)

        label = "OWNED_BY" if normalized_perm == "editor" else "SHARED_WITH"
    event["label"] = label

    if label in _DEPRECATED_EDGE_LABELS:
        return None

    if _edge_metadata(label) is None:
        return None

    if etype == "CREATE_EDGE":
        payload.pop("permission_level", None)
        normalized_attrs = _apply_edge_defaults(attrs, label)
        payload["attributes"] = normalized_attrs

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
