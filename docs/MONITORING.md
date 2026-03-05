# Monitoring Spec

UME exposes Prometheus metrics at `/metrics`. This spec defines the **required**
canonical pipeline metrics and label contracts.

## Canonical pipeline metrics

| Metric | Type | Required labels | Description |
| --- | --- | --- | --- |
| `ume_pipeline_ingress_total` | Counter | `source`, `adapter`, `event_type`, `event_ref`, `correlation_ref` | Ingress rate into canonical `EventPipelineOrchestrator` path. |
| `ume_pipeline_stage_latency_seconds` | Histogram | `source`, `stage`, `outcome`, `event_ref`, `correlation_ref` | Stage boundary latency for `decode`, `validate`, `policy`, and `project`. |
| `ume_pipeline_policy_outcomes_total` | Counter | `source`, `decision`, `event_type`, `event_ref`, `correlation_ref` | Policy outcomes (`ALLOW`, `DENY`, `QUARANTINE`, `REDACTED`). |
| `ume_pipeline_apply_failures_total` | Counter | `source`, `stage`, `error_category`, `event_type`, `event_ref`, `correlation_ref` | Failures while applying/projection (`processing_error`, `projection_failed`, etc.). |
| `ume_pipeline_replay_lag_seconds` | Gauge | `source` | Lag between replay wall-clock and replayed event timestamp. |

## Label safety and ID propagation

- `event_id` and `correlation_id` MUST propagate through:
  - pipeline logs,
  - tracing span attributes,
  - metric labels.
- Metric labels MUST use safe references (`event_ref`, `correlation_ref`) derived
  from a one-way hash prefix (`h:<12_hex_chars>`), not raw IDs.
- Missing IDs MUST use `none`.

## Baseline PromQL queries

- Ingress rate: `sum by (source) (rate(ume_pipeline_ingress_total[5m]))`
- P95 stage latency:
  - `histogram_quantile(0.95, sum by (le, stage) (rate(ume_pipeline_stage_latency_seconds_bucket[5m])))`
- Policy outcomes:
  - `sum by (decision) (rate(ume_pipeline_policy_outcomes_total[5m]))`
- Apply failures:
  - `sum by (error_category) (rate(ume_pipeline_apply_failures_total[5m]))`
- Replay lag: `max by (source) (ume_pipeline_replay_lag_seconds)`
