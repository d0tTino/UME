import json
import logging
from typing import Iterator

from confluent_kafka import Consumer, Producer, KafkaError, KafkaException  # type: ignore

from .event import Event, parse_event


logger = logging.getLogger(__name__)


class UMEClient:
    """Simple Kafka-based client for producing and consuming UME events."""

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = "ume_demo",
        group_id: str = "ume_client_group",
    ) -> None:
        self.topic = topic
        self.producer = Producer({"bootstrap.servers": bootstrap_servers})
        self.consumer = Consumer(
            {
                "bootstrap.servers": bootstrap_servers,
                "group.id": group_id,
                "auto.offset.reset": "earliest",
            }
        )
        self.consumer.subscribe([topic])

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
        self.producer.produce(self.topic, json.dumps(data_dict).encode("utf-8"))
        self.producer.flush()

    def consume_events(self, timeout: float = 1.0) -> Iterator[Event]:
        """Yield Events from the configured topic until no message is available."""
        while True:
            msg = self.consumer.poll(timeout)
            if msg is None:
                break
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    break
                raise KafkaException(msg.error())
            data = json.loads(msg.value().decode("utf-8"))
            yield parse_event(data)
