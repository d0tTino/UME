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


4. If you plan to run the Docker Compose stack, bootstrap runtime secrets first:
   ```
   export NEO4J_PASSWORD=<your-neo4j-password>
   export UME_API_TOKEN=<your-api-token>
   export UME_OAUTH_PASSWORD=<your-oauth-password>
   # Optional when using SASL: export KAFKA_SASL_PASSWORD=<your-kafka-password>
   ./scripts/bootstrap_docker_secrets.sh
   ```

5. In one terminal, start the demo consumer:
   ```
   python -m ume.consumer_demo
   ```

6. In another terminal, publish a typed demo event:
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

## Backend configuration terms (current)

When you move from demo scripts to API/projection deployments:

- Set `UME_GRAPH_BACKEND` and create graph adapters via `create_graph_adapter()`.
- Set `UME_VECTOR_BACKEND` and create vector stores via `create_vector_store()`.
- Custom backends are loaded through plugin entry points:
  - `ume.graph_adapters`
  - `ume.vector_backends`

## Concept Mapping (legacy -> current)

| Legacy term | Current term/API |
| --- | --- |
| `UME_GRAPH_ADAPTER` | `UME_GRAPH_BACKEND` |
| `get_adapter(...)` | `create_graph_adapter(...)` |
