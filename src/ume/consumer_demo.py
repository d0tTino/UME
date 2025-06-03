#!/usr/bin/env python3
"""A Kafka consumer demo script that subscribes to a Redpanda/Kafka topic and logs received events.

This script demonstrates the basic functionality of a Kafka consumer, including
configuring the consumer, subscribing to a topic, polling for messages,
and handling potential errors. It's intended to be used with the
corresponding producer_demo.py script.
"""
import json
import logging
from confluent_kafka import Consumer, KafkaException, KafkaError
from ume import parse_event, EventError # Import parse_event and EventError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("consumer_demo")

# Kafka broker and topic
BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC = "ume_demo"
GROUP_ID = "ume_demo_group"

def main():
    """Creates a Kafka consumer, subscribes to a topic, and processes messages.

    The consumer is configured with BOOTSTRAP_SERVERS, GROUP_ID, and
    auto.offset.reset policy. It subscribes to the specified TOPIC.
    The script then enters an infinite loop, polling for new messages.
    Received messages are decoded, deserialized from JSON, and logged.
    The loop handles Kafka errors and provides a graceful shutdown
    on KeyboardInterrupt or other Kafka exceptions.
    """
    # Create Consumer instance
    conf = {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "group.id": GROUP_ID,
        "auto.offset.reset": "earliest"  # Start reading from the beginning of the topic
    }
    consumer = Consumer(conf)
    consumer.subscribe([TOPIC])

    logger.info(f"Subscribed to topic '{TOPIC}', waiting for messages...")

    try:
        while True:
            # Poll for new messages; timeout ensures the loop doesn't block indefinitely if no messages.
            msg = consumer.poll(timeout=1.0)  # Poll for messages with a 1-second timeout
            if msg is None:
                continue  # No message, poll again
            if msg.error():
                # Error or event
                # _PARTITION_EOF is not an error but an informational event from the broker.
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    # End of partition event (not necessarily an error)
                    logger.info(f"Reached end of partition for {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")
                    continue
                else:
                    # Actual error
                    logger.error(f"Kafka error: {msg.error()}")
                    raise KafkaException(msg.error())
            
            # Proper message
            data = msg.value().decode("utf-8")
            try:
                event_data_dict = json.loads(data)
                received_event = parse_event(event_data_dict)
                logger.info(f"Received event object: {received_event}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON: {data}, error: {e}")
            except EventError as e:
                logger.error(f"Failed to parse event: {data}, error: {e}")

    except KeyboardInterrupt:
        logger.info("Interrupted by user, closing consumer.")
    except KafkaException as e:
        logger.error(f"Kafka related error: {e}")
    finally:
        # Cleanly close the consumer
        consumer.close()
        logger.info("Consumer closed.")

if __name__ == "__main__":
    main()
