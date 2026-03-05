# Projection Engine Contract

This document defines the **canonical projection pipeline contract** for UME.

## Canonical implementation

The authoritative implementation is:

- `ume.pipeline.core.EventPipelineOrchestrator` for stage orchestration.
- Transport adapters in `ume.events.adapters` + `ume.events.ingress` for ingress normalization.
- `ume.services.event_processor.EventProcessorService` as the single service entrypoint used by CLI/API/consumer integrations (implemented as a thin facade over `EventPipelineOrchestrator`).

Legacy entrypoints in `ume.projection_engine`, `ume.pipeline.graph_consumer`, and direct `ume.services.mutate.run_mutation*` calls are compatibility wrappers and are deprecated.

## Authoritative stage sequence

All ingress paths (Kafka, CLI, gRPC, API) MUST execute the same stages in the same order:

1. **Ingress normalization**
   - Decode transport payload.
   - Convert transport-specific fields to canonical event shape.
2. **Schema validation**
   - Validate canonical structure + required graph mutation fields.
3. **Policy evaluation**
   - Evaluate allow/deny/quarantine/redaction policy pipeline.
4. **Mutation apply**
   - Apply accepted effective event to the graph projector.
5. **Post-apply listeners/audit**
   - Run post-apply listeners and emit audit metadata.

Outcomes are normalized as `applied`, `redacted`, `rejected`, or `quarantined`.

## Deprecation timeline

Deprecated compatibility entrypoints:

- `ume.projection_engine.run_projection_engine`
- `ume.pipeline.graph_consumer.run_graph_consumer`
- `ume.services.mutate.run_mutation`
- `ume.services.mutate.run_mutation_async`

Timeline:

- Deprecated now (warnings emitted at runtime).
- Removal target: **2026-01-31**.
- Migration target: `ume.services.event_processor.DEFAULT_EVENT_PROCESSOR`.

## Configuration

Canonical consumer deployments still use:

- `KAFKA_BOOTSTRAP_SERVERS`
- `KAFKA_CLEAN_EVENTS_TOPIC`
- `KAFKA_GROUP_ID`

Example:

```bash
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_CLEAN_EVENTS_TOPIC=ume-clean-events
KAFKA_GROUP_ID=ume_client_group
```


## Replay guarantees

Replay behavior is deterministic for a fixed input ledger and schema transform set.

For the same ordered event log, identical replay cutoffs (`end_offset`/`end_timestamp`), and the same schema transformation bundle, UME guarantees:

- the same accepted/rejected/quarantined event set for the selected replay mode;
- the same final node and edge state in the reconstructed graph;
- stable schema-versioned mutation behavior for mixed-version ledgers.

Determinism is enforced with golden replay fixtures in `tests/data/replay_golden/` and CI replay regression tests.

### Replay modes

Replay policy side effects are configurable through replay mode selection:

- `current_policy` (default): re-runs policy evaluation using currently loaded policy stages. This is useful for forward-looking audits and simulations after policy updates.
- `strict_historical`: trusts persisted `policy_result` values in each ledger record and skips historical policy re-evaluation. This is useful for exact historical reconstruction and incident forensics.

When `strict_historical` is selected, deny/reject/quarantine outcomes in ledger metadata are treated as terminal and are not re-evaluated against the current policy stack.
