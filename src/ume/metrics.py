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
