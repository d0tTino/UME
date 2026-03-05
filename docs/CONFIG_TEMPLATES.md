# Configuration Templates

The following examples illustrate minimal configuration files for common environments.
These YAML snippets are intended as starting points and can be adapted to suit
your infrastructure.

## Development
```yaml
db_path: ":memory:"
neo4j:
  uri: bolt://localhost:7687
  user: neo4j
  password: changeme
arango:
  url: http://localhost:8529
  user: root
  password: password
  db: ume
event_store:
  type: in-memory
```

## Staging
```yaml
db_path: staging.db
neo4j:
  uri: bolt://staging-neo4j:7687
  user: neo4j
  password: secret
arango:
  url: http://staging-arango:8529
  user: root
  password: secret
  db: ume
event_store:
  type: kafka
  brokers:
    - localhost:9092
```

## Production
```yaml
db_path: /var/lib/ume/graph.db
neo4j:
  uri: bolt://neo4j.prod.example.com:7687
  user: neo4j
  password: prodpass
arango:
  url: http://arango.prod.example.com:8529
  user: root
  password: prodpass
  db: ume
event_store:
  type: kafka
  brokers:
    - kafka1.prod.example.com:9092
    - kafka2.prod.example.com:9092
```

## Stream Processor
```yaml
faust:
  broker: "kafka://localhost:9092"
  input_topic: "ume-clean-events"
  edge_topic: "ume_edges"
  node_topic: "ume_nodes"
  fallback_topic: "ume-misc-events"
  dead_letter_topic: "ume-dead-letter-events"
```

## Environment Variables

UME can also be configured via environment variables or a `.env` file. The table
below lists all available variables and their default values.

| Variable | Default | Description |
| --- | --- | --- |
| `UME_DB_PATH` | `ume_graph.db` | SQLite database used by `PersistentGraph`. |
| `UME_GRAPH_BACKEND` | `sqlite` | Backend for graph storage (`sqlite`, `postgres`, `redis`, `neo4j`, or `arango`). |

Valid values for `UME_GRAPH_BACKEND` are:

- `sqlite` – local SQLite database via `PersistentGraph`.
- `postgres` – PostgreSQL backend using `PostgresGraph`.
- `redis` – Redis-backed `RedisGraphAdapter`.
- `neo4j` – Neo4j graph database via `Neo4jGraph`.
- `arango` – ArangoDB backend using `ArangoGraph`.
| `UME_SNAPSHOT_PATH` | `ume_snapshot.json` | Path to graph snapshot file. |
| `UME_SNAPSHOT_DIR` | `.` | Directory that snapshot APIs will accept paths from. |
| `UME_AUDIT_LOG_PATH` | `audit.log` | Location of the audit log. |
| `UME_AUDIT_SIGNING_KEY` | `default-key` | Key used to sign audit entries. Must be changed from the default or startup will fail. |
| `UME_ENCRYPTION_ENABLED` | `False` | If `True`, encrypt audit, ledger, and dossier files with `UME_ENCRYPTION_KEY`. |
| `UME_ENCRYPTION_KEY` | *(unset)* | Base64 Fernet key used when encryption is enabled. |
| `UME_AGENT_ID` | `SYSTEM` | Identifier recorded in audit logs. |
| `UME_EMBED_MODEL` | `all-MiniLM-L6-v2` | SentenceTransformer model name. |
| `UME_CLI_DB` | `ume_graph.db` | Database path used by the CLI. |
| `UME_DOSSIER_PATH` | `~/.ume_dossier` | Directory containing YAML files for the user dossier. Defaults to `~/.ume_dossier` when unset. |
| `UME_ROLE` | *(unset)* | Optional role for the CLI. |
| `UME_API_ROLE` | *(unset)* | Optional role applied by the API server. |
| `UME_RATE_LIMIT_REDIS` | *(unset)* | Redis URL for API rate limiting. |
| `UME_VECTOR_BACKEND` | `faiss` | Vector store backend (`faiss`, `chroma`, `milvus`, or plugin such as `memory`). |

Valid values for `UME_VECTOR_BACKEND` are:

- `faiss` – local FAISS index written to `UME_VECTOR_INDEX`.
- `chroma` – lightweight in-memory backend.
- `milvus` – remote Milvus database service (requires optional `pymilvus` package; falls back to `chroma` if missing).
- `memory` – example plugin backend for testing.

When using `milvus`, set `UME_MILVUS_URI` to the server endpoint. Optional
`UME_MILVUS_USER` and `UME_MILVUS_PASSWORD` may be provided when authentication
is enabled.
| `UME_VECTOR_DIM` | `1536` | Dimension of embedding vectors. |
| `UME_VECTOR_INDEX` | `vectors.faiss` | Vector index file path. |
| `UME_VECTOR_USE_GPU` | `False` | Whether to build the index on a GPU. |
| `UME_VECTOR_GPU_MEM_MB` | `256` | GPU memory used when building the index. |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Comma separated list of Kafka brokers. |
| `KAFKA_RAW_EVENTS_TOPIC` | `ume-raw-events` | Topic for raw events. |
| `KAFKA_CLEAN_EVENTS_TOPIC` | `ume-clean-events` | Topic for sanitized events. |
| `KAFKA_QUARANTINE_TOPIC` | `ume-quarantine-events` | Topic for rejected events. |
| `KAFKA_EDGE_TOPIC` | `ume_edges` | Topic for processed edges. |
| `KAFKA_NODE_TOPIC` | `ume_nodes` | Topic for processed nodes. |
| `KAFKA_ROUTING_FALLBACK_TOPIC` | `ume-misc-events` | Fallback topic for unknown/custom events without an explicit schema topic. |
| `KAFKA_ROUTING_DEAD_LETTER_TOPIC` | `ume-dead-letter-events` | Dead-letter topic for policy-denied events. |
| `KAFKA_GROUP_ID` | `ume_client_group` | Consumer group for demos and stream processors. |
| `KAFKA_PRIVACY_AGENT_GROUP_ID` | `ume-privacy-agent-group` | Consumer group for the privacy agent. |
| `KAFKA_PRODUCER_BATCH_SIZE` | `10` | Number of messages before producer flush. |
| `UME_OAUTH_USERNAME` | `ume` | Username for obtaining OAuth tokens. |
| `UME_OAUTH_PASSWORD` | `password` | Password for obtaining OAuth tokens. |
| `UME_OAUTH_ROLE` | `AnalyticsAgent` | Role assigned to issued tokens. |
| `UME_OAUTH_TTL` | `3600` | Lifetime of issued tokens in seconds. |
| `UME_GRPC_TOKEN` | *(unset)* | Bearer token required by the gRPC server. If empty, the server logs a warning and rejects requests. |
| `UME_API_TOKEN` | *(unset)* | Required token for HTTP API requests. |
| `UME_LOG_LEVEL` | `INFO` | Logging level used by `configure_logging`. |
| `UME_LOG_JSON` | `False` | Output logs as JSON lines when set to `True`. |
| `UME_GRAPH_RETENTION_DAYS` | `30` | Age in days before old nodes/edges are purged. |
| `WATCH_PATHS` | `['.']` | Paths watched by the dev-log watcher. |
| `UME_ACTIVITY_LOG_ENABLED` | `True` | Disable to skip registering `dossier_activity_hook`. |
| `DAG_RESOURCES` | `{'cpu': 1, 'io': 1}` | Resource slots for the DAG service. |
| `KAFKA_CA_CERT` | *(unset)* | CA certificate for Kafka TLS. |
| `KAFKA_CLIENT_CERT` | *(unset)* | Client certificate for Kafka TLS. |
| `KAFKA_CLIENT_KEY` | *(unset)* | Client key for Kafka TLS. |
| `LLM_FERRY_API_URL` | `https://example.com/api` | Endpoint for the `LLMFerry` listener. |
| `LLM_FERRY_API_KEY` | *(unset)* | API key used by `LLMFerry` for authentication. |
| `UME_OPA_URL` | *(unset)* | Base URL of a remote OPA server used by `RegoPolicyEngine`. |
| `UME_OPA_TOKEN` | *(unset)* | Bearer token sent with OPA requests. |
| `UME_POLICY_GRAPH_MAX_SNAPSHOT_NODES` | `500` | If graph node count is <= this limit, policy input includes a full graph snapshot. |
| `UME_POLICY_GRAPH_NEIGHBORHOOD_DEPTH` | `1` | Neighborhood hop depth used when a full snapshot is skipped. |
| `UME_POLICY_GRAPH_MAX_NEIGHBORHOOD_NODES` | `200` | Maximum nodes included in neighborhood mode before truncation. |

### OPA/Rego input shape

Requests to OPA use an input document shaped as `{event, graph, actor, source, metadata}`.
`event` contains normalized event fields; `graph` contains either `mode: snapshot`
with full `nodes`/`edges` or `mode: neighborhood` with bounded context;
`actor` and `source` provide principal and ingress metadata.

`UME_RATE_LIMIT_REDIS` may be set to a Redis URL to enable shared rate limiting.
If unset, the API uses an in-memory limiter.

The dev-log watcher monitors the directories listed in `WATCH_PATHS`. Importing `ume.watchers` enables logging of file events to each dossier's `telemetry/activity.log`.
## Benchmark Hardware
A single-node Dell PowerEdge R7625 with an EPYC 9254P CPU, 256 GB RAM and four NVMe drives was used when validating the Redpanda benchmark.

## Docker Compose Quickstart

The repository ships with a `docker-compose.yml` for spinning up Redpanda
alongside the privacy agent and FastAPI server. The compose file now also
includes an optional `neo4j` service. The `ume-db` volume persists the default
SQLite database and can be repurposed for Neo4j data if desired. To start the
stack:


1. Install Docker and Docker Compose.
2. From the project root run:
   ```bash
   poetry run ume up
   ```
3. Wait until `redpanda`, `neo4j`, and `ume-api` report `healthy` with `docker compose ps`.
4. Inspect logs with `docker compose logs -f ume-api`.
5. Confirm all services report `healthy` with `docker compose ps`.
6. Stop all containers with `docker compose down` when finished.
