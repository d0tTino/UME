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
   - Encapsulates HTTP + SSE calls to UME backend.
   - Handles token attachment, retries, and stream resume policy.
4. **Domain utilities**
   - Pure helpers for shaping backend payloads into view models.

### Real-time consumption pattern

- Use a stream client abstraction for `GET /graph/digest/stream`.
- Use a dashboard stream client abstraction for `GET /dashboard/stream` to drive high-churn panels (`stats`, `recent_events`, PII redaction count).
- Persist last processed event ID per session to support reconnection.
- Treat `control.backpressure` events as data-loss signals and trigger a catch-up flow.
- Keep REST compatibility paths (`/dashboard/stats`, `/dashboard/recent_events`, `/pii/redactions`) for explicit refresh and stream fallback.

### Transport feature flags

The React SPA selects transport at runtime using Vite env flags:

- `VITE_ENABLE_DASHBOARD_STREAM` (`true` by default): master switch for stream subscription.
- `VITE_DASHBOARD_STREAM_TRANSPORT` (`sse` default): current transport selector.
- `VITE_DASHBOARD_REST_FALLBACK` (`true` default): whether to fall back to REST when stream errors or backpressure occurs.

Backend capability hints are available via `GET /dashboard/transport_features`.

### Testing strategy

- Unit test view/state/domain logic in isolation.
- Integration test data-access adapters with mocked transport.
- End-to-end test authenticated real-time subscription and reconnect behavior.

## Concrete framework decision

**Chosen framework: React (Vite-based SPA).**

Rationale:

- Existing codebase and tests are already built around React components.
- The dashboard deployment model is static assets served alongside the API.
- Current build/test tooling (`vite`, `vitest`) is already integrated in repository workflows.
