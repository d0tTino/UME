# Policy Pipeline Extension Guide

The policy pipeline is split into **decision** and **transform** stages.

## Stage contract

All stages implement `run(context: PolicyContext) -> Optional[PolicyResult]`.

- **Inputs**
  - Stages receive a mutable `PolicyContext`.
  - `pre_parse_*` stages normalize `raw_payload` / `transport_data` into
    `canonical_event` and `effective_event`.
- **Side effects**
  - Stages should mutate only `PolicyContext`.
  - Stages should not emit audit logs directly; `PolicyPipeline` emits final
    decisions and post-apply audit records.
- **Decision precedence**
  1. `DENY` / `QUARANTINE` (terminal)
  2. `REDACTED`
  3. `ALLOW`
- **Idempotency**
  - Stage behavior should be deterministic for equivalent input.
  - Transform stages should preserve stable results when re-run.

## Declarative stage registry

`build_default_policy_pipeline(...)` uses a stage registry and supports
configuration in either:

- Environment variable: `UME_POLICY_PIPELINE_STAGES`
- JSON config file via `config_path`:

```json
{
  "policy_pipeline": {
    "stages": [
      "pre_parse_transport",
      "pre_apply_consent",
      "pre_apply_alignment",
      "pre_persist_redaction",
      "post_apply_auditing"
    ]
  }
}
```

When both are provided, the environment variable takes precedence.

## Built-in stages

- `pre_parse_transport` (decision)
- `pre_apply_consent` (decision)
- `pre_apply_alignment` (decision)
- `pre_persist_redaction` (transform)
- `post_apply_auditing` (post_apply)

## Adding a custom stage

1. Create a class with a `name` and `run(context)` method.
2. Register it via `PolicyStageRegistration` in a `StageRegistry` instance.
3. Pass your registry to `build_default_policy_pipeline(registry=...)`.
4. Include the stage name in `UME_POLICY_PIPELINE_STAGES` or your config file.
