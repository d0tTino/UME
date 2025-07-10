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
