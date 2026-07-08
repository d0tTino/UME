# UME Graph Model


> Canonical architecture reference: [`ARCHITECTURE_OVERVIEW.md`](ARCHITECTURE_OVERVIEW.md).
This document defines the initial ontology used by the Universal Memory Engine.
It describes node types, edge labels and general versioning guidelines for the
graph representation.

Producer-facing event fields, canonical transform rules, and parser boundaries are defined in the authoritative external producer contract: [`API_REFERENCE.md#authoritative-external-producer-contract`](API_REFERENCE.md#authoritative-external-producer-contract).

## Node Types

### UserMemory

Represents memory items about a specific user. A single user may have many
memory nodes capturing different experiences or facts.

Properties:

- `user_id` *(string, required)*: Unique identifier of the user.
- `data` *(object)*: Free form attributes describing the memory. Example:
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

### NewType

Represents an additional concept introduced in schema version `2.0.0`.

Properties:

- `type_id` *(string, required)*: Unique identifier for the new entity.
- Other attributes depend on the producer.

### User

Represents an individual actor within UME. These nodes participate in
permission edges that grant or restrict access to resources.

Properties:

- `user_id` *(string, required)*: Stable identifier for the user.
- `name` *(string)*: Display name.
- `email` *(string)*: Contact address.

### UserGroup

Collects users for shared permissions and collaboration. Groups can be
linked to resources to extend access to multiple users at once.

Properties:

- `group_id` *(string, required)*: Stable identifier for the group.
- `name` *(string)*: Human friendly label.
- `members` *(array)*: List of `user_id` values belonging to the group.

### Resource

Generic node representing a shareable asset such as a document or calendar
event.

Properties:

- `id` *(string, required)*: Stable identifier for the resource.
- `visibility` *(string)*: `private` or `public_to_group`. When
  `public_to_group`, all members of the owning group can view the resource.
- Additional attributes depend on the resource type.

## Edge Labels

- `REMEMBERS`: connects a `UserMemory` node to an `AgentIntent` that created it.
- `ASSOCIATED_WITH`: Generic association between any two nodes.
- `CAUSES`: Expresses a causal relationship from one event or context to another.
- `LINKS_TO`: Represents a generic connection between nodes.
- `CONNECTS_TO`: Used for network-style associations.
- `RELATES_TO`: Indicates a topical relationship.
- `NEW_LABEL`: Links research job nodes to the documents they discover.
- `OWNED_BY`: Links a resource node to the `User` or `UserGroup` that owns it.
- `SHARED_WITH`: Grants a `UserGroup` access to a resource. Optional
  `permission_level` property describes viewer/editor rights.

### Permission Levels

The `permission_level` attribute on `OWNED_BY` and `SHARED_WITH` edges
controls access to resources. Supported values:

- `viewer` – read‑only access.
- `editor` – read and modify access.
- `public` – accessible without explicit ownership or sharing.

When creating these edges through `/edges` or `/events`, include the
`permission_level` field in the payload. The API also requires `user_id` (and
optionally `group_id`) query parameters on generic graph endpoints so the
server can evaluate these permissions at request time.

```bash
curl -X POST http://localhost:8000/edges \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
        "user_id": "User.owner",
        "group_id": "Group.ops",
        "source": "Resource.1",
        "target": "Group.ops",
        "label": "SHARED_WITH",
        "permission_level": "viewer"
      }'
```

Successful edge creation responses echo the stored permission level:

```json
{
  "status": "ok",
  "edge": {
    "source": "Resource.1",
    "target": "Group.ops",
    "label": "SHARED_WITH",
    "permission_level": "viewer"
  }
}
```

If the acting `user_id` does not have `editor` rights on the resource, the
request fails with `403 Forbidden`:

```json
{
  "detail": {
    "error": "permission_denied",
    "message": "User.helper cannot grant viewer access on Resource.1",
    "required_permission": "editor"
  }
}
```

> **Migration note:** Clients must supply the new query parameters and explicit
> `permission_level` values before schema version `3.0.0` becomes the default.
> Older requests that omit them will be rejected once the migration completes.

### Group Membership Checks

When resolving `SHARED_WITH` edges the graph now verifies that the requesting
user is listed in the target group's `members` array. A non-member receives an
access denied error even if the edge grants permissions.

### `PUBLIC_TO_GROUP` Visibility

Resources may include a `visibility` property. Setting it to
`public_to_group` makes the resource readable by every member of the owning
`UserGroup`. Editing still requires a `SHARED_WITH` edge with
`permission_level: editor`.

```json
{
  "id": "cal1",
  "visibility": "public_to_group",
  "edges": [
    {"label": "OWNED_BY", "target": "Group.eng"},
    {"label": "SHARED_WITH", "target": "Group.eng", "permission_level": "editor"}
  ]
}
```

Members of `Group.eng` can view `cal1`. Only those granted `editor` rights may
modify or delete it; others remain read-only viewers.

### Permission Queries

The API exposes helpers for inspecting permissions.

- `GET /v1/nodes` returns nodes owned by a user. It requires the
  `user_id` query parameter.
- `GET /v1/nodes/shared` returns nodes shared with a group. It requires the
  `group_id` query parameter.

```bash
curl "http://localhost:8000/v1/nodes?user_id=User.u1"
curl "http://localhost:8000/v1/nodes/shared?group_id=Group.g1"
```

Example edge creation event:

```json
{
  "eventType": "CREATE_EDGE",
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

For compatibility, the parser accepts both `eventType` (preferred) and
`event_type` as input keys.

During sanitization the Privacy Agent tokenizes common text fields such as
`name`, `text` and `content`. The resulting list of tokens is attached to the
event payload under the `tokens` key so that downstream components can create
vector embeddings consistently.

### Canonical Event Fields

| Field | Description |
|-------|-------------|
| `eventType` | Operation type like `CREATE_NODE` or `ENTITY_DISCOVERED`. |
| `timestamp` | Event time as either epoch `int` or ISO&nbsp;8601 string; `parse_event()` normalizes it to an epoch integer in the parsed `Event`. |
| `eventId` | Unique identifier for the event. |
| `correlationId` | ID linking related events. |
| `subjectEntity` | `{id, type}` describing the entity affected. |
| `sourceService` | Originating service name. |
| `payload` | Additional attributes specific to the event type. |

`timestamp` accepts either a Unix epoch integer or an ISO&nbsp;8601 string. During
parsing, values are normalized to an epoch integer in the `Event` object.

### Event Contract Compatibility and Validation

Current runtime behavior in `parse_event()` + `apply_event_to_graph()`:

* Required for all events: `eventType` and `timestamp`.
* Optional common fields: `eventId`, `correlationId`, `subjectEntity`,
  `sourceService`.
* Node-create family (`CREATE_NODE`, `RESEARCH_JOB_STARTED`):
  * parse: requires `node_id` (or `payload.node_id`), plus `payload` as `dict`.
  * processing: uses `payload.attributes` when present; must be `dict`.
* Node-update family (`UPDATE_NODE_ATTRIBUTES`, `DOCUMENT_ARCHIVED`):
  * parse: requires `node_id`, `payload.attributes` as `dict`.
  * processing: requires non-empty `payload.attributes`;
    `DOCUMENT_ARCHIVED` defaults `attributes.archived = true` if missing.
* Edge family (`CREATE_EDGE`, `DELETE_EDGE`, `CREATE_ONTOLOGY_RELATION`,
  `DATA_SOURCE_QUERIED`, `ENTITY_DISCOVERED`):
  * parse: requires `node_id`, `target_node_id`, `label` (all strings).
  * parse: `payload` is optional and defaults to `{}` for these event types.
  * processing (`CREATE_EDGE`, `DATA_SOURCE_QUERIED`, `ENTITY_DISCOVERED`):
    `payload.attributes` must be a `dict` if provided.
  * processing (`ENTITY_DISCOVERED`): creates target node when absent, then adds
    the edge.
* Unknown event types: parser accepts them, processor currently rejects with
  `ProcessingError`.

#### Example: RESEARCH_JOB_STARTED

```json
{
  "eventType": "RESEARCH_JOB_STARTED",
  "timestamp": "2024-03-15T12:10:00Z",
  "node_id": "job_123",
  "payload": {"attributes": {"type": "research_job", "status": "running"}}
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

#### Example: ENTITY_DISCOVERED

```json
{
  "eventType": "ENTITY_DISCOVERED",
  "timestamp": "2024-03-15T12:12:00Z",
  "node_id": "job_123",
  "target_node_id": "entity_789",
  "label": "FOUND",
  "payload": {"attributes": {"name": "Foo", "type": "entity"}}
}
```

#### Example: DOCUMENT_ARCHIVED

```json
{
  "eventType": "DOCUMENT_ARCHIVED",
  "timestamp": "2024-03-15T12:13:00Z",
  "node_id": "doc_1",
  "payload": {"attributes": {"archived_by": "agent_42", "archived": true}}
}
```

#### Example: CREATE_ONTOLOGY_RELATION

```json
{
  "eventType": "CREATE_ONTOLOGY_RELATION",
  "timestamp": "2024-03-15T12:14:00Z",
  "node_id": "term_a",
  "target_node_id": "term_b",
  "label": "IS_A",
  "payload": {}
}
```

### Event Flow

```text
Producer (canonical JSON) --> ume-raw-events --> Privacy Agent --> ume-clean-events
    --> Projection Engine --> Graph Adapter --> Graph Storage & Vector Store
```

1. Producers emit events following the canonical schema above.
2. The Privacy Agent validates and redacts sensitive data before forwarding
   to `ume-clean-events`.
3. The projection engine processes sanitized events and updates the graph
   via the chosen adapter.
4. `VectorStoreListener` automatically indexes any `embedding` vectors
   during this step.

As events pass from ingestion through projection they retain the canonical
schema, ensuring consistent processing across components.

Compatibility note: the primary ingest path accepts only the authoritative external contract (`eventType`, camelCase metadata keys, graph snake_case keys). For edge-family events, omitted `payload` defaults to `{}`.

### Legacy migration

Historical payload variants (`event` wrapper or snake_case metadata keys) must be normalized via `ume.events.legacy_transform.apply_legacy_transform()` before canonicalization.

As events move from the ingestion API through the Privacy Agent
and into the projection engine, they keep this schema. The engine
applies them to the graph and notifies listeners such as
`VectorStoreListener`, which adds embedded vectors to the configured
index automatically.

## Versioning

The schema is expected to evolve.  Node and edge type definitions should be
additive where possible.  Breaking changes to existing types require a new major
schema version.  Each schema file will include a `version` field so producers and
consumers can negotiate compatibility.

Version numbers follow `MAJOR.MINOR.PATCH` semantics.  Adding a new optional
property bumps the MINOR version.  Changing required fields or the meaning of an
existing property increments MAJOR.  The PATCH component is reserved for
documentation fixes or clarifications that do not alter validation rules.

### Migration Notes

Historical event ledgers can be upgraded after a schema change using the
`ume.migrate_events` utility:

```bash
poetry run python -m ume.migrate_events --source ledger > migrated_events.json
```

This command reads stored event envelopes and re-emits them with the latest
`schema_version`, ensuring new node and edge definitions like `User` or
`SHARED_WITH` are applied consistently.

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

- ``register_schema <version> <schema_path> <proto_module>`` – load an external
  YAML schema file and associated Protobuf module at runtime.
- ``migrate_schema <old_version> <new_version>`` – apply ``upgrade_schema`` to
  the current graph.
