"""Privacy agent for redacting PII from incoming events."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Tuple, List, cast
from ..utils import ssl_config
from ..logging_utils import configure_logging

from confluent_kafka import Consumer, Producer, KafkaException, KafkaError
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from jsonschema import ValidationError

from ..config import settings
from ..schema_utils import validate_event_dict
from ..audit import log_audit_entry
from ..event import parse_event, EventError
from ..consent_ledger import consent_ledger
from ..plugins.alignment import load_plugins, get_plugins, PolicyViolationError


configure_logging()
logger = logging.getLogger(__name__)


BOOTSTRAP_SERVERS = settings.KAFKA_BOOTSTRAP_SERVERS
RAW_TOPIC = settings.KAFKA_RAW_EVENTS_TOPIC
CLEAN_TOPIC = settings.KAFKA_CLEAN_EVENTS_TOPIC
QUARANTINE_TOPIC = settings.KAFKA_QUARANTINE_TOPIC
GROUP_ID = settings.KAFKA_PRIVACY_AGENT_GROUP_ID
BATCH_SIZE = settings.KAFKA_PRODUCER_BATCH_SIZE

# Initialize Presidio engines
_ANALYZER = AnalyzerEngine()
_ANONYMIZER = AnonymizerEngine()


def redact_event_payload(
    payload_dict: Dict[str, object],
) -> Tuple[Dict[str, object], bool]:
    """Redact PII from a payload dict using Presidio.

    Returns a tuple of (redacted_payload, was_redacted).
    """
    text = json.dumps(payload_dict)
    results = _ANALYZER.analyze(text=text, language="en")
    if not results:
        return payload_dict, False

    anonymized = _ANONYMIZER.anonymize(
        text=text, analyzer_results=cast(List[Any], results)
    )
    try:
        new_payload = json.loads(anonymized.text)
    except json.JSONDecodeError:
        # Fall back to returning original if structure broke
        return payload_dict, False

    return new_payload, True


def run_privacy_agent() -> None:
    """Consume raw events, redact payloads, and produce sanitized versions."""
    load_plugins()
    consumer_conf = {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "group.id": GROUP_ID,
        "auto.offset.reset": "earliest",
    }
    consumer_conf.update(ssl_config())
    consumer = Consumer(consumer_conf)
    consumer.subscribe([RAW_TOPIC])

    producer_conf = {"bootstrap.servers": BOOTSTRAP_SERVERS}
    producer_conf.update(ssl_config())
    producer = Producer(producer_conf)

    logger.info("Privacy agent started, listening on %s", RAW_TOPIC)

    pending = 0
    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    logger.error("Kafka error: %s", msg.error())
                continue

            raw_bytes = msg.value()
            try:
                data = json.loads(raw_bytes.decode("utf-8"))
                validate_event_dict(data)
            except (json.JSONDecodeError, ValidationError) as exc:
                logger.error("Invalid event received: %s", exc)
                try:
                    producer.produce(QUARANTINE_TOPIC, value=raw_bytes)
                    pending += 1
                except KafkaException as exc2:
                    logger.error("Failed to produce quarantine event: %s", exc2)
                continue

            try:
                event = parse_event(data)
            except EventError as exc:
                logger.error("Failed to parse event: %s", exc)
                try:
                    producer.produce(QUARANTINE_TOPIC, value=raw_bytes)
                    pending += 1
                except KafkaException as exc2:
                    logger.error("Failed to produce quarantine event: %s", exc2)
                continue

            payload = event.payload if isinstance(event.payload, dict) else {}
            user_id = payload.get("user_id")
            scope = payload.get("scope")
            has_consent = False
            if user_id and scope:
                has_consent = consent_ledger.has_consent(str(user_id), str(scope))
            setattr(event, "consent", has_consent)

            try:
                for plugin in get_plugins():
                    plugin.validate(event)
            except PolicyViolationError as exc:
                logger.warning("Event rejected by policy: %s", exc)
                try:
                    producer.produce(
                        QUARANTINE_TOPIC,
                        value=json.dumps({"error": str(exc), "event": data}).encode(
                            "utf-8"
                        ),
                    )
                    pending += 1
                except KafkaException as exc2:
                    logger.error("Failed to produce quarantine event: %s", exc2)
                continue

            original_payload = data.get("payload", {})
            redacted_payload, was_redacted = redact_event_payload(original_payload)
            data["payload"] = redacted_payload

            dest_topic = CLEAN_TOPIC if has_consent else QUARANTINE_TOPIC

            try:
                producer.produce(dest_topic, value=json.dumps(data).encode("utf-8"))
                pending += 1
            except KafkaException as exc:
                logger.error("Failed to produce sanitized event: %s", exc)

            if was_redacted:
                try:
                    producer.produce(
                        QUARANTINE_TOPIC,
                        value=json.dumps({"original": original_payload}).encode(
                            "utf-8"
                        ),
                    )
                    pending += 1
                except KafkaException as exc:
                    logger.error("Failed to produce quarantine event: %s", exc)
                user_id = settings.UME_AGENT_ID
                log_audit_entry(user_id, f"payload_redacted {data.get('event_id')}")
            if pending >= BATCH_SIZE:
                producer.flush()
                pending = 0
    except KeyboardInterrupt:
        logger.info("Privacy agent shutting down")
    finally:
        producer.flush()
        consumer.close()


if __name__ == "__main__":
    run_privacy_agent()
