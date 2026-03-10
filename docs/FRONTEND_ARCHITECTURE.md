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
- Persist last processed event ID per session to support reconnection.
- Treat `control.backpressure` events as data-loss signals and trigger a catch-up flow.

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
