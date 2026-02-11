"""Privacy agent for redacting PII from incoming events."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Tuple, cast

from confluent_kafka import Consumer, KafkaError, KafkaException, Producer
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

from ..audit import log_audit_entry
from ..config import settings
from ..event_ledger import event_ledger
from ..logging_utils import configure_logging
from ..policy.pipeline import PolicyContext, PolicyDecision, build_default_policy_pipeline
from ..plugins.alignment import PolicyViolationError, get_plugins, load_plugins
from ..tokenization import tokenize
from ..utils import event_to_camel, event_to_snake, ssl_config

__all__ = ["run_privacy_agent", "redact_event_payload", "PolicyViolationError"]

def _add_tokens(attrs: Dict[str, object]) -> None:
    """Tokenize textual fields and store the tokens list if any."""
    tokens: List[str] = []
    for key in ("name", "text", "content"):
        val = attrs.get(key)
        if isinstance(val, str):
            tokens.extend(tokenize(val))
    if tokens:
        attrs["tokens"] = tokens


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
    pipeline = build_default_policy_pipeline(
        redactor=redact_event_payload,
        plugin_loader=load_plugins,
        plugin_provider=get_plugins,
    )
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
            context = PolicyContext(source="kafka_privacy_agent", raw_payload=raw_bytes)
            result = pipeline.evaluate(context)

            if result.decision in {PolicyDecision.DENY, PolicyDecision.QUARANTINE}:
                logger.warning("Event quarantined by policy: %s", result.audit_event.reason)
                try:
                    if result.decision == PolicyDecision.DENY and context.transport_data is not None:
                        payload = {
                            "error": result.audit_event.reason,
                            "event": context.transport_data,
                        }
                        producer.produce(QUARANTINE_TOPIC, value=json.dumps(payload).encode("utf-8"))
                    else:
                        producer.produce(QUARANTINE_TOPIC, value=raw_bytes)
                    pending += 1
                except KafkaException as exc2:
                    logger.error("Failed to produce quarantine event: %s", exc2)
                continue

            if context.canonical_event is None:
                logger.error("Policy pipeline returned no canonical event")
                continue

            data = event_to_snake(event_to_camel(context.canonical_event))
            original_payload = context.transport_data.get("payload", {}) if context.transport_data else {}
            redacted_payload = context.event_payload
            was_redacted = context.redacted
            _add_tokens(redacted_payload)
            data["payload"] = redacted_payload

            try:
                producer.produce(
                    CLEAN_TOPIC,
                    value=json.dumps(event_to_camel(data)).encode("utf-8"),
                )
                pending += 1
                try:
                    event_ledger.append(msg.offset(), data)
                except ValueError as exc:  # pragma: no cover - offsets should be unique
                    logger.error("Ledger append failed: %s", exc)
            except KafkaException as exc:
                logger.error("Failed to produce sanitized event: %s", exc)

            if was_redacted:
                try:
                    producer.produce(
                        QUARANTINE_TOPIC,
                        value=json.dumps({"original": original_payload}).encode("utf-8"),
                    )
                    pending += 1
                except KafkaException as exc:
                    logger.error("Failed to produce quarantine event: %s", exc)
                log_audit_entry(os.getenv("UME_AGENT_ID", settings.UME_AGENT_ID), f"payload_redacted {data.get('event_id')}")

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
