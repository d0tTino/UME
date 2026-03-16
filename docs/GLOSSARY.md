# UME Glossary

> Canonical architecture reference: [`ARCHITECTURE_OVERVIEW.md`](ARCHITECTURE_OVERVIEW.md).

This glossary is the single source for architecture terminology used across UME documentation.

## Canonical terms

- **backend**: A runtime implementation selected by environment/configuration (for example `UME_GRAPH_BACKEND`, `UME_VECTOR_BACKEND`).
- **adapter**: A concrete interface bridge that connects UME contracts to a selected backend or integration surface (for example graph adapters and integration adapters).
- **canonical event**: The normalized event representation used by policy and projection stages.
- **orchestrator**: `ume.pipeline.core.EventPipelineOrchestrator`, the canonical stage coordinator.
- **canonical path**: The primary mutation/projection execution path used in current architecture (ingress -> `EventProcessorService` -> `EventPipelineOrchestrator` -> graph/vector backends).

## Legacy migration terminology policy

Historical terms and surfaces remain documented only in dedicated **Legacy migration** sections. Primary sections should use canonical terms exclusively.

Examples:

- `UME_GRAPH_ADAPTER` -> `UME_GRAPH_BACKEND`
- `UME_VECTOR_ADAPTER` -> `UME_VECTOR_BACKEND`
- `get_adapter(...)` (graph-backend context) -> `create_graph_adapter(...)`
- "adapter map" (graph backend context) -> graph backend plugin registry (`ume.graph_adapters`)
