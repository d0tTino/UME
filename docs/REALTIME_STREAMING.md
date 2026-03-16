# Real-time projection contract (SSE topic projection)

UME exposes a server-side real-time projection feed over **SSE** at:

- `GET /graph/digest/stream`
- `GET /dashboard/stream`

This endpoint is the canonical HTTP topic projection API for graph digest consumption.
`/dashboard/stream` is a dashboard-focused projection that emits sanitized high-churn panel state.

## Authentication

- Requires OAuth bearer token (`Authorization: Bearer <token>`).
- Uses the same auth flow as other API routes (`POST /auth/token`).

## Cursor and resume semantics

Clients can choose where to start consumption:

- `cursor` query parameter: absolute starting ledger offset.
- `max_events` query parameter (optional): cap emitted digest events, useful for bounded consumers/tests.
- `lastEventId` query parameter: last consumed SSE event ID; server resumes from `lastEventId + 1`.
- `Last-Event-ID` header: standard SSE reconnect header; takes precedence over `lastEventId` query parameter.

If both `cursor` and a reconnect marker are present, the server starts from the larger value.

## Event types

### `graph_digest`

Event payload follows `ume.realtime_contracts.GraphDigestEvent`.

```json
{
  "offset": 42,
  "event_id": "evt-123",
  "event_type": "CREATE_NODE",
  "source_service": "api",
  "schema_version": "3.0.0",
  "timestamp": 1730400000,
  "node_id": "n1",
  "target_node_id": null,
  "label": null,
  "payload_hash": "8f7d..."
}
```

### `control`

Control channel payload follows `ume.realtime_contracts.GraphDigestControlEvent`.

`kind` values:

- `heartbeat`: emitted while idle so clients can detect liveness.
- `backpressure`: emitted when the bounded queue dropped buffered events.

```json
{
  "kind": "backpressure",
  "cursor_offset": 120,
  "dropped_events": 8
}
```

### `dashboard_digest`

Dashboard payload follows `ume.realtime_contracts.DashboardDigestEvent`.

```json
{
  "cursor_offset": 120,
  "stats": {
    "node_count": 32,
    "edge_count": 71,
    "vector_index_size": 32
  },
  "recent_events": [
    {
      "offset": 120,
      "event_id": "evt-120",
      "event_type": "UPDATE_NODE_ATTRIBUTES",
      "payload_hash": "8f7d..."
    }
  ],
  "redacted_count": 11
}
```

`recent_events` contains graph digests only (event metadata + payload hash), never raw payload bodies.

## Backpressure behavior

The stream uses a bounded in-memory queue. When the consumer cannot keep up:

1. oldest buffered frame(s) are dropped,
2. server keeps streaming latest digest frames,
3. a `control`/`backpressure` event reports how many were dropped.

Clients should treat `backpressure` as a gap signal and resynchronize using the reported `cursor_offset`.

## Reconnection and backfill semantics

- Clients should persist the last consumed SSE `id` and reconnect with `Last-Event-ID`.
- Server resumes from `Last-Event-ID + 1`.
- If no reconnect marker is available, clients may use `cursor` for explicit backfill start.
- If both are supplied, the greater offset wins.
- On `control.kind=backpressure`, clients should treat local state as potentially stale and perform a REST catch-up (`/dashboard/stats`, `/dashboard/recent_events`, `/pii/redactions`) before continuing stream consumption.

## Transport notes

- SSE media type is `text/event-stream`.
- `id` field is set to the ledger offset for replay-safe resume.
- Message order is monotonic by ledger offset.
