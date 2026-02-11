# Event Topic Routing Conventions

The stream processor now derives destination topics from canonical envelope metadata
instead of a fixed event-type lookup. Producer teams should emit canonical fields
that describe event semantics so routing remains stable as new event types are added.

## Canonical metadata used for routing

Routing decisions are computed from `metadata` and `graph` fields in the canonical
envelope:

- `metadata.type_family`: optional semantic family (`node`, `edge`, or custom).
- `metadata.schema_version`: schema version string used for observability and
  compatibility checks.
- `metadata.policy_result`: optional policy verdict. Denied/rejected values are
  routed to dead-letter.
- `metadata.schema.topic` (or `metadata.destination_topic`): optional explicit topic
  override from schema metadata.
- `graph.node_id`, `graph.target_node_id`, `graph.label`: graph semantics used as
  fallback family detection when `type_family` is not present.

## Routing order

The router applies decisions in this order:

1. **Policy deny path**: denied/rejected events go to dead-letter topic.
2. **Schema topic override**: if schema metadata specifies a topic, that topic wins.
3. **Semantic family routing**:
   - `edge` family -> `KAFKA_EDGE_TOPIC`
   - `node` family -> `KAFKA_NODE_TOPIC`
4. **Fallback topic**: unknown/custom events without schema topic ->
   `KAFKA_ROUTING_FALLBACK_TOPIC`.

## Producer recommendations

- Always provide canonical `metadata.event_type`, `metadata.timestamp`, and
  `metadata.schema_version` values.
- Include `metadata.type_family` for custom event names so they route predictably.
- If a custom event requires a dedicated topic, define it in schema metadata using
  `metadata.schema.topic` (or `metadata.destination_topic`).
- Emit `metadata.policy_result` for events already evaluated by policy engines to
  ensure denied data lands in `KAFKA_ROUTING_DEAD_LETTER_TOPIC`.

## Related settings

- `KAFKA_EDGE_TOPIC`
- `KAFKA_NODE_TOPIC`
- `KAFKA_ROUTING_FALLBACK_TOPIC`
- `KAFKA_ROUTING_DEAD_LETTER_TOPIC`
