#!/usr/bin/env python3
"""Produce and consume events on Redpanda, reporting p99 latency."""

from __future__ import annotations

import argparse
import json
import threading
import time
from statistics import quantiles

from confluent_kafka import Consumer, KafkaError, KafkaException, Producer

from ume.config import settings
from ume.event import Event
from ume.logging_utils import configure_logging
from ume.utils import ssl_config


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--num-events",
        type=int,
        default=1000,
        help="Number of events to send",
    )
    parser.add_argument(
        "--topic",
        default=settings.KAFKA_RAW_EVENTS_TOPIC,
        help="Kafka topic to use",
    )
    parser.add_argument(
        "--bootstrap",
        default=settings.KAFKA_BOOTSTRAP_SERVERS,
        help="Kafka bootstrap servers",
    )
    parser.add_argument(
        "--group-id",
        default="benchmark-redpanda",
        help="Consumer group id",
    )
    args = parser.parse_args()

    prod_conf = {"bootstrap.servers": args.bootstrap}
    prod_conf.update(ssl_config())
    producer = Producer(prod_conf)

    cons_conf = {
        "bootstrap.servers": args.bootstrap,
        "group.id": args.group_id,
        "auto.offset.reset": "earliest",
    }
    cons_conf.update(ssl_config())
    consumer = Consumer(cons_conf)
    consumer.subscribe([args.topic])

    latencies: list[float] = []
    done = threading.Event()

    def _consume() -> None:
        while len(latencies) < args.num_events:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise KafkaException(msg.error())
            data = json.loads(msg.value().decode("utf-8"))
            sent_ts = data["timestamp"]
            latencies.append(time.perf_counter() - sent_ts)
        done.set()

    thread = threading.Thread(target=_consume)
    thread.start()

    for _ in range(args.num_events):
        evt = Event(
            event_type="benchmark",
            timestamp=time.perf_counter(),
            payload={"payload": "x"},
            source="benchmark",
        )
        producer.produce(args.topic, json.dumps(evt.__dict__).encode("utf-8"))
    producer.flush()

    done.wait(timeout=30)
    consumer.close()
    thread.join()

    if latencies:
        p99 = quantiles(latencies, n=100)[98]
        print(f"p99 latency: {p99*1000:.2f} ms")
    else:
        print("No messages consumed")


if __name__ == "__main__":
    main()

