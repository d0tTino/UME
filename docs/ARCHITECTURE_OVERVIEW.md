# UME Architecture Overview (Single Source of Truth)

This document is the canonical architecture reference for backend selection and
runtime bootstrap in UME. It describes the *actual* creation paths used by the
codebase today.

## Glossary

Use [`GLOSSARY.md`](GLOSSARY.md) as the single source for canonical terminology (`backend`, `adapter`, `canonical event`, and `canonical path`).


## Layered package layout

UME now uses explicit package boundaries:

- `ume.kernel`: core platform contracts and orchestration primitives
  - `ume.kernel.events`
  - `ume.kernel.policy`
  - `ume.kernel.graph_adapter`
  - `ume.kernel.processing`
  - `ume.kernel.ledger`
- `ume.domains.<name>`: feature/domain packs implementing domain-specific logic

### Extension points for domain logic

Domain modules integrate through extension hooks instead of direct coupling to core pipeline modules.
Use `ume.domains.extensions.DomainExtension` and `run_domain_extensions(...)` to attach domain behavior from mutation/pipeline entry points.

### Static dependency enforcement

Kernel/domain boundaries are statically enforced:

- Linter: `python scripts/lint_dependencies.py`
- Tests: `tests/architecture/test_dependency_boundaries.py`

These checks fail when any kernel module imports `ume.domains` directly.

## Canonical mutation/projection runtime contract

All mutation-capable ingress routes (API, CLI, Kafka, gRPC, and compatibility consumers) now converge on a single runtime contract:

- `ume.services.event_processor.EventProcessorService` is the service boundary used by integrations.
- `ume.pipeline.core.EventPipelineOrchestrator` is the only stage orchestration runtime behind that service boundary.

`ume.projection_engine.run_projection_engine` and `ume.pipeline.graph_consumer.run_graph_consumer` were removed after sunset and replaced by orchestrator-native entrypoints. Remaining compatibility shims (`ume.services.mutate.run_mutation*`, `ume.stream_processor`, top-level `ume.__getattr__` fallback exports) are controlled by `ume.deprecations.DEPRECATION_REGISTRY` and a CI callsite guard (`scripts/check_deprecated_callsites.py`).



## Legacy migration

```python
# old mutation path
from ume.services.mutate import run_mutation_async
result = await run_mutation_async(payload, source="kafka")

# new service boundary
from ume.services.event_processor import DEFAULT_EVENT_PROCESSOR
result = await DEFAULT_EVENT_PROCESSOR.process_payload_async(payload, source="kafka")
```

```python
# old projection consumer
from ume.projection_engine import run_projection_engine
run_projection_engine(graph)

# new orchestrator worker
from ume.services.projection_worker import run_projection_worker
run_projection_worker(graph)
```

```python
# old stream import
from ume import stream_processor

# new stream import
from ume.pipeline import stream_processor
```

## Deprecated top-level export migration matrix

`src/ume/__init__.py` now keeps only the top-level compatibility exports still exercised by external-facing tests or runtime bootstrap compatibility paths. First-party source modules should import canonical modules directly.

### `_RUNTIME_EXPORTS` audit

| Symbol | Disposition | Replacement import / action | Target removal | Notes |
| --- | --- | --- | --- | --- |
| `Neo4jGraph` | keep | Call `ume.bootstrap.runtime.bootstrap_runtime("ume")`, then use `ume.Neo4jGraph` only on the bootstrapped package or import `ume.neo4j_graph.Neo4jGraph` directly where appropriate. | `0.3.0` | Runtime bootstrap fallback retained for external callers only. |
| `VectorBackend` | keep | `ume.bootstrap.runtime.bootstrap_runtime("ume")` or `ume.vector_store.VectorBackend`. | `0.3.0` | Runtime bootstrap fallback retained for external callers only. |
| `VectorStore` | keep | `ume.bootstrap.runtime.bootstrap_runtime("ume")` or `ume.vector_store.VectorStore`. | `0.3.0` | Runtime bootstrap fallback retained for external callers only. |
| `VectorStoreListener` | keep | `ume.bootstrap.runtime.bootstrap_runtime("ume")` or `ume._internal.listeners.VectorStoreListener`. | `0.3.0` | Runtime bootstrap fallback retained for external callers only. |
| `create_default_store` | keep | `ume.bootstrap.runtime.bootstrap_runtime("ume")` or `ume.vector_store.create_default_store`. | `0.3.0` | Runtime bootstrap fallback retained for external callers only. |
| `FaissBackend` | keep | `ume.bootstrap.runtime.bootstrap_runtime("ume")` or `ume.faiss_backend.FaissBackend`. | `0.3.0` | Runtime bootstrap fallback retained for external callers only. |
| `ChromaBackend` | keep | `ume.bootstrap.runtime.bootstrap_runtime("ume")` or `ume.chroma_backend.ChromaBackend`. | `0.3.0` | Runtime bootstrap fallback retained for external callers only. |
| `generate_embedding` | keep | `ume.bootstrap.runtime.bootstrap_runtime("ume")` or `ume.embedding.generate_embedding`. | `0.3.0` | Runtime bootstrap fallback retained for external callers only. |
| `OntologyListener` | keep | `ume.bootstrap.runtime.bootstrap_runtime("ume")` or `ume.embedding.OntologyListener`. | `0.3.0` | Runtime bootstrap fallback retained for external callers only. |
| `configure_ontology_graph` | keep | `ume.bootstrap.runtime.bootstrap_runtime("ume")` or `ume.ontology.configure_ontology_graph`. | `0.3.0` | Runtime bootstrap fallback retained for external callers only. |

### `_COMPAT_EXPORTS` audit

| Symbol | Disposition | Replacement import | Target removal | Notes |
| --- | --- | --- | --- | --- |
| `MockGraph` | keep | `from ume.graph import MockGraph` | `0.4.0` | Retained for external/tests compatibility. |
| `PersistentGraph` | keep | `from ume.persistent_graph import PersistentGraph` | `0.4.0` | Retained for external/tests compatibility. |
| `PostgresGraph` | remove | `from ume.postgres_graph import PostgresGraph` | removed now | No first-party top-level import callsites remain. |
| `RedisGraphAdapter` | remove | `from ume.redis_graph_adapter import RedisGraphAdapter` | removed now | No first-party top-level import callsites remain. |
| `ArangoGraph` | remove | `from ume.arango_graph import ArangoGraph` | removed now | No first-party top-level import callsites remain. |
| `enable_periodic_snapshot` | remove | `from ume.auto_snapshot import enable_periodic_snapshot` | removed now | Internal callers already use module imports. |
| `disable_periodic_snapshot` | remove | `from ume.auto_snapshot import disable_periodic_snapshot` | removed now | Internal callers already use module imports. |
| `enable_snapshot_autosave_and_restore` | remove | `from ume.auto_snapshot import enable_snapshot_autosave_and_restore` | removed now | `ume.cli.prompt` now imports the canonical module directly. |
| `start_retention_scheduler` | remove | `from ume.retention import start_retention_scheduler` | removed now | Internal callers already use module imports. |
| `stop_retention_scheduler` | remove | `from ume.retention import stop_retention_scheduler` | removed now | Internal callers already use module imports. |
| `start_ledger_compaction_scheduler` | remove | `from ume.retention import start_ledger_compaction_scheduler` | removed now | Internal callers already use module imports. |
| `stop_ledger_compaction_scheduler` | remove | `from ume.retention import stop_ledger_compaction_scheduler` | removed now | Internal callers already use module imports. |
| `start_memory_aging_scheduler` | remove | `from ume.memory_aging import start_memory_aging_scheduler` | removed now | Internal callers already use module imports. |
| `stop_memory_aging_scheduler` | remove | `from ume.memory_aging import stop_memory_aging_scheduler` | removed now | Internal callers already use module imports. |
| `start_vector_age_scheduler` | remove | `from ume.memory_aging import start_vector_age_scheduler` | removed now | Internal callers already use module imports. |
| `stop_vector_age_scheduler` | remove | `from ume.memory_aging import stop_vector_age_scheduler` | removed now | Internal callers already use module imports. |
| `RoleBasedGraphAdapter` | keep | `from ume.rbac_adapter import RoleBasedGraphAdapter` | `0.4.0` | Retained for external/tests compatibility. |
| `AccessDeniedError` | keep | `from ume.rbac_adapter import AccessDeniedError` | `0.4.0` | Retained for external/tests compatibility. |
| `PermissionsGraphAdapter` | keep | `from ume.permissions_adapter import PermissionsGraphAdapter` | `0.4.0` | Retained for external/tests compatibility. |
| `PolicyViolationError` | keep | `from ume.plugins.alignment import PolicyViolationError` | `0.4.0` | Retained for external/tests compatibility. |
| `apply_event_to_graph` | keep | `from ume.processing import apply_event_to_graph` | `0.4.0` | Retained for external/tests compatibility. |
| `ProcessingError` | keep | `from ume.processing import ProcessingError` | `0.4.0` | Retained for external/tests compatibility. |
| `log_audit_entry` | remove | `from ume.audit import log_audit_entry` | removed now | `ume.cli.prompt` now imports the canonical module directly. |
| `get_audit_entries` | keep | `from ume.audit import get_audit_entries` | `0.4.0` | Retained for external/tests compatibility. |
| `snapshot_graph_to_file` | keep | `from ume.snapshot import snapshot_graph_to_file` | `0.4.0` | Retained for external/tests compatibility. |
| `load_graph_from_file` | keep | `from ume.snapshot import load_graph_from_file` | `0.4.0` | Retained for external/tests compatibility. |
| `load_graph_into_existing` | remove | `from ume.snapshot import load_graph_into_existing` | removed now | `ume.cli.prompt` now imports the canonical module directly. |
| `SnapshotError` | keep | `from ume.snapshot import SnapshotError` | `0.4.0` | Retained for external/tests compatibility. |
| `validate_event_dict` | remove | `from ume.schema_utils import validate_event_dict` | removed now | Internal callers already use module imports. |
| `GraphSchema` | remove | `from ume.graph_schema import GraphSchema` | removed now | Internal callers already use module imports. |
| `load_default_schema` | remove | `from ume.graph_schema import load_default_schema` | removed now | Internal callers already use module imports. |
| `GraphSchemaManager` | remove | `from ume.schema_manager import GraphSchemaManager` | removed now | Internal callers already use module imports. |
| `DEFAULT_SCHEMA_MANAGER` | keep | `from ume.schema_manager import DEFAULT_SCHEMA_MANAGER` | `0.4.0` | Internal callers migrated; shim remains for external/tests compatibility. |
| `ssl_config` | remove | `from ume.utils import ssl_config` | removed now | Internal callers already use module imports. |
| `EpisodicMemory` | remove | `from ume.memory import EpisodicMemory` | removed now | Internal callers already use package/module imports. |
| `SemanticMemory` | remove | `from ume.memory import SemanticMemory` | removed now | Internal callers already use package/module imports. |
| `ColdMemory` | remove | `from ume.memory import ColdMemory` | removed now | Internal callers already use package/module imports. |
| `LLMFerry` | remove | `from ume.llm_ferry import LLMFerry` | removed now | No first-party top-level import callsites remain. |
| `score_text` | remove | `from ume.reliability import score_text` | removed now | Internal callers already use module imports. |
| `filter_low_confidence` | remove | `from ume.reliability import filter_low_confidence` | removed now | Internal callers already use module imports. |
| `AgentTask` | remove | `from ume.agent_orchestrator import AgentTask` | removed now | No first-party top-level import callsites remain. |
| `AgentOrchestrator` | remove | `from ume.agent_orchestrator import AgentOrchestrator` | removed now | No first-party top-level import callsites remain. |
| `Supervisor` | remove | `from ume.agent_orchestrator import Supervisor` | removed now | No first-party top-level import callsites remain. |
| `Critic` | remove | `from ume.agent_orchestrator import Critic` | removed now | No first-party top-level import callsites remain. |
| `MessageEnvelope` | remove | `from ume.message_bus import MessageEnvelope` | removed now | No first-party top-level import callsites remain. |
| `ReflectionAgent` | remove | `from ume.agent_orchestrator import ReflectionAgent` | removed now | No first-party top-level import callsites remain. |
| `Task` | keep | `from ume.dag_executor import Task` | `0.4.0` | Retained for external/tests compatibility. |
| `DAGExecutor` | keep | `from ume.dag_executor import DAGExecutor` | `0.4.0` | Retained for external/tests compatibility. |
| `DAGService` | remove | `from ume.dag_service import DAGService` | removed now | No first-party top-level import callsites remain. |
| `ResourceScheduler` | remove | `from ume.resource_scheduler import ResourceScheduler` | removed now | No first-party top-level import callsites remain. |
| `ScheduledTask` | remove | `from ume.resource_scheduler import ScheduledTask` | removed now | No first-party top-level import callsites remain. |
| `Dossier` | remove | `from ume.dossier import Dossier` | removed now | No first-party top-level import callsites remain. |
| `tokenize` | remove | `from ume.tokenization import tokenize` | removed now | Internal callers already use module imports. |
| `create_graph_adapter` | migrate | `from ume.factories import create_graph_adapter` | migrated in-tree, removed now | `ume.cli.prompt` now imports the canonical factory directly. |
| `create_vector_store` | remove | `from ume.factories import create_vector_store` | removed now | Internal callers already use module imports. |
| `create_graph` | remove | `from ume.resources import create_graph` | removed now | Internal callers already use module imports. |
| `graph_factory` | remove | `from ume.resources import graph_factory` | removed now | No first-party top-level import callsites remain. |
| `vector_store_factory` | remove | `from ume.resources import vector_store_factory` | removed now | No first-party top-level import callsites remain. |
| `get_capability_manifest` | remove | `from ume.factories import get_capability_manifest` | removed now | Internal callers already use module imports. |
| `start_dossier_snapshot_scheduler` | remove | `from ume.dossier.scheduler import start_dossier_snapshot_scheduler` | removed now | Internal callers already use module imports. |
| `stop_dossier_snapshot_scheduler` | remove | `from ume.dossier.scheduler import stop_dossier_snapshot_scheduler` | removed now | Internal callers already use module imports. |

## Architecture status

### Implemented components

- Canonical event ingestion paths for API, CLI, Kafka, and gRPC through `EventProcessorService`.
- `EventPipelineOrchestrator` as the canonical orchestration runtime for validation, policy, and projection stages.
- Graph backend factory + plugin discovery via `create_graph_adapter()` and `ume.graph_adapters`.
- Vector backend factory + plugin discovery via `create_vector_store()` and `ume.vector_backends`.
- Explicit runtime bootstrap via `bootstrap_runtime("ume")`.
- Event-contract lifecycle controls (`v1`/`v2`/`v3` schemas + compatibility checks in CI).
- Capability metadata exposure and runtime capability checks for graph/vector operations.

### Planned components

- Expanded backend capability negotiation for advanced graph features (for example native ACL primitives and richer transactional semantics).
- Additional canonical-event schema lines beyond `v3` with adjacent-version transforms when new majors are introduced.
- Broader plugin ecosystem coverage for optional vector backends and integration adapters.
- Continued reduction of compatibility shims in `ume.projection_engine` and mutation legacy surfaces once downstream migrations are complete.

## 1) Graph backend creation flow

**Primary API:** `ume.factories.create_graph_adapter()` (`src/ume/factories.py`).

**Source files (authoritative):**

- `src/ume/factories.py`
- `src/ume/adapters/bootstrap.py`
- `src/ume/adapters/registry.py`

```text
create_graph_adapter()
  -> register_builtin_graph_backends()          # src/ume/adapters/bootstrap.py
  -> ensure_external_graph_backends_discovered()# src/ume/adapters/registry.py
  -> read UME_GRAPH_BACKEND
  -> create_registered_graph_adapter(backend, db_path, default="persistent")
  -> optional TracingGraphAdapter wrapper
  -> optional RoleBasedGraphAdapter wrapper
```

### Built-in graph backends

`register_builtin_graph_backends()` registers the built-in names exactly once:

- `sqlite` and `persistent` -> `PersistentGraph`
- `postgres` -> `PostgresGraph`
- `redis` -> `RedisGraphAdapter`
- `arango` -> `ArangoGraph`
- `neo4j` -> lazy-loaded constructor (imported only when selected)

### External graph backends (plugins)

`src/ume/adapters/registry.py` uses the shared plugin registry and discovery
path for graph backends:

- Capability: `graph_backend`
- Entry-point group: `ume.graph_adapters`
- Optional module discovery from `UME_GRAPH_ADAPTER_MODULES`

This means graph backends can be contributed as plugins and discovered from
Python package entry points, in addition to built-ins. External registrations
must now provide explicit capability metadata; `ume.graph_adapters` entry
points must resolve to either a single backend spec with `constructor` and
`capabilities`, or a mapping of backend names to those specs. Registrations
that omit `capabilities` are rejected during discovery.

## 2) Vector backend creation flow

**Primary API:** `ume.vector_store.create_vector_store()` (alias of
`create_default_store`) in `src/ume/vector_store.py`.

**Source files (authoritative):**

- `src/ume/vector_store.py`
- `src/ume/vector_backends/` (registry, built-ins, plugin loading)

```text
create_vector_store() / create_default_store()
  -> read UME_VECTOR_BACKEND (env or settings)
  -> get_backend(name)                          # src/ume/vector_backends/__init__.py
  -> resolve vector dimension
  -> instantiate backend class
```

### Vector backend registry and plugins

`src/ume/vector_backends/__init__.py` defines vector backend registration and
plugin discovery:

- Capability: `vector_backend`
- Entry-point group: `ume.vector_backends`
- Built-ins include `faiss` and `chroma`
- Optional providers are available through plugin modules/entry points (for
  example Pinecone or Milvus integrations)

`VectorStore` remains available as a compatibility constructor, but new code
should use `create_vector_store()`.

## 3) Runtime bootstrap behavior

**Primary API:** `ume.bootstrap.runtime.bootstrap_runtime()` in
`src/ume/bootstrap/runtime.py`.

**Source file (authoritative):**

- `src/ume/bootstrap/runtime.py`

`bootstrap_runtime()` performs explicit runtime wiring so importing `ume`
remains lightweight:

1. Loads configuration symbols via `load_config()`.
2. Loads optional Neo4j symbol via `load_neo4j()`.
3. Loads vector modules via `load_vector_modules()`.
4. Loads embedding integrations/listeners via `load_embedding()`.
5. Attaches all resolved exports onto the package module and sets
   `_runtime_bootstrapped = True`.

Use this function from long-running entry points (API service, CLI workers,
projection workers) before constructing graph/vector resources.

## 4) Legacy migration (term mapping)

| Legacy term | Current term/API |
| --- | --- |
| `UME_GRAPH_ADAPTER` | `UME_GRAPH_BACKEND` |
| `get_adapter(...)` | `create_graph_adapter(...)` |
| “adapter map” | Graph backend plugin registry (`ume.graph_adapters` entry points + adapter registry helpers) |
| “vector adapter” | Vector backend (`UME_VECTOR_BACKEND`, `create_vector_store()`, `ume.vector_backends` entry points) |

## 5) Practical guidance

- For graph backend selection, always configure `UME_GRAPH_BACKEND` and create
  adapters via `create_graph_adapter()`.
- For vector backend selection, always configure `UME_VECTOR_BACKEND` and
  create stores via `create_vector_store()`.
- For plugin backends, declare entry points under `ume.graph_adapters` (graph)
  or `ume.vector_backends` (vector).
- For service startup, call `bootstrap_runtime("ume")` in the process entry
  point before first use of optional integrations.


## 6) Canonical event contract lifecycle

UME keeps machine-validated contract bundles under `src/ume/schemas/v1`, `v2`, and `v3`. Runtime validation resolves the bundle by `metadata.schema_version` major.

- **Required vs optional fields:** core required fields are stable; v3 introduces required identity metadata (`eventId`, `sourceService`) while v1/v2 remain permissive for legacy replay.
- **Additive changes:** new optional keys may ship in-place within a major line.
- **Breaking changes:** required-field removals or type/semantic changes require a major bump plus explicit upgrade/downgrade transformers (`upgrade_event`, `downgrade_event`).
- **Deprecation window:** minimum two minor releases or 90 days before removing deprecated fields in the next major.

CI enforces compatibility with `scripts/check_schema_compatibility.py`, and replay compatibility is covered by `tests/test_event_contract.py`.


## 7) Backend capability matrix

Backend registrations now carry declared capability metadata so runtime features
can negotiate support before executing capability-dependent operations.

### Graph backend capabilities

| Backend | transactional | bulk_write | native_acl | Fallbacks |
| --- | --- | --- | --- | --- |
| sqlite / persistent | no | yes | no | application-side ACL filtering |
| postgres | yes | yes | no | application-side ACL filtering |
| redis | no | yes | no | application-side ACL filtering |
| arango | yes | yes | no | application-side ACL filtering |
| neo4j | yes | yes | no | application-side ACL filtering |

### Vector backend capabilities

| Backend | vector_similarity | bulk_write |
| --- | --- | --- |
| faiss | yes | yes |
| chroma | yes | yes |
| milvus | yes | yes |
| pinecone (optional) | yes | yes |

API capability metadata is exposed at `GET /health/capabilities`. Vector query
routes also verify `vector_similarity` support and return `501` when the selected
backend does not provide it.

## 8) Policy input contract (OPA/Rego)

Policy plugins now receive a stable structured input document with the following shape:

```json
{
  "event": {
    "event_id": "...",
    "event_type": "...",
    "timestamp": 0,
    "node_id": "...",
    "target_node_id": "...",
    "label": "...",
    "payload": {}
  },
  "graph": {
    "mode": "snapshot|neighborhood",
    "nodes": {},
    "edges": []
  },
  "actor": {"id": "...", "type": "..."},
  "source": {"transport": "api|kafka|...", "service": "..."},
  "metadata": {"redacted": false, "canonical_metadata": {}}
}
```

`graph.mode=snapshot` is used for small graphs; large graphs receive a bounded neighborhood view centered on event nodes. This keeps policy decisions backend-agnostic while letting Rego evaluate existing node/edge state.
