"""Metric definitions used throughout UME.

The project relies on ``prometheus_client`` for metric collection. However the
test environment used for kata exercises doesn't always provide a compatible
version of that library (missing symbols such as ``Exemplar`` have been
observed). Importing the package in those situations would raise an
``ImportError`` and prevent the rest of the module from being imported. To make
the module robust, we fall back to lightweight no-op stubs when the real
library isn't available.
"""

from typing import Any, Iterable

_PromCounter: Any
_PromHistogram: Any
_PromGauge: Any

Counter: Any
Histogram: Any
Gauge: Any


try:
    from prometheus_client import (
        Counter as _PromCounter,
        Histogram as _PromHistogram,
        Gauge as _PromGauge,
    )
    if not all(hasattr(m, "clear") for m in (_PromCounter, _PromHistogram, _PromGauge)):
        raise ImportError("prometheus_client stubs lack clear()")
except Exception:  # pragma: no cover - library missing or incompatible
    _PromCounter = _PromHistogram = _PromGauge = None

if _PromCounter is None:
    class _Sample:
        def __init__(self, name: str, labels: dict[str, str], value: float) -> None:
            self.name = name
            self.labels = labels
            self.value = value

    class _MetricChild:
        def __init__(self, parent: "_Metric", labels: dict[str, str]):
            self._parent = parent
            self._labels = tuple(labels.get(n, "") for n in parent.labelnames)

        def inc(self, amount: float = 1) -> None:
            self._parent._inc(self._labels, amount)

        def observe(self, amount: float) -> None:
            self._parent._observe(self._labels, amount)

        def set(self, value: float) -> None:
            self._parent._set(self._labels, value)

    class _Metric:
        """Minimal in-memory metric used when prometheus_client isn't available."""

        def __init__(
            self,
            name: str,
            doc: str,
            labelnames: Iterable[str] = (),
            kind: str = "counter",
        ) -> None:
            self.name = name
            self.doc = doc
            self.labelnames = tuple(labelnames)
            self.kind = kind  # 'counter', 'histogram', 'gauge'
            self.values: dict[tuple[str, ...], float] = {}
            self.sums: dict[tuple[str, ...], float] = {}

        def labels(self, *args: str, **kwargs: str) -> _MetricChild:
            labels = kwargs or dict(zip(self.labelnames, args))
            return _MetricChild(self, labels)

        def clear(self) -> None:
            self.values.clear()
            self.sums.clear()

        # internal helpers operating on label keys
        def _inc(self, key: tuple[str, ...], amount: float) -> None:
            self.values[key] = self.values.get(key, 0.0) + amount

        def _observe(self, key: tuple[str, ...], amount: float) -> None:
            self.values[key] = self.values.get(key, 0.0) + 1.0
            self.sums[key] = self.sums.get(key, 0.0) + amount

        def _set(self, key: tuple[str, ...], value: float) -> None:
            self.values[key] = value

        # public methods for unlabelled metrics
        def inc(self, amount: float = 1) -> None:
            self._inc((), amount)

        def observe(self, amount: float) -> None:
            self._observe((), amount)

        def set(self, value: float) -> None:
            self._set((), value)

        def collect(self) -> list[object]:  # pragma: no cover - simple stub
            class _Collected:
                def __init__(self, samples: list[_Sample]):
                    self.samples = samples

            samples: list[_Sample] = []
            for key, val in self.values.items():
                labels = dict(zip(self.labelnames, key))
                if self.kind == "counter":
                    samples.append(_Sample(f"{self.name}_total", labels, val))
                elif self.kind == "histogram":
                    samples.append(_Sample(f"{self.name}_count", labels, val))
                    samples.append(
                        _Sample(f"{self.name}_sum", labels, self.sums.get(key, 0.0))
                    )
                else:  # gauge
                    samples.append(_Sample(self.name, labels, val))
            return [_Collected(samples)]

    class _Counter(_Metric):
        def __init__(self, name: str, doc: str, labelnames: Iterable[str] = ()) -> None:
            super().__init__(name, doc, labelnames, kind="counter")

    class _Histogram(_Metric):
        def __init__(self, name: str, doc: str, labelnames: Iterable[str] = ()) -> None:
            super().__init__(name, doc, labelnames, kind="histogram")

    class _Gauge(_Metric):
        def __init__(self, name: str, doc: str, labelnames: Iterable[str] = ()) -> None:
            super().__init__(name, doc, labelnames, kind="gauge")

    Counter = _Counter
    Histogram = _Histogram
    Gauge = _Gauge
else:
    Counter = _PromCounter
    Histogram = _PromHistogram
    Gauge = _PromGauge
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
