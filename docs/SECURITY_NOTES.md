# Security Notes


> Canonical architecture reference: [`ARCHITECTURE_OVERVIEW.md`](ARCHITECTURE_OVERVIEW.md).
This document describes UME's security architecture and trust boundaries.

## Security authority and trust boundaries

### 1) Producer ingress authentication boundary

**Boundary:** external producers -> UME ingest adapters (CLI/API/gRPC/Kafka).  
**Controls:**
- API/gRPC enforce bearer-token authentication before mutating graph state.
- Kafka path relies on broker-side TLS/SASL and ACLs to authenticate producer principals.
- CLI is treated as a privileged local operator boundary and must run with least-privilege host access.

**Trust decision:** untrusted payload is accepted only as transport data; it is not trusted for mutation until canonicalized, validated, and policy-evaluated.

### 2) API authentication/authorization boundary

**Boundary:** authenticated caller -> route-level action.

**Controls:**
- OAuth token verification in `api_deps.get_current_role` gates API routes.
- Role and ownership/group checks enforce authorization prior to read/write operations.
- Access-denied responses return deterministic `401`/`403` semantics.

**Trust decision:** token identity + role + entity permissions determine whether the operation can proceed.

### 3) Policy enforcement authority boundary

**Boundary:** parsed event -> graph mutation.

**Authority:** `EventPipelineOrchestrator` + `PolicyPipeline` are the canonical policy decision point for external mutation pathways.

**Decision semantics:**
- `ALLOW`: mutation may proceed.
- `DENY` / `QUARANTINE`: mutation must not be applied.
- `REDACTED`: transformed payload is applied with redaction metadata.

All adapter entrypoints (CLI/API/Kafka/gRPC) are expected to route through this authority so deny behavior is consistent.

### 4) Audit integrity/signing boundary

**Boundary:** privileged mutation attempt -> persistent audit trail.

**Controls:**
- Audit entries are hash-chained (`prev`) and HMAC-signed with `UME_AUDIT_SIGNING_KEY`.
- Privileged mutation audit includes actor identity and correlation identifiers when present.
- Optional ledger/audit encryption protects at-rest integrity/confidentiality (`UME_ENCRYPTION_ENABLED`).

## Signed audit requirements for privileged operations

Privileged operations (graph mutations and redactions) must emit signed audit records containing:
- actor identifier,
- operation outcome,
- correlation ID (if provided by event metadata),
- immutable signature and previous-signature reference.

## Operational key management

- Rotate `UME_AUDIT_SIGNING_KEY` regularly.
- Store signing/encryption keys in a secret manager, never in git.
- Restrict audit/ledger filesystem paths to service-account-only access.

## Threat model highlights

- **Policy bypass risk:** direct internal mutation functions can bypass policy if used as ingress.
- **Mitigation:** external transport adapters must use the canonical event processor/pipeline; tests assert deny-stage parity across pathways.
- **Audit forgery risk:** mitigated via signature chain and per-deployment signing keys.


## Producer authorization outcome auditing

Ingressed canonical metadata now carries producer identity fields (`producer_id`, `tenant`) and optional `producer_signature`.
The policy pipeline verifies producer authentication/authorization in `pre_apply_producer_auth` before policy alignment checks.
Unauthenticated or unauthorized producer events are denied by default.
Audit records include producer auth outcome fields: method, authenticated flag, authorized flag, producer_id, and tenant.
