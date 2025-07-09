# API Reference

This document summarizes the HTTP routes exposed by the UME FastAPI application.
Acquire a token from `/token` using the OAuth2 password flow and include it as a
`Bearer` token in the `Authorization` header. Tokens expire after `UME_OAUTH_TTL` seconds.

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

### POST `/snapshot/save`
Write the entire graph state to a JSON file.
- **Body**: `{"path": "file.json"}`

### POST `/snapshot/load`
Replace the current graph with the contents of a snapshot file.
- **Body**: `{"path": "file.json"}`

### GET `/ledger/events`
List entries in the event ledger.
- **Query parameters**: `start` (default `0`), optional `end`, optional `limit`.

### GET `/ledger/replay`
Return a snapshot of the graph reconstructed from ledger events.
- **Query parameters**: optional `end_offset`, optional `end_timestamp`.

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

### POST `/events`
Validate and apply an event to the graph.

**Body Parameters**

- `event_type` – the name of the event, e.g. `CREATE_NODE`
- `timestamp` – integer timestamp for the event
- `node_id` – ID of the acting node when applicable
- `target_node_id` – ID of the target node when applicable
- `label` – edge label if the event involves an edge
- `payload` – any additional structured data

Example request:

```bash
curl -X POST http://localhost:8000/events \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"event_type":"CREATE_NODE","timestamp":1,"node_id":"n1","payload":{"node_id":"n1"}}'
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

## API Documentation

To explore the API interactively, run the FastAPI server and open the Swagger UI:

```bash
uvicorn ume.api:app
```

Then visit [http://localhost:8000/docs](http://localhost:8000/docs) in your browser.
The raw OpenAPI schema is available at
[http://localhost:8000/openapi.json](http://localhost:8000/openapi.json).
