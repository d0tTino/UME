# Angel Bridge

`AngelBridge` consumes recent sanitized events and emits a short daily summary.
The service keeps external systems informed about activity without exposing the
full event stream.

Events are retrieved from the local SQLite based `event_ledger` that is filled
by the privacy agent. If Kafka is configured, the bridge will read directly from
the clean events topic instead. The returned summary aggregates the number of
events for each `event_type`.

Example output::

    Summary for 2024-05-08:
    CREATE_NODE: 2
    CREATE_EDGE: 1

## Configuration

`AngelBridge` reads its defaults from environment variables via `Settings`:

- `ANGEL_BRIDGE_LOOKBACK_HOURS` – number of hours to consider when generating the summary (defaults to `24`).

These can be set in your environment or `.env` file.
