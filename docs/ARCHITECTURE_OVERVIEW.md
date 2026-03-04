# UME Architecture Overview (Single Source of Truth)

This document is the canonical architecture reference for backend selection and
runtime bootstrap in UME. It describes the *actual* creation paths used by the
codebase today.

## 1) Graph backend creation flow

**Primary API:** `ume.factories.create_graph_adapter()` (`src/ume/factories.py`).

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
Python package entry points, in addition to built-ins.

## 2) Vector backend creation flow

**Primary API:** `ume.vector_store.create_vector_store()` (alias of
`create_default_store`) in `src/ume/vector_store.py`.

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

## 4) Concept Mapping (legacy -> current)

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
