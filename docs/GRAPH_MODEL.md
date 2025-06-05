# UME Graph Model

This document defines the initial ontology used by the Universal Memory Engine.
It describes node types, edge labels and general versioning guidelines for the
graph representation.

## Node Types

### UserMemory
Represents memory items about a specific user.  A single user may have many
memory nodes capturing different experiences or facts.

Properties:
- `user_id` *(string, required)*: Unique identifier of the user.
- `data` *(object)*: Free form attributes describing the memory.  Example:
  `{"text": "Alice ordered coffee"}`.

### AgentIntent
Captures an intention produced by an agent.

Properties:
- `intent_id` *(string, required)*: Unique identifier for the intent.
- `description` *(string)*: Short human friendly description of the action.
  Example: `"schedule meeting"`.

### PerceptualContext
Stores sensory observations that provide context for reasoning.

Properties:
- `context_id` *(string, required)*: Unique identifier for the context entry.
- `modality` *(string)*: E.g. `vision`, `audio`.
- `payload` *(object)*: Raw or processed perceptual data.
  Example: `{"image": "base64..."}`.

## Edge Labels

- `REMEMBERS`: connects a `UserMemory` node to an `AgentIntent` that created it.
- `ASSOCIATED_WITH`: Generic association between any two nodes.
- `CAUSES`: Expresses a causal relationship from one event or context to another.

Example edge creation event:

```json
{
  "event_type": "CREATE_EDGE",
  "timestamp": 1678954321,
  "node_id": "intent123",
  "target_node_id": "memory789",
  "label": "REMEMBERS",
  "payload": {}
}
```

Each edge is directed and labeled and may carry optional properties in the
future.  At minimum an edge stores the source node ID, target node ID and
its label.

## Versioning

The schema is expected to evolve.  Node and edge type definitions should be
additive where possible.  Breaking changes to existing types require a new major
schema version.  Each schema file will include a `version` field so producers and
consumers can negotiate compatibility.

Version numbers follow `MAJOR.MINOR.PATCH` semantics.  Adding a new optional
property bumps the MINOR version.  Changing required fields or the meaning of an
existing property increments MAJOR.  The PATCH component is reserved for
documentation fixes or clarifications that do not alter validation rules.
