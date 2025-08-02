# Projection Engine

`ume.projection_engine` consumes sanitized events from Kafka and applies them to the configured graph adapter. It keeps the local graph in sync with the latest events published by the Privacy Agent.

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
