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

## API Documentation

To explore the API interactively, run the FastAPI server and open the Swagger UI:

```bash
uvicorn ume.api:app
```

Then visit [http://localhost:8000/docs](http://localhost:8000/docs) in your browser.
The raw OpenAPI schema is available at
[http://localhost:8000/openapi.json](http://localhost:8000/openapi.json).
