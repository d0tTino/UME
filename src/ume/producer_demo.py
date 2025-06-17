#!/usr/bin/env python3
"""A Kafka producer demo script that sends a sample event to a Redpanda/Kafka topic.

This script demonstrates the basic functionality of a Kafka producer, including
configuring the producer, sending a message, and handling delivery reports.
It's intended to be used with the corresponding consumer_demo.py script.
"""

import json
import logging
from ume.utils import ssl_config
from ume.config import settings
from ume.logging_utils import configure_logging
import time
from confluent_kafka import Producer, KafkaException  # type: ignore
from ume import Event
from ume.schema_utils import validate_event_dict
from jsonschema import ValidationError

configure_logging()
logger = logging.getLogger("producer_demo")

# Kafka broker and topic
# Set KAFKA_CA_CERT, KAFKA_CLIENT_CERT and KAFKA_CLIENT_KEY to enable TLS.
BOOTSTRAP_SERVERS = settings.KAFKA_BOOTSTRAP_SERVERS
TOPIC = settings.KAFKA_RAW_EVENTS_TOPIC


def delivery_report(err, msg):
    """Called once for each message produced to indicate delivery result."""
    if err is not None:
        logger.error(f"Message delivery failed: {err}")
    else:
        logger.info(
            f"Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}"
        )


def main():
    """Creates a Kafka producer, constructs a sample event, and sends it.

    The producer is configured to connect to the BOOTSTRAP_SERVERS.
    A sample event dictionary is created, serialized to JSON, and then
    encoded to UTF-8. This event is then produced to the specified TOPIC.
    The script waits for the message to be delivered using producer.flush().
    """
    # Create Producer instance
    conf = {"bootstrap.servers": BOOTSTRAP_SERVERS}
    conf.update(ssl_config())
    producer = Producer(conf)

    # Construct an Event instance
    event_payload_data = {"message": "Hello from producer_demo with Event class!"}
    event_to_send = Event(
        event_type="demo_event",
        timestamp=int(time.time()),
        payload=event_payload_data,
        source="producer_demo",  # Add source
    )

    # Convert Event object to dict for JSON serialization
    data_dict = {
        "event_id": event_to_send.event_id,
        "event_type": event_to_send.event_type,
        "timestamp": event_to_send.timestamp,
        "payload": event_to_send.payload,
        "source": event_to_send.source,
    }

    try:
        validate_event_dict(data_dict)
    except ValidationError as e:
        logger.error("Event failed schema validation: %s", e)
        return

    data = json.dumps(data_dict).encode("utf-8")

    logger.info(f"Producing event object to topic '{TOPIC}': {event_to_send}")
    # Asynchronously produce a message, the delivery report callback will be triggered from poll()
    try:
        producer.produce(TOPIC, value=data, callback=delivery_report)
        # Wait for any outstanding messages to be delivered
        producer.flush()  # Block until all messages are sent/acknowledged or timeout occurs.
    except KafkaException as e:
        logger.error(f"Failed to produce message: {e}")


if __name__ == "__main__":
    main()
