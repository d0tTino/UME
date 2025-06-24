# Angel Bridge

`AngelBridge` consumes recent events and emits a short daily summary. This can be
used to keep external services informed about the system's activity without
exposing the full event stream.

The implementation included here is a stub which counts events in a given
lookback window. Real deployments might query a database or message queue and
post the resulting summary to another service.

## Configuration

`AngelBridge` reads its defaults from environment variables via `Settings`:

- `ANGEL_BRIDGE_LOOKBACK_HOURS` – number of hours to consider when generating the summary (defaults to `24`).

These can be set in your environment or `.env` file.
