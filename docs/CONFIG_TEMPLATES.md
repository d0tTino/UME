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
  input_topic: "ume_demo"
  edge_topic: "ume_edges"
  node_topic: "ume_nodes"
```
