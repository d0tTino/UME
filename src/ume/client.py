import json
import logging
from typing import Iterator

from confluent_kafka import Consumer, Producer, KafkaError  # type: ignore
from jsonschema import ValidationError
from .config import Settings

from .event import Event, parse_event
from .embedding import generate_embedding
from .schema_utils import validate_event_dict


class UMEClientError(Exception):
    """Exception raised for errors occurring within :class:`UMEClient`."""

    pass


logger = logging.getLogger(__name__)


class UMEClient:
    """Simple Kafka-based client for producing and consuming UME events."""

    def __init__(self, settings: Settings) -> None:
        self.produce_topic = settings.KAFKA_RAW_EVENTS_TOPIC
        self.consume_topic = settings.KAFKA_CLEAN_EVENTS_TOPIC
        bootstrap = settings.KAFKA_BOOTSTRAP_SERVERS
        group_id = settings.KAFKA_GROUP_ID
        self.producer = Producer({"bootstrap.servers": bootstrap})
        self.consumer = Consumer(
            {
                "bootstrap.servers": bootstrap,
                "group.id": group_id,
                "auto.offset.reset": "earliest",
            }
        )
        self.consumer.subscribe([self.consume_topic])

    def produce_event(self, event: Event) -> None:
        """Serialize and send an Event to the configured topic."""
        data_dict = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "timestamp": event.timestamp,
            "payload": event.payload,
            "source": event.source,
            "node_id": event.node_id,
            "target_node_id": event.target_node_id,
            "label": event.label,
        }
        try:
            validate_event_dict(data_dict)
            self.producer.produce(
                self.produce_topic, json.dumps(data_dict).encode("utf-8")
            )
            self.producer.flush()
        except ValidationError as e:
            logger.error("Event validation failed: %s", e.message)
            raise UMEClientError(f"Event validation failed: {e.message}") from e
        except (
            Exception
        ) as e:  # pragma: no cover - confluent_kafka may raise various errors
            logger.error("Failed to produce event: %s", e)
            raise UMEClientError(f"Failed to produce event: {e}") from e

    def consume_events(self, timeout: float = 1.0) -> Iterator[Event]:
        """Yield Events from the configured topic until no message is available."""
        while True:
            msg = self.consumer.poll(timeout)
            if msg is None:
                break
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    break
                raise UMEClientError(f"Consumer error: {msg.error()}")
            data = json.loads(msg.value().decode("utf-8"))
            payload = data.get("payload")
            if isinstance(payload, dict):
                text_values = [v for v in payload.values() if isinstance(v, str)]
                if text_values:
                    payload["embedding"] = generate_embedding(" ".join(text_values))
            yield parse_event(data)

    def close(self) -> None:
        """Flush the producer and close the consumer."""
        try:
            self.producer.flush()
        finally:
            self.consumer.close()

    def __enter__(self) -> "UMEClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
