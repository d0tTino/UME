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
```

## Environment Variables

UME can also be configured via environment variables or a `.env` file. The table
below lists all available variables and their default values.

| Variable | Default | Description |
| --- | --- | --- |
| `UME_DB_PATH` | `ume_graph.db` | SQLite database used by `PersistentGraph`. |
| `UME_SNAPSHOT_PATH` | `ume_snapshot.json` | Path to graph snapshot file. |
| `UME_AUDIT_LOG_PATH` | `audit.log` | Location of the audit log. |
| `UME_AUDIT_SIGNING_KEY` | `default-key` | Key used to sign audit entries. |
| `UME_AGENT_ID` | `SYSTEM` | Identifier recorded in audit logs. |
| `UME_EMBED_MODEL` | `all-MiniLM-L6-v2` | SentenceTransformer model name. |
| `UME_CLI_DB` | `ume_graph.db` | Database path used by the CLI. |
| `UME_ROLE` | *(unset)* | Optional role for the CLI. |
| `UME_API_ROLE` | *(unset)* | Optional role applied by the API server. |
| `UME_VECTOR_DIM` | `1536` | Dimension of embedding vectors. |
| `UME_VECTOR_INDEX` | `vectors.faiss` | FAISS index file path. |
| `UME_VECTOR_USE_GPU` | `False` | Whether to build the index on a GPU. |
| `UME_VECTOR_GPU_MEM_MB` | `256` | GPU memory used when building the index. |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Comma separated list of Kafka brokers. |
| `KAFKA_RAW_EVENTS_TOPIC` | `ume-raw-events` | Topic for raw events. |
| `KAFKA_CLEAN_EVENTS_TOPIC` | `ume-clean-events` | Topic for sanitized events. |
| `KAFKA_QUARANTINE_TOPIC` | `ume-quarantine-events` | Topic for rejected events. |
| `KAFKA_EDGE_TOPIC` | `ume_edges` | Topic for processed edges. |
| `KAFKA_NODE_TOPIC` | `ume_nodes` | Topic for processed nodes. |
| `KAFKA_GROUP_ID` | `ume_client_group` | Consumer group for demos and stream processors. |
| `KAFKA_PRIVACY_AGENT_GROUP_ID` | `ume-privacy-agent-group` | Consumer group for the privacy agent. |
| `KAFKA_PRODUCER_BATCH_SIZE` | `10` | Number of messages before producer flush. |
| `UME_OAUTH_USERNAME` | `ume` | Username for obtaining OAuth tokens. |
| `UME_OAUTH_PASSWORD` | `password` | Password for obtaining OAuth tokens. |
| `UME_OAUTH_ROLE` | `AnalyticsAgent` | Role assigned to issued tokens. |
| `UME_LOG_LEVEL` | `INFO` | Logging level used by `configure_logging`. |
| `UME_LOG_JSON` | `False` | Output logs as JSON lines when set to `True`. |
| `UME_GRAPH_RETENTION_DAYS` | `30` | Age in days before old nodes/edges are purged. |
| `WATCH_PATHS` | `['.']` | Paths watched by the dev-log watcher. |
| `DAG_RESOURCES` | `{'cpu': 1, 'io': 1}` | Resource slots for the DAG service. |
| `KAFKA_CA_CERT` | *(unset)* | CA certificate for Kafka TLS. |
| `KAFKA_CLIENT_CERT` | *(unset)* | Client certificate for Kafka TLS. |
| `KAFKA_CLIENT_KEY` | *(unset)* | Client key for Kafka TLS. |
| `LLM_FERRY_API_URL` | `https://example.com/api` | Endpoint for the `LLMFerry` listener. |
| `LLM_FERRY_API_KEY` | *(unset)* | API key used by `LLMFerry` for authentication. |
