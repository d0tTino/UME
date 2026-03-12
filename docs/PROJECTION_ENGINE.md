# Projection Engine Contract


> Canonical architecture reference: [`ARCHITECTURE_OVERVIEW.md`](ARCHITECTURE_OVERVIEW.md).
This document defines the **canonical projection pipeline contract** for UME.

## Canonical implementation

The authoritative implementation is:

- `ume.pipeline.core.EventPipelineOrchestrator` for stage orchestration.
- Transport adapters in `ume.events.adapters` + `ume.events.ingress` for ingress normalization.
- `ume.services.event_processor.EventProcessorService` as the single service entrypoint used by CLI/API/consumer integrations (implemented as a thin facade over `EventPipelineOrchestrator`).

Legacy entrypoints in `ume.projection_engine`, `ume.pipeline.graph_consumer`, and direct `ume.services.mutate.run_mutation*` calls are tracked in the central deprecation registry (`ume.deprecations.DEPRECATION_REGISTRY`). Past-sunset shims are removed; active shims emit registry-backed runtime warnings.

Conformance is enforced by the mutation route parity matrix in `tests/test_mutation_entrypoint_parity.py`, which asserts equivalent `PipelineEnvelope` outcomes across Kafka/API/CLI/gRPC paths for identical payloads.

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

## Deprecated entrypoint inventory and migration map

| Legacy entrypoint | Status | Sunset | Replacement |
| --- | --- | --- | --- |
| `ume.projection_engine.run_projection_engine` | Removed (past sunset) | 2026-01-31 / 0.2.0 | `ume.services.projection_worker.run_projection_worker` |
| `ume.pipeline.graph_consumer.run_graph_consumer` | Removed (past sunset) | 2026-01-31 / 0.2.0 | `ume.pipeline.graph_consumer.run_event_pipeline_consumer` |
| `ume.services.mutate.run_mutation` | Active deprecation | 2026-07-01 / 0.3.0 | `DEFAULT_EVENT_PROCESSOR.process_payload(...)` |
| `ume.services.mutate.run_mutation_async` | Active deprecation | 2026-07-01 / 0.3.0 | `DEFAULT_EVENT_PROCESSOR.process_payload_async(...)` |
| `ume.stream_processor` | Active deprecation | 2026-07-01 / 0.3.0 | `ume.pipeline.stream_processor` |

### Migration snippets

```python
# old
from ume.services.mutate import run_mutation
envelope = run_mutation(payload, source="api")

# new
from ume.services.event_processor import DEFAULT_EVENT_PROCESSOR
envelope = DEFAULT_EVENT_PROCESSOR.process_payload(payload, source="api")
```

```python
# old
from ume.pipeline.graph_consumer import run_graph_consumer
run_graph_consumer(graph)

# new
from ume.pipeline.graph_consumer import run_event_pipeline_consumer
run_event_pipeline_consumer(graph)
```

```python
# explicit orchestrator wiring
from ume.pipeline.core import EventPipelineOrchestrator
from ume.services.event_processor import EventProcessorService

orchestrator = EventPipelineOrchestrator()
service = EventProcessorService(orchestrator=orchestrator)
envelope = service.process_payload(payload, source="cli")
```

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
