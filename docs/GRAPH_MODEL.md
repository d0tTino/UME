# UME Graph Model

This document defines the initial ontology used by the Universal Memory Engine.
It describes node types, edge labels and general versioning guidelines for the
graph representation.

## Node Types

### UserMemory
Represents memory items about a specific user.  A single user may have many
memory nodes capturing different experiences or facts.

Properties:
- `user_id` *(string, required)*: Unique identifier of the user.
- `data` *(object)*: Free form attributes describing the memory.  Example:
  `{"text": "Alice ordered coffee"}`.

### AgentIntent
Captures an intention produced by an agent.

Properties:
- `intent_id` *(string, required)*: Unique identifier for the intent.
- `description` *(string)*: Short human friendly description of the action.
  Example: `"schedule meeting"`.

### PerceptualContext
Stores sensory observations that provide context for reasoning.

Properties:
- `context_id` *(string, required)*: Unique identifier for the context entry.
- `modality` *(string)*: E.g. `vision`, `audio`.
- `payload` *(object)*: Raw or processed perceptual data.
  Example: `{"image": "base64..."}`.

## Edge Labels

- `REMEMBERS`: connects a `UserMemory` node to an `AgentIntent` that created it.
- `ASSOCIATED_WITH`: Generic association between any two nodes.
- `CAUSES`: Expresses a causal relationship from one event or context to another.

Example edge creation event:

```json
{
  "event_type": "CREATE_EDGE",
  "timestamp": 1678954321,
  "node_id": "intent123",
  "target_node_id": "memory789",
  "label": "REMEMBERS",
  "payload": {}
}
```

Each edge is directed and labeled and may carry optional properties in the
future.  At minimum an edge stores the source node ID, target node ID and
its label.

## Event Sourcing

Events entering the system contain an `eventType` string describing the
operation (for example `CREATE_NODE` or `DELETE_EDGE`). The parser attempts to
map this value to the :class:`~ume.event.EventType` enumeration but preserves the
original text when the value is unknown. This allows custom event categories to
flow through the pipeline and be stored in the ledger without schema changes.

During sanitization the Privacy Agent tokenizes common text fields such as
`name`, `text` and `content`. The resulting list of tokens is attached to the
event payload under the `tokens` key so that downstream components can create
vector embeddings consistently.

### Canonical Event Fields

| Field | Description |
|-------|-------------|
| `eventType` | The type of operation, e.g. `CREATE_NODE` or `ENTITY_DISCOVERED`. |
| `timestamp` | ISO&nbsp;8601 time when the event occurred. |
| `eventId` | Unique identifier for the event. |
| `correlationId` | ID linking related events. |
| `subjectEntity` | `{id, type}` describing the entity affected. |
| `sourceService` | Originating service name. |
| `payload` | Additional attributes specific to the event type. |

#### Example: RESEARCH_JOB_STARTED

```json
{
  "eventType": "RESEARCH_JOB_STARTED",
  "timestamp": "2024-03-15T12:10:00Z",
  "node_id": "job_123",
  "payload": {"status": "running"}
}
```

#### Example: DATA_SOURCE_QUERIED

```json
{
  "eventType": "DATA_SOURCE_QUERIED",
  "timestamp": "2024-03-15T12:11:00Z",
  "node_id": "job_123",
  "target_node_id": "source_456",
  "label": "USED",
  "payload": {}
}
```

As events pass from the ingestion API through the Privacy Agent and into the projection engine, they retain this schema. The engine applies them to the graph and notifies listeners such as `VectorStoreListener`, which adds any embedded vectors to the configured index automatically.

## Versioning

The schema is expected to evolve.  Node and edge type definitions should be
additive where possible.  Breaking changes to existing types require a new major
schema version.  Each schema file will include a `version` field so producers and
consumers can negotiate compatibility.

Version numbers follow `MAJOR.MINOR.PATCH` semantics.  Adding a new optional
property bumps the MINOR version.  Changing required fields or the meaning of an
existing property increments MAJOR.  The PATCH component is reserved for
documentation fixes or clarifications that do not alter validation rules.

## Programmatic Schema Loading

UME ships with a default graph schema definition stored in
`ume/schemas/graph_schema.yaml`.  The :class:`ume.graph_schema.GraphSchema`
class provides helpers to load this file and validate node types and edge labels
at runtime.  The function :func:`ume.graph_schema.load_default_schema` returns a
schema instance, which is imported during module initialization as
`ume.graph_schema.DEFAULT_SCHEMA`.

Custom schema files can also be loaded using
``GraphSchema.load("path/to/schema.yaml")``.  The loader accepts YAML or JSON
formats and constructs :class:`NodeType` and :class:`EdgeLabel` objects with
their associated version metadata.  ``GraphSchema.load_default()`` is a
convenient wrapper that reads the built-in schema shipped with UME.

`apply_event_to_graph` consults this default schema whenever a node or edge is
created.  If a ``type`` attribute is present for a new node it must match one of
the defined node types.  Edge creation will fail if the provided label is not in
the schema.  Each node type and edge label entry contains a `version` field so
applications can coordinate upgrades over time.

## Schema Management Utilities

The :class:`ume.schema_manager.GraphSchemaManager` class discovers all schema
files shipped with UME and exposes them by version.  `apply_event_to_graph`
accepts a ``schema_version`` parameter, allowing events to be validated against
different revisions of the ontology.  This makes it possible to evolve node and
edge types while maintaining backward compatibility.  Each schema version also
maps to a Protobuf definition, accessible via ``GraphSchemaManager.get_proto``.
This provides strongly typed representations for serialized graph snapshots.

```python
from ume import Event, EventType, apply_event_to_graph, DEFAULT_SCHEMA_MANAGER

schema = DEFAULT_SCHEMA_MANAGER.get_schema("2.0.0")
event = Event(
    event_type=EventType.CREATE_NODE,
    timestamp=123,
    payload={"node_id": "n1", "attributes": {"type": "NewType"}},
)

apply_event_to_graph(event, graph, schema_version=schema.version)
```

## SQLite indices

The `PersistentGraph` backend uses SQLite for storing nodes and edges.
During initialization, indices on the `edges` table are created to
speed up lookups. An index `idx_edges_source` is always created on the
`source` column and an additional `idx_edges_target` index is created on
the `target` column.

## Graph retention

Both the SQLite and Neo4j adapters track a `created_at` timestamp for
every node and edge. The method `purge_old_records(max_age_seconds)`
removes graph entries older than the provided age.  Edges are deleted
first, followed by nodes that fall below the cutoff.  Any relationships
attached to those nodes are removed automatically.
The API runs a background task that calls this method once per day. The
retention window defaults to 30 days and can be configured via the
`UME_GRAPH_RETENTION_DAYS` environment variable.

## Ledger replay

The event ledger stores sanitized events with their original offsets. A graph
can be reconstructed at any point by replaying these events. The helper
function ``build_graph_from_ledger`` instantiates a temporary graph and applies
events up to a specified offset or timestamp:

```python
from ume.event_ledger import EventLedger
from ume.replay import build_graph_from_ledger

ledger = EventLedger("ledger.db")
graph = build_graph_from_ledger(ledger, end_offset=10)
# or limit by timestamp
snapshot = build_graph_from_ledger(ledger, end_timestamp=1_725_000_000)
```

The `/ledger/replay` API wraps this helper and returns a JSON snapshot of the
graph state.

To update an existing graph in place, use ``replay_from_ledger`` specifying a
``start_offset``. This allows applications to store a bookmark and resume event
processing from the last applied offset:

```python
from ume.replay import replay_from_ledger

last = replay_from_ledger(graph, ledger, start_offset=stored_offset)
```

### Restoring historical state

Because the ledger is append-only, you can rebuild the graph as it looked at any
previous moment by providing ``end_offset`` or ``end_timestamp`` when calling
``build_graph_from_ledger``. The ``/graph/history`` API exposes this capability
over HTTP:

```bash
curl -X GET -H "Authorization: Bearer <token>" \
  "http://localhost:8000/graph/history?timestamp=1725000000"
```

The returned JSON snapshot reflects all events up to the requested cutoff.

## Snapshot scheduler

Call :func:`ume.enable_periodic_snapshot` to write the graph to
``UME_SNAPSHOT_PATH`` at a fixed interval (default 3600 seconds). The function
returns the background thread and a stop callback. Use
:func:`ume.enable_snapshot_autosave_and_restore` to restore an existing snapshot
before scheduling future saves. Snapshot locations are validated against
``UME_SNAPSHOT_DIR``.

## Memory aging

The :class:`ume.memory.TieredMemoryManager` orchestrates data movement across
the episodic, semantic and optional cold layers. During each aging cycle old
events migrate from episodic into semantic memory and very old entries can be
archived in cold storage. Embeddings are expired based on age and their
freshness is audited against the ``UME_VECTOR_MAX_AGE_DAYS`` threshold.
Instantiate ``TieredMemoryManager`` with the memory instances and call
``start()`` to run the process in the background. Pass ``vector_age_seconds=None``
to disable vector pruning.
Use :func:`ume.start_vector_age_scheduler` to audit existing vectors and
record the ``ume_stale_vector_count`` metric.

## Schema Upgrades

### Migrating from version 1.0.0 to 2.0.0

UME provides the helper `GraphSchemaManager.upgrade_schema` to update both
the schema definition and any stored data. When upgrading from `1.0.0` to
`2.0.0` the following transformations occur:

1. Edges labeled `L` are renamed to `LINKS_TO`.
2. Edges labeled `TO_DELETE` are removed from the graph.

Applications should instantiate a `GraphSchemaManager` and pass the graph
instance when calling `upgrade_schema`:

```python
manager = GraphSchemaManager()
schema = manager.upgrade_schema("1.0.0", "2.0.0", graph)
```

After the call, the provided graph will conform to the new schema and the
returned schema object can be used for validating future events.

### CLI Helpers

The ``ume`` tool includes two utilities for working with schema versions:

* ``register_schema <version> <schema_path> <proto_module>`` – load an external
  YAML schema file and associated Protobuf module at runtime.
* ``migrate_schema <old_version> <new_version>`` – apply ``upgrade_schema`` to
  the current graph.
