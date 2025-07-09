# Aging Schedulers

UME exposes several helpers that maintain memory freshness. They can run
side by side and each focuses on a specific layer of storage.

- `start_retention_scheduler` removes graph entries older than the configured
  retention window.
- `start_memory_aging_scheduler` migrates events from episodic to semantic
  memory and optionally archives very old items in cold storage while pruning
  outdated vectors.
- `start_vector_age_scheduler` audits existing vectors and records warnings
  when embeddings exceed the `UME_VECTOR_MAX_AGE_DAYS` threshold.
- `enable_periodic_snapshot` periodically writes the graph to
  `UME_SNAPSHOT_PATH`. Use `enable_snapshot_autosave_and_restore` to restore
  the previous snapshot at startup and schedule future saves.

Applications can start these schedulers independently. Each function returns the
background thread and a stop callback so lifecycles can be coordinated.
