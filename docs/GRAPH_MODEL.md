# UME Graph Model

This document defines the initial ontology used by the Universal Memory Engine.
It describes node types, edge labels and general versioning guidelines for the
graph representation.

## Node Types

### UserMemory
Represents memory items about a specific user.

Properties:
- `user_id` *(string, required)*: unique identifier of the user.
- `data` *(object)*: free form attributes describing the memory.

### AgentIntent
Captures an intention produced by an agent.

Properties:
- `intent_id` *(string, required)*: unique identifier for the intent.
- `description` *(string)*: short human friendly description.

### PerceptualContext
Stores sensory observations that provide context for reasoning.

Properties:
- `context_id` *(string, required)*: unique identifier.
- `modality` *(string)*: e.g. `vision`, `audio`.
- `payload` *(object)*: raw or processed perceptual data.

## Edge Labels

- `REMEMBERS`: connects a `UserMemory` node to an `AgentIntent` that created it.
- `ASSOCIATED_WITH`: generic association between any two nodes.
- `CAUSES`: expresses a causal relationship from one event or context to another.

Each edge is directed and labeled and may carry optional properties in the
future.  At minimum an edge stores the source node ID, target node ID and
its label.

## Versioning

The schema is expected to evolve.  Node and edge type definitions should be
additive where possible.  Breaking changes to existing types require a new major
schema version.  Each schema file will include a `version` field so producers and
consumers can negotiate compatibility.
