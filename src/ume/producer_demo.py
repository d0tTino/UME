#!/usr/bin/env python3
"""A Kafka producer demo script that sends a sample event to a Redpanda/Kafka topic.

This script demonstrates the basic functionality of a Kafka producer, including
configuring the producer, sending a message, and handling delivery reports.
It's intended to be used with the corresponding consumer_demo.py script.
"""
import json
import logging
import time
from confluent_kafka import Producer, KafkaException

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("producer_demo")

# Kafka broker and topic
BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC = "ume_demo"

def delivery_report(err, msg):
    """ Called once for each message produced to indicate delivery result. """
    if err is not None:
        logger.error(f"Message delivery failed: {err}")
    else:
        logger.info(f"Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")

def main():
    """Creates a Kafka producer, constructs a sample event, and sends it.

    The producer is configured to connect to the BOOTSTRAP_SERVERS.
    A sample event dictionary is created, serialized to JSON, and then
    encoded to UTF-8. This event is then produced to the specified TOPIC.
    The script waits for the message to be delivered using producer.flush().
    """
    # Create Producer instance
    conf = {
        "bootstrap.servers": BOOTSTRAP_SERVERS
    }
    producer = Producer(conf)

    # Example event payload
    event = {
        "type": "demo_event",
        "timestamp": int(time.time()),
        "payload": {"message": "Hello from producer_demo!"}
    }
    data = json.dumps(event).encode("utf-8")

    logger.info(f"Producing event to topic '{TOPIC}': {event}")
    # Asynchronously produce a message, the delivery report callback will be triggered from poll()
    try:
        producer.produce(TOPIC, value=data, callback=delivery_report)
        # Wait for any outstanding messages to be delivered
        producer.flush()  # Block until all messages are sent/acknowledged or timeout occurs.
    except KafkaException as e:
        logger.error(f"Failed to produce message: {e}")

if __name__ == "__main__":
    main()
