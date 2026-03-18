# Frontend architecture

This document describes UI architecture in a framework-neutral way, then records the concrete framework choice for this repository.

## Framework-neutral architecture

### Goals

- Keep presentation, data access, and state management separated.
- Make API integration explicit and testable.
- Preserve portability to any SPA-capable framework.

### Layers

1. **View layer**
   - Renders pages/components.
   - Delegates side effects to hooks/services.
2. **State layer**
   - Stores session/auth state and view model state.
   - Exposes deterministic update functions.
3. **Data access layer**
   - Encapsulates HTTP + streaming transport calls to UME backend.
   - Handles token attachment, retries, and stream resume policy.
4. **Domain utilities**
   - Pure helpers for shaping backend payloads into view models.

### Real-time consumption pattern

- Use a stream client abstraction for `GET /graph/digest/stream`.
- Use a dashboard stream client abstraction for `GET /dashboard/stream` to drive high-churn panels (`stats`, `recent_events`, PII redaction count).
- Persist last processed event ID per session to support reconnection.
- Treat `control.backpressure` events as data-loss signals and trigger a catch-up flow.
- Keep REST compatibility paths (`/dashboard/stats`, `/dashboard/recent_events`, `/pii/redactions`) for explicit refresh and stream fallback.

### Formal transport contract

The canonical dashboard real-time contract is transport-neutral even though the currently deployed backend endpoint is SSE-first.
Any future transport, including WebSocket, must preserve the same auth, replay, and payload semantics.

#### Supported transports

- **SSE (canonical production transport):** `GET /dashboard/stream` with `Accept: text/event-stream`.
- **WebSocket (migration/reference transport):** clients may bind the same event envelope to a WebSocket endpoint when the backend advertises one. Transport swaps must not require view-layer rewrites.

#### Authentication model

- Every transport uses the same bearer token obtained from `POST /auth/token`.
- SSE clients send `Authorization: Bearer <token>`.
- WebSocket clients must forward the same bearer token during the handshake using a negotiated subprotocol, header, or equivalent server-approved handshake mechanism.
- Auth failures are terminal for the current connection attempt and should not mutate the replay cursor.

#### Replay semantics

- `lastEventId` is the canonical replay cursor and always represents the most recently processed stream event ID.
- For SSE, clients send the cursor using the standard `Last-Event-ID` header; the query parameter `lastEventId` is a compatibility fallback.
- When both are supplied, `Last-Event-ID` takes precedence.
- Server replay resumes at `lastEventId + 1`.
- If both `cursor` and a replay cursor are provided, the server starts at the greater offset.
- Clients must persist the last acknowledged event ID only after a digest or control event has been parsed successfully.
- `control.kind=backpressure` indicates a gap; clients must refresh via REST before treating the stream as current again.

#### Event envelope schema

All transports must emit the same logical envelope before framework-specific mapping:

```json
{
  "event": "dashboard_digest",
  "id": "42",
  "data": {
    "cursor_offset": 42,
    "stats": {
      "node_count": 32,
      "edge_count": 71,
      "vector_index_size": 32
    },
    "recent_events": [
      {
        "offset": 42,
        "event_id": "evt-42",
        "event_type": "UPDATE_NODE_ATTRIBUTES",
        "payload_hash": "8f7d..."
      }
    ],
    "redacted_count": 11
  }
}
```

Envelope requirements:

- `event`: string event discriminator. Supported values today are `dashboard_digest` and `control`.
- `id`: stringified ledger offset used for replay and ordering.
- `data`: JSON object matching the backend contract models.
- Ordering is monotonic by ledger offset.
- `dashboard_digest.data.recent_events` must remain sanitized metadata only; raw payload bodies must not be emitted.

### Transport feature flags

The React SPA selects transport at runtime using Vite env flags:

- `VITE_ENABLE_DASHBOARD_STREAM` (`true` by default): master switch for stream subscription.
- `VITE_DASHBOARD_STREAM_TRANSPORT` (`sse` default): transport selector (`sse` or `websocket`).
- `VITE_DASHBOARD_REST_FALLBACK` (`true` default): whether to fall back to REST when stream errors or backpressure occurs.

Backend capability hints are available via `GET /dashboard/transport_features`.

### Testing strategy

- Unit test view/state/domain logic in isolation.
- Integration test data-access adapters with mocked transport.
- Conformance test `/dashboard/stream` envelope, auth, and replay behavior so future framework migrations inherit the same contract.
- End-to-end test authenticated real-time subscription and reconnect behavior.

## Concrete framework decision

**Chosen framework: React (Vite-based SPA).**

Rationale:

- Existing codebase and tests are already built around React components.
- The dashboard deployment model is static assets served alongside the API.
- Current build/test tooling (`vite`, `vitest`) is already integrated in repository workflows.

## Next.js migration note

Next.js remains a valid roadmap target only if it consumes the same canonical transport contract.
To keep that migration low-risk, the repository includes a parallel reference client module at `frontend/src/next/dashboardStreamClient.js` that reuses the shared transport abstraction instead of redefining stream semantics.
