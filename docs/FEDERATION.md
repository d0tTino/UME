# Federating UME Across Data Centers

This document outlines several approaches for running multiple UME deployments in different regions while keeping their graphs synchronized.

## Event Log Replication
Replicate Kafka/Redpanda topics between sites (for example via MirrorMaker or Redpanda's replication tools).

**Pros**
- Each instance processes the same event stream and converges on the same graph state.
- Natural fit for event sourcing and allows independent recovery.

**Cons**
- Requires reliable cross-region messaging infrastructure.
- Network latency can delay propagation of new events.

## Periodic Graph Snapshots
Periodically export the graph from one region and load it into others.

**Pros**
- Simple to implement using existing snapshot functionality.
- Works even if event streams are not continuously replicated.

**Cons**
- Snapshots may grow large as the graph expands.
- Merging concurrent changes from multiple regions can be complex.

## Shared Distributed Database
Use a multi-region database as the backing store for the graph (e.g., CockroachDB or Yugabyte).

**Pros**
- Single source of truth for all deployments.
- No custom replication logic required.

**Cons**
- Depends on a distributed database with global consistency.
- Potentially higher operational complexity and cost.
