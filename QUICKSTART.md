# Quickstart for UME

This quickstart shows how to run a simple producer and consumer locally.

## Prerequisites

- Python 3.10+
- Docker (optional for Redpanda)

## Steps

1. Clone the repository and navigate into it:
   ```
   git clone https://github.com/d0tTino/UME.git
   cd UME
   ```

2. Create a virtual environment and install dependencies:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

3. Run Redpanda in Docker (or use another Kafka-compatible broker):
   ```
   docker run -d -p 9092:9092 -p 9644:9644 --name redpanda docker.redpanda.com/vectorized/redpanda:latest redpanda start
   ```

4. In one terminal, start the demo consumer:
   ```
   python -m ume.consumer_demo
   ```

5. In another terminal, publish a typed demo event:
   ```
   python -m ume.producer_demo
   ```

### Demo integration path (producer -> consumer)

The demo scripts are wired for direct end-to-end flow with no intermediate
processor required:

```
producer_demo.py
  -> topic: KAFKA_RAW_EVENTS_TOPIC
  -> consumer_demo.py
```

Expected behavior:

- `producer_demo.py` publishes a schema-valid `CREATE_NODE` event.
- `consumer_demo.py` subscribes to the same raw topic and parses each message
  through `ingest_transport_payload(..., adapter="kafka")` before logging the
  parsed `Event`.
