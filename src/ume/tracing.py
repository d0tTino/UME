from __future__ import annotations

from typing import Any, Dict, Optional, List, ContextManager

from contextlib import nullcontext

try:  # pragma: no cover - optional dependency
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
except Exception:  # pragma: no cover - package may be missing
    trace = None

from .config import settings
from .graph_adapter import IGraphAdapter

if trace is None:
    class _DummyTracer:
        def start_as_current_span(self, *_args: Any, **_kwargs: Any) -> ContextManager[Any]:
            return nullcontext()

    tracer = _DummyTracer()
else:
    tracer = trace.get_tracer("ume")
_enabled = False


def configure_tracing(endpoint: str | None = None) -> None:
    """Configure OpenTelemetry tracing if an endpoint is provided."""
    global _enabled
    if trace is None:
        return
    endpoint = endpoint or settings.UME_OTLP_ENDPOINT
    if not endpoint:
        return
    provider = TracerProvider(resource=Resource.create({"service.name": "ume"}))
    exporter = OTLPSpanExporter(endpoint=endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _enabled = True


def is_tracing_enabled() -> bool:
    """Return ``True`` if tracing has been configured."""
    return _enabled


class TracingGraphAdapter(IGraphAdapter):
    """Wrap another adapter and emit spans for graph operations."""

    def __init__(self, adapter: IGraphAdapter, tracer: trace.Tracer = tracer) -> None:
        self._adapter = adapter
        self._tracer = tracer

    # ---- Node methods -------------------------------------------------
    def add_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        with self._tracer.start_as_current_span("graph.add_node"):
            self._adapter.add_node(node_id, attributes)

    def update_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        with self._tracer.start_as_current_span("graph.update_node"):
            self._adapter.update_node(node_id, attributes)

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        with self._tracer.start_as_current_span("graph.get_node"):
            return self._adapter.get_node(node_id)

    def node_exists(self, node_id: str) -> bool:
        with self._tracer.start_as_current_span("graph.node_exists"):
            return self._adapter.node_exists(node_id)

    def dump(self) -> Dict[str, Any]:
        with self._tracer.start_as_current_span("graph.dump"):
            return self._adapter.dump()

    def clear(self) -> None:
        with self._tracer.start_as_current_span("graph.clear"):
            self._adapter.clear()

    def get_all_node_ids(self) -> List[str]:
        with self._tracer.start_as_current_span("graph.get_all_node_ids"):
            return self._adapter.get_all_node_ids()

    def find_connected_nodes(self, node_id: str, edge_label: Optional[str] = None) -> List[str]:
        with self._tracer.start_as_current_span("graph.find_connected_nodes"):
            return self._adapter.find_connected_nodes(node_id, edge_label)

    def add_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        with self._tracer.start_as_current_span("graph.add_edge"):
            self._adapter.add_edge(source_node_id, target_node_id, label)

    def get_all_edges(self) -> List[tuple[str, str, str]]:
        with self._tracer.start_as_current_span("graph.get_all_edges"):
            return self._adapter.get_all_edges()

    def delete_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        with self._tracer.start_as_current_span("graph.delete_edge"):
            self._adapter.delete_edge(source_node_id, target_node_id, label)

    def redact_node(self, node_id: str) -> None:
        with self._tracer.start_as_current_span("graph.redact_node"):
            self._adapter.redact_node(node_id)

    def redact_edge(self, source_node_id: str, target_node_id: str, label: str) -> None:
        with self._tracer.start_as_current_span("graph.redact_edge"):
            self._adapter.redact_edge(source_node_id, target_node_id, label)

    def close(self) -> None:
        with self._tracer.start_as_current_span("graph.close"):
            self._adapter.close()

    # ---- Traversal and pathfinding ---------------------------------
    def shortest_path(self, source_id: str, target_id: str) -> List[str]:
        with self._tracer.start_as_current_span("graph.shortest_path"):
            return self._adapter.shortest_path(source_id, target_id)

    def traverse(self, start_node_id: str, depth: int, edge_label: Optional[str] = None) -> List[str]:
        with self._tracer.start_as_current_span("graph.traverse"):
            return self._adapter.traverse(start_node_id, depth, edge_label)

    def extract_subgraph(
        self,
        start_node_id: str,
        depth: int,
        edge_label: Optional[str] = None,
        since_timestamp: Optional[int] = None,
    ) -> Dict[str, Any]:
        with self._tracer.start_as_current_span("graph.extract_subgraph"):
            return self._adapter.extract_subgraph(start_node_id, depth, edge_label, since_timestamp)

    def constrained_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int | None = None,
        edge_label: str | None = None,
        since_timestamp: int | None = None,
    ) -> List[str]:
        with self._tracer.start_as_current_span("graph.constrained_path"):
            return self._adapter.constrained_path(
                source_id, target_id, max_depth, edge_label, since_timestamp
            )
