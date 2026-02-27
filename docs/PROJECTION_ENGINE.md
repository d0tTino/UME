# Projection Engine

`ume.projection_engine` consumes sanitized events from Kafka and applies them to the configured graph adapter. It keeps the local graph in sync with the latest events published by the Privacy Agent.

## Deterministic projection rules

Projection is deterministic when the same ordered event stream is replayed:

1. Events are parsed through the policy pipeline before projection.
2. Any invalid event is mapped to one explicit outcome: `reject`, `quarantine`, or `dead_letter`.
3. Invalid events are serialized into the event ledger as `REJECTED_EVENT` records for audit/replay parity.
4. Graph state changes are performed only by `apply_event_to_graph` handler execution.
5. Projection/replay skips unknown or otherwise non-applicable events and continues in offset order.

## Configuration

The engine reads the following settings from `Settings`:

- `KAFKA_BOOTSTRAP_SERVERS` &ndash; comma separated list of brokers.
- `KAFKA_CLEAN_EVENTS_TOPIC` &ndash; topic containing sanitized events.
- `KAFKA_GROUP_ID` &ndash; consumer group used for the projection engine.

These may be provided in your environment or a `.env` file:

```bash
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_CLEAN_EVENTS_TOPIC=ume-clean-events
KAFKA_GROUP_ID=ume_client_group
```

## Running under systemd

```ini
[Unit]
Description=UME Projection Engine
After=network.target

[Service]
EnvironmentFile=/opt/ume/.env
ExecStart=/opt/ume/.venv/bin/ume-projection
Restart=always

[Install]
WantedBy=multi-user.target
```

## Docker Compose

```yaml
  ume-projection:
    image: ume:latest
    command: ume-projection
    env_file: ./ume.env
    depends_on:
      - redpanda
```
