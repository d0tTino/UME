# ADR 0001: Memory Storage Backend

## Status

Accepted

## Context

UME needs a reliable store for the knowledge graph and embeddings. Early
development prioritizes ease of setup for contributors and automated tests.

## Decision

SQLite will be used as the default graph database. It requires no separate
service and is bundled with Python, making local development and CI simple. The
architecture allows swapping out the adapter later for databases like PostgreSQL
or Neo4j if more scalability is required.

## Consequences

Using SQLite keeps dependencies minimal and simplifies onboarding, but it is not
well suited for high concurrency or very large datasets. Future ADRs may revisit
this choice when performance requirements grow.
