# Configuration Templates

The following examples illustrate minimal configuration files for common environments.
These YAML snippets are intended as starting points and can be adapted to suit
your infrastructure.

## Development
```yaml
db_path: ":memory:"
event_store:
  type: in-memory
```

## Staging
```yaml
db_path: staging.db
event_store:
  type: kafka
  brokers:
    - localhost:9092
```

## Production
```yaml
db_path: /var/lib/ume/graph.db
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
