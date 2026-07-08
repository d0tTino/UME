# API Reference



> Canonical architecture reference: [`ARCHITECTURE_OVERVIEW.md`](ARCHITECTURE_OVERVIEW.md).
This document summarizes the HTTP routes exposed by the UME FastAPI application.
Acquire a token from `/auth/token` using the OAuth2 password flow and include it as a
`Bearer` token in the `Authorization` header. Tokens expire after `UME_OAUTH_TTL` seconds.

For gRPC clients, send the configured `UME_GRPC_TOKEN` as a bearer token in the
`authorization` metadata. The helper class `AsyncUMEClient` accepts this token
via its `token` argument and attaches it automatically.

## Canonical terminology

Use [`GLOSSARY.md`](GLOSSARY.md) as the single source for canonical terms used in this reference.

## Backend Factory and Plugin Terms

- Graph backend selection uses `UME_GRAPH_BACKEND` with `create_graph_adapter()`.
- Vector backend selection uses `UME_VECTOR_BACKEND` with `create_vector_store()`.
- Plugin entry-point groups:
  - `ume.graph_adapters` for graph backends
  - `ume.vector_backends` for vector backends

## Legacy migration

| Legacy term | Current term/API |
| --- | --- |
| `UME_GRAPH_ADAPTER` | `UME_GRAPH_BACKEND` |
| `get_adapter(...)` | `create_graph_adapter(...)` |

## Graph Request Context Requirements

Graph endpoints now require a `user_id` query parameter that identifies the
requesting principal. Optionally include `group_id` when the caller is acting on
behalf of a delegated team or workspace. The API enforces permissions by
inspecting ownership (`OWNED_BY`) and sharing (`SHARED_WITH`) edges that include
an explicit `permission_level` property. Supported values remain `viewer`,
`editor`, and `public`.

When creating or updating these edges, include the `permission_level` field in
the payload. Omitting it for ownership edges defaults to `editor` for backwards
compatibility, but clients should begin providing it explicitly ahead of schema
version `3.0.0` when the default will be removed.

### Example: Querying Nodes with Context

```bash
curl -G "http://localhost:8000/nodes" \
  -H "Authorization: Bearer <token>" \
  --data-urlencode "user_id=User.u1" \
  --data-urlencode "group_id=Group.eng"
```

Successful responses scope results to the caller's permissions:

```json
{
  "nodes": [
    {
      "id": "resource-42",
      "attributes": {
        "title": "Launch Checklist"
      },
      "edges": [
        {
          "label": "OWNED_BY",
          "target": "User.u1",
          "permission_level": "editor"
        }
      ]
    }
  ]
}
```

Requests made without sufficient permission return an HTTP `403` status with
context about the failing edge check:

```json
{
  "detail": {
    "error": "permission_denied",
    "message": "User.u2 lacks viewer access to resource-42 via Group.eng",
    "required_permission": "viewer"
  }
}
```

> **Migration note:** Update existing clients to supply `user_id`, propagate
> any acting `group_id`, and include `permission_level` on ownership and sharing
> edges before schema version `3.0.0` becomes the default. Requests missing this
> context will be rejected once the migration window closes.

The gRPC service also exposes `SaveSnapshot` and `LoadSnapshot` RPCs which
mirror the `/snapshot/save` and `/snapshot/load` HTTP endpoints. Both accept a
`SnapshotPath` message containing the target file path and return an empty
response on success.


## Authoritative External Producer Contract

This section is the single authoritative contract for producers that emit events into UME. Other documents should link here instead of restating the producer payload shape.

### Boundary summary

1. **External contract accepted at ingress:** producers send one flat JSON object with the field names listed below.
2. **One canonical transform:** UME converts that external payload with `ume.events.contract.canonicalize_event(...)`. Legacy transports must first be upgraded by `ume.events.legacy_transform.apply_legacy_transform(...)`.
3. **Parser accepts only canonical form:** `ume.kernel.events.parse_event(...)` accepts only `metadata` + `graph` + `payload`; it rejects producer payloads and legacy wrappers.

### Producer payload fields

Required for every event:

- `eventType` — event operation name, for example `CREATE_NODE` or `CREATE_EDGE`.
- `timestamp` — Unix timestamp integer or ISO-8601 string.

Recommended for all producers and required by schema version `3.x`:

- `eventId` — stable producer event identifier.
- `sourceService` — stable service name for the producer.

Optional metadata fields:

- `schemaVersion` — semantic contract version, for example `3.0.0`.
- `producerId` — producer instance or principal identifier.
- `tenant` — tenant or workspace identifier.
- `signature` — producer signature or integrity token.
- `correlationId` — request or workflow correlation identifier.
- `subjectEntity` — object containing `id` and `type` for the event subject.

Graph fields, required according to event type:

- `node_id` — source node identifier.
- `target_node_id` — target node identifier for edge operations.
- `label` — edge label for edge operations.

Payload field:

- `payload` — event-specific object. It may be omitted only when optional for the event type.

### Producer example

```json
{
  "eventId": "evt-123",
  "eventType": "CREATE_NODE",
  "timestamp": "2026-06-22T00:00:00Z",
  "schemaVersion": "3.0.0",
  "sourceService": "example-producer",
  "producerId": "producer-a",
  "tenant": "tenant-1",
  "correlationId": "corr-123",
  "subjectEntity": {"id": "User.u1", "type": "User"},
  "node_id": "Document.1",
  "payload": {
    "node_id": "Document.1",
    "attributes": {"title": "Launch Checklist"}
  }
}
```

### Canonical parser form

After the one canonical transform, parsers receive this internal shape:

```json
{
  "metadata": {
    "event_id": "evt-123",
    "event_type": "CREATE_NODE",
    "timestamp": "2026-06-22T00:00:00Z",
    "schema_version": "3.0.0",
    "source": "example-producer",
    "producer_id": "producer-a",
    "tenant": "tenant-1",
    "producer_signature": null,
    "correlation_ids": {"correlation_id": "corr-123"},
    "subject_entity": {"id": "User.u1", "type": "User"}
  },
  "graph": {
    "node_id": "Document.1",
    "target_node_id": null,
    "label": null
  },
  "payload": {
    "node_id": "Document.1",
    "attributes": {"title": "Launch Checklist"}
  }
}
```

### Legacy migration: historical inputs only

Historical payloads may contain a nested `event` wrapper or legacy producer metadata aliases such as `event_type`, `event_id`, `schema_version`, `source`, `producer_signature`, `correlation_id`, and `subject_entity`. Those names are not accepted at new ingress. They are permitted only in documented legacy migration contexts and must be transformed once with `apply_legacy_transform(...)` before canonicalization.

Canonical migration path for historical payloads:

1. `ume.events.legacy_transform.apply_legacy_transform(...)`
2. `ume.events.contract.canonicalize_event(...)`
3. `ume.kernel.events.parse_event(...)`

### Producer migration matrix (legacy/flat -> canonical parser form)

| Producer field | Canonical parser field |
| --- | --- |
| `eventType` | `metadata.event_type` |
| `eventId` | `metadata.event_id` |
| `timestamp` | `metadata.timestamp` |
| `schemaVersion` | `metadata.schema_version` |
| `sourceService` | `metadata.source` |
| `producerId` | `metadata.producer_id` |
| `tenant` | `metadata.tenant` |
| `signature` | `metadata.producer_signature` |
| `correlationId` | `metadata.correlation_ids.correlation_id` |
| `subjectEntity` | `metadata.subject_entity` |
| `node_id` | `graph.node_id` |
| `target_node_id` | `graph.target_node_id` |
| `label` | `graph.label` |
| `payload` | `payload` |

### `parse_event` error examples

- `parse_event expects canonicalized data with 'metadata', 'graph', and 'payload'; apply ume.events.legacy_transform before canonicalization for historical transport shapes`
- `Missing required event field: eventType`
- `Invalid type for 'payload': expected dict, got list`
- `Invalid timestamp format`
- `Missing required fields for CREATE_EDGE event: node_id, target_node_id, label`
- `Missing required field 'payload.attributes' for UPDATE_NODE_ATTRIBUTES event.`

## Event Contract Version Policy

UME event contracts are versioned with semantic versions and validated against JSON Schema bundles under `src/ume/schemas/v{major}`.

### Required vs optional fields

- **Always required (all majors):** `eventType`, `timestamp`.
- **Version 1.x / 2.x:** identity fields (`eventId`, `sourceService`) are optional for compatibility with historical emitters.
- **Version 3.x:** `eventId` and `sourceService` are required on all events; replay transformers can synthesize these when upgrading old ledgers.

### Additive vs breaking changes

- **Additive change (minor/patch):** adding optional fields, widening enum choices, adding optional payload keys.
- **Breaking change (major):** removing required fields, changing field meaning/type incompatibly, or making previously optional fields required.
- Breaking changes must include explicit migration transformers in `src/ume/events/versioning.py` and pass compatibility checks.

### Deprecation window

- Contract fields targeted for removal are first marked deprecated for **two minor releases** (or **90 days**, whichever is longer).
- During deprecation, producers should emit both old/new representations when possible.
- Removal only occurs in the next major bundle after migration guidance and replay transforms are available.

### Supported schema transitions

UME supports only adjacent major-version replay transforms in both directions:

- ✅ Supported upgrades: `1.x -> 2.x`, `2.x -> 3.x`.
- ✅ Supported downgrades: `3.x -> 2.x`, `2.x -> 1.x`.
- ❌ Unsupported jumps: `1.x -> 3.x` and `3.x -> 1.x` as single-step transforms. These must be performed as chained adjacent transforms.
- ❌ Unsupported unknown majors (for example `4.x`) until an explicit transform path is added.

Live ingress resolves active schema once from event metadata (`metadata.schema_version`) and uses that same resolved version for policy evaluation and projection in-process.

## Ingestion API

The standalone ingestion service listens on port `8001` and publishes raw events to Kafka.

Deterministic projection behavior and invalid-event handling rules are documented in
[`docs/PROJECTION_ENGINE.md`](PROJECTION_ENGINE.md).

### POST `/events` (ingestion)
Validate the request body and forward the event to the `ume-raw-events` topic.

## Endpoints

### GET `/query`
Execute a Cypher query.
- **Query parameters**: `cypher` – the Cypher statement.

### POST `/analytics/shortest_path`
Return the shortest path between two nodes.
- **Body**: `{"source": "id", "target": "id"}`

### POST `/analytics/path`
Find a path subject to optional constraints.
- **Body fields**: `source`, `target`, optional `max_depth`, `edge_label`, `since_timestamp`.

### POST `/analytics/subgraph`
Extract a subgraph from a starting node.
- **Body fields**: `start`, `depth`, optional `edge_label`, `since_timestamp`.

### POST `/redact/node/{node_id}`
Redact a node by ID.

### POST `/redact/edge`
Redact an edge.
- **Body**: `{"source": "id", "target": "id", "label": "L"}`

### POST `/nodes`
Create a new node.
- **Body**: `{"id": "id", "attributes": {...}}`

### PATCH `/nodes/{node_id}`
Update a node's attributes.
- **Body**: `{"attributes": {...}}`

### DELETE `/nodes/{node_id}`
Remove a node from the graph.

### POST `/edges`
Create an edge.
- **Body**: `{"source": "id", "target": "id", "label": "L"}`

### DELETE `/edges/{source}/{target}/{label}`
Delete an edge.

### GET `/entities/{type}/{id}`
Return node `id` if its `type` attribute matches `type`.

```bash
curl -X GET http://localhost:8000/entities/user/u1 \
  -H "Authorization: Bearer <token>"
```

### POST `/snapshot/save`
Write the entire graph state to a JSON file.
- **Body**: `{"path": "file.json"}`
Example request:

```bash
curl -X POST http://localhost:8000/snapshot/save \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"path":"backup.json"}'
```

### POST `/snapshot/load`
Replace the current graph with the contents of a snapshot file.
- **Body**: `{"path": "file.json"}`
Example request:

```bash
curl -X POST http://localhost:8000/snapshot/load \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"path":"backup.json"}'
```

### GET `/graph/digest/stream`
Consume real-time graph digest events via SSE.
- **Auth**: bearer token required.
- **Query parameters**:
  - `cursor` (optional): absolute starting ledger offset.
  - `lastEventId` (optional): reconnect from `lastEventId + 1`.
- **Headers**:
  - `Last-Event-ID` (optional): standard SSE resume marker; takes precedence over `lastEventId`.
- **SSE events**:
  - `graph_digest`: payload follows `ume.realtime_contracts.GraphDigestEvent`.
  - `control`: payload follows `ume.realtime_contracts.GraphDigestControlEvent` with `heartbeat` and `backpressure` kinds.

Example request:

```bash
curl -N "http://localhost:8000/graph/digest/stream?cursor=0"   -H "Authorization: Bearer <token>"   -H "Accept: text/event-stream"
```

See [`docs/REALTIME_STREAMING.md`](REALTIME_STREAMING.md) for the full contract and backpressure behavior.

### GET `/ledger/events`
List entries in the event ledger.
- **Query parameters**: `start` (default `0`), optional `end`, optional `limit`.

### GET `/ledger/replay`
Return a snapshot of the graph reconstructed from ledger events.
- **Query parameters**: optional `end_offset`, optional `end_timestamp`, optional `replay_mode` (`current_policy` or `strict_historical`).
Example request:

```bash
curl -X GET -H "Authorization: Bearer <token>" \
  "http://localhost:8000/ledger/replay?end_offset=50&replay_mode=strict_historical"
```

If `end_timestamp` is supplied, replay stops once an event newer than the
timestamp is encountered.

### GET `/graph/history`
Return a snapshot of the graph as it existed at a past point in time.
- **Query parameters**: optional `offset`, optional `timestamp`, optional `replay_mode` (`current_policy` or `strict_historical`).
Example request:

```bash
curl -X GET -H "Authorization: Bearer <token>" \
  "http://localhost:8000/graph/history?timestamp=1725000000"
```

This endpoint rebuilds the graph up to the provided cutoff and returns it as
JSON.

### GET `/policies`
List available Rego policy files.

### POST `/policies/{path}`
Upload a policy file.
- **Form field**: `file` – the `.rego` file contents.

### DELETE `/policies/{path}`
Delete a policy file.

### POST `/vectors`
Add a vector to the in-memory index.
- **Body**: `{"id": "id", "vector": [0.0, ...]}`

### GET `/vectors/search`
Search for nearest vectors.
- **Query parameters**: repeated `vector` values forming the query vector and optional `k` (defaults to 5).

### POST `/search/semantic`
Return the `k` nearest nodes to a text query.
- **Body**: `{"query": "text", "k": 5}`

```bash
curl -X POST http://localhost:8000/search/semantic \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query":"hello","k":2}'
```

### GET `/vectors/benchmark`
Run a synthetic benchmark against the vector store.
- **Query parameters**: `use_gpu` (boolean, default `false`), `num_vectors` (default `1000`), `num_queries` (default `100`).

### GET `/metrics/summary`
Return a summary of core Prometheus metrics including total request counts and vector index size.

### GET `/dashboard/stats`
Return basic graph and vector index statistics.

### GET `/dashboard/recent_events`
Return recent audit log entries, newest first.
- **Query parameters**: optional `limit` (default `10`).

### GET `/events`
Query events or nodes stored in the graph.
- **Query parameters**:
  - `tag` – return only entries whose `tags` list contains this value.
  - `node_id` – optionally restrict results to a specific node.
  - `limit` – maximum number of results (default `100`).

Example:

```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/events?tag=phishing"
```

### POST `/events`
Validate and apply an event to the graph. This endpoint is also available as
`/store`.

**Body Parameters**

- `eventType` – the name of the event, e.g. `CREATE_NODE`
- `timestamp` – integer timestamp for the event
- `node_id` – ID of the acting node when applicable
- `target_node_id` – ID of the target node when applicable
- `label` – edge label if the event involves an edge
- `payload` – any additional structured data

Text values under `name`, `text` or `content` in a node's attributes are tokenized and stored in a `"tokens"` field. The tokenizer uses `tiktoken` when available.

Example request:

```bash
curl -X POST http://localhost:8000/events \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"eventType":"CREATE_NODE","timestamp":1,"eventId":"evt-1","sourceService":"api-client","node_id":"n1","payload":{"node_id":"n1"}}'
```

### POST `/events/batch`
Apply multiple events sequentially. This endpoint is also available as
`/store/batch`.

Example request:

```bash
curl -X POST http://localhost:8000/events/batch \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '[{"eventType":"CREATE_NODE","timestamp":1,"eventId":"evt-1","sourceService":"api-client","node_id":"n1","payload":{"node_id":"n1"}}]'
```


### GET `/recall`
Retrieve attribute data for the `k` nearest nodes to a query.

**Query Parameters**

- `query` – text used to look up similar vectors (optional)
- `vector` – repeated float values forming the query vector (optional)
- `k` – number of results to return (default `5`)

Example text query:

```bash
curl -X GET -H "Authorization: Bearer <token>" \
  'http://localhost:8000/recall?query=hello&k=2'
```

Example using a vector:

```bash
curl -X GET -H "Authorization: Bearer <token>" \
  'http://localhost:8000/recall?vector=0.1&vector=0.2&k=2'
```

### GET `/dossier/{dossier_id}`
View details for a dossier.

```bash
curl -X GET -H "Authorization: Bearer <token>" \
  http://localhost:8000/dossier/example
```

### POST `/dossier/add-project`
Attach a project to a dossier.

```bash
curl -X POST http://localhost:8000/dossier/add-project \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"dossier_id":"example","project_id":"p1"}'
```

### POST `/dossier/add-value`
Add a personal value entry to the dossier.

```bash
curl -X POST http://localhost:8000/dossier/add-value \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"dossier_id":"example","value":"curiosity"}'
```

### POST `/dossier/add-skill`
Add a skill entry to the dossier.

```bash
curl -X POST http://localhost:8000/dossier/add-skill \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"dossier_id":"example","skill":"python"}'
```

The dossier directory is initialized from template files located under
`src/ume/dossier/dossier_template/` which include `skills.yaml` and
`values.yaml`.

### POST `/v1/calendar/events`
Create a calendar event owned by a user and optionally shared with a group.

**Body fields**

- `title` – event title
- `start_time` – ISO8601 timestamp
- `user_id` – ID of the owning user *(required)*
- `group_id` – ID of the owning group *(optional)*

Example request:

```bash
curl -X POST http://localhost:8000/v1/calendar/events \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Team Meeting","start_time":"2024-03-10T10:00:00Z","user_id":"u1","group_id":"g1"}'
```

### GET `/v1/calendar/events`
List calendar events accessible to a user. Events may also be filtered by group or layer.

**Query parameters**

- `user_id` – ID of the requesting user *(required)*
- `group_id` – limit to events shared with a group *(optional)*
- `layer_id` – limit to events tagged with a calendar layer *(optional)*
- `since` – return events starting at or after this UNIX timestamp *(optional)*

Example request:

```bash
curl -G -H "Authorization: Bearer <token>" \
  --data-urlencode "user_id=u1" \
  --data-urlencode "group_id=g1" \
  http://localhost:8000/v1/calendar/events
```

### POST `/v1/decisions`
Create a decision analysis node.

**Body fields**

- `query` – question being analyzed
- `user_id` – ID of the owning user *(required)*
- `group_id` – ID of the owning group *(optional)*

Example request:

```bash
curl -X POST http://localhost:8000/v1/decisions \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query":"Select mitigation","user_id":"u1","group_id":"g1"}'
```

### POST `/v1/decisions/{analysis_id}/actions`
Attach a proposed action to a decision analysis.

**Body fields**

- `description` – description of the action
- `user_id` – ID of the owning user *(required)*
- `group_id` – ID of the owning group *(optional)*

Example request:

```bash
curl -X POST http://localhost:8000/v1/decisions/123/actions \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"description":"Notify users","user_id":"u1","group_id":"g1"}'
```

### GET `/v1/decisions/{analysis_id}`
Retrieve a decision analysis and its proposed actions.

**Query parameters**

- `user_id` – ID of the requesting user *(required)*
- `group_id` – limit to decisions shared with a group *(optional)*

Example request:

```bash
curl -G -H "Authorization: Bearer <token>" \
  --data-urlencode "user_id=u1" \
  --data-urlencode "group_id=g1" \
  http://localhost:8000/v1/decisions/123
```

### GET `/v1/nodes`
Return node IDs owned by a specific user.

**Query parameters**

- `user_id` – identifier of the owner *(required)*

Example request:

```bash
curl -G -H "Authorization: Bearer <token>" \
  --data-urlencode "user_id=User.u1" \
  http://localhost:8000/v1/nodes
```

### GET `/v1/nodes/shared`
Return node IDs shared with a group.

**Query parameters**

- `group_id` – identifier of the group *(required)*

Example request:

```bash
curl -G -H "Authorization: Bearer <token>" \
  --data-urlencode "group_id=Group.g1" \
  http://localhost:8000/v1/nodes/shared
```

## API Documentation

To explore the API interactively, run the FastAPI server and open the Swagger UI:

```bash
uvicorn ume.api:app
```

Then visit [http://localhost:8000/docs](http://localhost:8000/docs) in your browser.
The raw OpenAPI schema is available at
[http://localhost:8000/openapi.json](http://localhost:8000/openapi.json).


## Legacy migration section

Legacy envelopes and snake_case metadata keys are supported only through `ume.events.legacy_transform.apply_legacy_transform()`. New code paths must not parse both shapes directly.
