"""Minimal in-memory Prometheus client stubs for tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple


@dataclass
class Sample:
    name: str
    labels: Dict[str, str]
    value: float


class _MetricChild:
    def __init__(self, parent: "_Metric", labels: Dict[str, str]):
        self._parent = parent
        self._labels = tuple(labels.get(n, "") for n in parent.labelnames)

    def inc(self, amount: float = 1) -> None:
        self._parent._inc(self._labels, amount)

    def observe(self, amount: float) -> None:
        self._parent._observe(self._labels, amount)

    def set(self, value: float) -> None:
        self._parent._set(self._labels, value)


class _Metric:
    def __init__(self, name: str, doc: str, labelnames: Iterable[str] = (), kind: str = "counter") -> None:
        self.name = name
        self.doc = doc
        self.labelnames = tuple(labelnames)
        self.kind = kind
        self.values: Dict[Tuple[str, ...], float] = {}
        self.sums: Dict[Tuple[str, ...], float] = {}

    def labels(self, *args: str, **kwargs: str) -> _MetricChild:
        labels = kwargs or dict(zip(self.labelnames, args))
        return _MetricChild(self, labels)

    def clear(self) -> None:
        self.values.clear()
        self.sums.clear()

    def _inc(self, key: Tuple[str, ...], amount: float) -> None:
        self.values[key] = self.values.get(key, 0.0) + amount

    def _observe(self, key: Tuple[str, ...], amount: float) -> None:
        self.values[key] = self.values.get(key, 0.0) + 1.0
        self.sums[key] = self.sums.get(key, 0.0) + amount

    def _set(self, key: Tuple[str, ...], value: float) -> None:
        self.values[key] = value

    def inc(self, amount: float = 1) -> None:
        self._inc((), amount)

    def observe(self, amount: float) -> None:
        self._observe((), amount)

    def set(self, value: float) -> None:
        self._set((), value)

    def collect(self) -> List[object]:  # pragma: no cover - simple stub
        class _Collected:
            def __init__(self, samples: List[Sample]):
                self.samples = samples

        samples: List[Sample] = []
        for key, val in self.values.items():
            labels = dict(zip(self.labelnames, key))
            if self.kind == "counter":
                samples.append(Sample(f"{self.name}_total", labels, val))
            elif self.kind == "histogram":
                samples.append(Sample(f"{self.name}_count", labels, val))
                samples.append(Sample(f"{self.name}_sum", labels, self.sums.get(key, 0.0)))
            else:  # gauge
                samples.append(Sample(self.name, labels, val))
        return [_Collected(samples)]


class _Registry:
    def __init__(self) -> None:
        self._metrics: List[_Metric] = []

    def register(self, metric: _Metric) -> None:
        if metric not in self._metrics:
            self._metrics.append(metric)

    def unregister(self, metric: _Metric) -> None:
        if metric in self._metrics:
            self._metrics.remove(metric)

    def collect(self) -> Iterable[object]:
        for metric in list(self._metrics):
            yield from metric.collect()


REGISTRY = _Registry()


class Counter(_Metric):
    def __init__(self, name: str, doc: str, labelnames: Iterable[str] = ()) -> None:
        super().__init__(name, doc, labelnames, kind="counter")
        REGISTRY.register(self)


class Histogram(_Metric):
    def __init__(self, name: str, doc: str, labelnames: Iterable[str] = ()) -> None:
        super().__init__(name, doc, labelnames, kind="histogram")
        REGISTRY.register(self)


class Gauge(_Metric):
    def __init__(self, name: str, doc: str, labelnames: Iterable[str] = ()) -> None:
        super().__init__(name, doc, labelnames, kind="gauge")
        REGISTRY.register(self)


CONTENT_TYPE_LATEST = "text/plain"


def generate_latest(registry: _Registry | None = None) -> bytes:  # pragma: no cover - simple stub
    return b""


__all__ = [
    "Counter",
    "Histogram",
    "Gauge",
    "Sample",
    "REGISTRY",
    "generate_latest",
    "CONTENT_TYPE_LATEST",
]
