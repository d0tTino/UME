# Event Topic Routing Conventions


> Canonical architecture reference: [`ARCHITECTURE_OVERVIEW.md`](ARCHITECTURE_OVERVIEW.md).
The stream processor derives destination topics from canonical metadata and publishes
canonical outbound envelopes with routing metadata attached. This keeps downstream
services from recomputing policy/routing context.

## Canonical metadata used for routing

Routing decisions are computed from `metadata` and `graph` fields:

- `metadata.type_family`: optional semantic family (`node`, `edge`, or custom).
- `metadata.schema_version`: schema version used for compatibility and observability.
- `metadata.policy_result`: policy verdict (`applied`, `rejected`, `quarantined`, etc.).
- `metadata.schema.topic` (or `metadata.destination_topic`): optional explicit topic
  override from schema metadata.
- `graph.node_id`, `graph.target_node_id`, `graph.label`: graph semantics used as
  fallback family detection when `type_family` is missing.

## Routing order

The router applies decisions in this order:

1. **Policy DLQ path**: deny/reject/quarantine-style outcomes route to dead-letter.
2. **Schema topic override**: if schema metadata specifies a topic, that topic wins.
3. **Semantic family routing**:
   - `edge` family -> `KAFKA_EDGE_TOPIC`
   - `node` family -> `KAFKA_NODE_TOPIC`
4. **Fallback topic**: unknown/custom events without schema topic ->
   `KAFKA_ROUTING_FALLBACK_TOPIC`.

## Outbound event contract

All published events (success, reject, quarantine, malformed input) use a consistent
envelope with canonical fields and routing metadata:

```json
{
  "metadata": {
    "event_type": "CREATE_NODE",
    "timestamp": 1736000000,
    "policy_result": "applied",
    "schema_version": "v1",
    "type_family": "node",
    "routing": {
      "topic": "ume_nodes",
      "reason": "node_family",
      "family": "node",
      "schema_version": "v1",
      "policy_result": "applied"
    }
  },
  "graph": {
    "node_id": "n1"
  },
  "payload": {}
}
```

### DLQ envelope fields

When canonical data is unavailable (for example malformed JSON or transport validation
failure), the stream processor publishes a DLQ envelope with:

- `metadata.policy_result`, `metadata.schema_version`, and `metadata.type_family`
- `metadata.routing` object with final topic + reason
- `dlq.stage`, `dlq.reason`, and optional `dlq.details`

Example malformed input payload:

```json
{
  "metadata": {
    "event_type": "UNKNOWN_EVENT",
    "timestamp": null,
    "policy_result": "rejected",
    "schema_version": "unknown",
    "type_family": "unknown",
    "routing": {
      "topic": "ume-dead-letter-events",
      "reason": "policy_denied",
      "family": "unknown",
      "schema_version": null,
      "policy_result": "rejected"
    }
  },
  "graph": {},
  "dlq": {
    "stage": "decode",
    "reason": "malformed_json",
    "details": {
      "raw_payload_present": true
    }
  }
}
```

## Related settings

- `KAFKA_EDGE_TOPIC`
- `KAFKA_NODE_TOPIC`
- `KAFKA_ROUTING_FALLBACK_TOPIC`
- `KAFKA_ROUTING_DEAD_LETTER_TOPIC`
