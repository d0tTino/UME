# Access Control


> Canonical architecture reference: [`ARCHITECTURE_OVERVIEW.md`](ARCHITECTURE_OVERVIEW.md).
This document defines how UME enforces authN/authZ and where deny decisions occur.

## Canonical decision points

To keep behavior consistent, deny decisions must occur in the same logical places for CLI/API/Kafka/gRPC mutation paths:

1. **AuthN boundary (transport):** reject unauthenticated requests (`401`) before processing payload.
2. **AuthZ boundary (role/permissions):** reject unauthorized actions (`403`) before or during command construction.
3. **Policy boundary (event pipeline):** reject/quarantine events at policy stage before graph mutation.
4. **Resource visibility boundary:** return `403` when resource exists but caller lacks access, `404` when not found.

## Pathway mapping

### CLI
- Operator identity is local/runtime-scoped.
- Mutating commands must pass through canonical event processor (`mutate_graph`), which applies policy before mutation.

### API
- OAuth token -> role resolution for authN/authZ.
- Route permission checks enforce ownership/group constraints.
- Event mutations route through ingest/event-processor stack to reach shared policy stage.

### Kafka
- Broker principal + ACLs authenticate producer identity.
- Consumer mutation path canonicalizes payload and routes through same policy stage as CLI/API.

## Policy enforcement authority

`PolicyPipeline` is the authority for mutation allow/deny/quarantine/redaction decisions.

- `DENY` / `QUARANTINE` are terminal decisions: no graph mutation is allowed.
- Deny reasons are normalized through mutation error categories to provide parity across adapters.

## Audit requirements for privileged operations

Every privileged mutation operation must emit signed audit entries with:
- `user_id`/actor identity,
- outcome and reason,
- correlation ID when available,
- signature chain fields (`prev`, `signature`).

## Security checklist for contributors

When adding a **new route**, **event type**, or **adapter**, verify all of the following:

- [ ] AuthN exists and fails closed for missing/invalid credentials.
- [ ] AuthZ exists and denies unauthorized role/ownership actions.
- [ ] Mutation path uses canonical event processor/policy pipeline (no direct bypass mutation ingress).
- [ ] Deny behavior matches existing CLI/API/Kafka semantics and error categories.
- [ ] Privileged operations emit signed audit records with actor + correlation IDs.
- [ ] Threat-model tests cover bypass attempts and deny-path parity.
