from prometheus_client import Counter, Histogram, Gauge

# HTTP metrics
REQUEST_COUNT = Counter(
    "ume_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "ume_request_latency_seconds",
    "Request latency in seconds",
    ["method", "path"],
)

# Vector store metrics
VECTOR_QUERY_LATENCY = Histogram(
    "ume_vector_query_latency_seconds",
    "VectorStore query latency in seconds",
)
VECTOR_INDEX_SIZE = Gauge(
    "ume_vector_index_size",
    "Number of vectors stored in the VectorStore",
)
STALE_VECTOR_WARNINGS = Counter(
    "ume_stale_vector_warning_total",
    "Number of times stale vectors exceeded threshold",
)
STALE_VECTOR_COUNT = Gauge(
    "ume_stale_vector_count",
    "Current number of vectors exceeding the freshness limit",
)

# Ingestion metrics
INGEST_EVENTS_TOTAL = Counter(
    "ume_ingest_events_total",
    "Number of ingested events by type",
    ["event_type"],
)

# Endpoint latency metrics
SEMANTIC_SEARCH_LATENCY = Histogram(
    "ume_semantic_search_latency_seconds",
    "Latency of /search/semantic in seconds",
)

# Recall metrics
RECALL_SCORE = Histogram(
    "ume_recall_score",
    "Distance between the query vector and recalled node embeddings",
)

# Reliability metrics
RESPONSE_CONFIDENCE = Histogram(
    "ume_response_confidence",
    "Confidence scores for analytics responses",
)
FALSE_TEXT_RATE = Counter(
    "ume_false_text_total",
    "Number of low-confidence items filtered",
)

# Additional recall metrics
RECALL_LATENCY = Histogram(
    "ume_recall_latency_seconds",
    "Latency of recall operations in seconds",
)
RECALL_LATENCY_MS = Histogram(
    "ume_recall_latency_ms",
    "Latency of recall operations in milliseconds",
)

# Ledger maintenance metrics
LEDGER_COMPACTED_BYTES = Gauge(
    "ume_ledger_compacted_bytes",
    "Bytes removed during the most recent ledger compaction",
)

__all__ = [
    "REQUEST_COUNT",
    "REQUEST_LATENCY",
    "VECTOR_QUERY_LATENCY",
    "VECTOR_INDEX_SIZE",
    "STALE_VECTOR_WARNINGS",
    "STALE_VECTOR_COUNT",
    "RECALL_SCORE",
    "RESPONSE_CONFIDENCE",
    "FALSE_TEXT_RATE",
    "RECALL_LATENCY",
    "RECALL_LATENCY_MS",
    "LEDGER_COMPACTED_BYTES",
    "INGEST_EVENTS_TOTAL",
    "SEMANTIC_SEARCH_LATENCY",
]
