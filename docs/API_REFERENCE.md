# API Reference


This document summarizes the HTTP routes exposed by the UME FastAPI application.
Acquire a token from `/auth/token` using the OAuth2 password flow and include it as a
`Bearer` token in the `Authorization` header. Tokens expire after `UME_OAUTH_TTL` seconds.

For gRPC clients, send the configured `UME_GRPC_TOKEN` as a bearer token in the
`authorization` metadata. The helper class `AsyncUMEClient` accepts this token
via its `token` argument and attaches it automatically.

## Backend Factory and Plugin Terms

- Graph backend selection uses `UME_GRAPH_BACKEND` with `create_graph_adapter()`.
- Vector backend selection uses `UME_VECTOR_BACKEND` with `create_vector_store()`.
- Plugin entry-point groups:
  - `ume.graph_adapters` for graph backends
  - `ume.vector_backends` for vector backends

## Concept Mapping (legacy -> current)

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


## Event Contract Version Policy

UME event contracts are versioned with semantic versions and validated against JSON Schema bundles under `src/ume/schemas/v{major}`.

### Required vs optional fields

- **Always required (all majors):** `eventType`, `timestamp`.
- **Version 1.x / 2.x:** identity fields (`eventId`, `sourceService`) are optional for compatibility with historical emitters.
- **Version 3.x:** `eventId` and `sourceService` are required on all events; replay transformers can synthesize these when upgrading old ledgers.
- Event-type schemas define additional required fields (`node_id`, `target_node_id`, `label`, `payload`) based on operation type.

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
