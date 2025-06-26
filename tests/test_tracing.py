from unittest.mock import MagicMock
from typing import Any, Dict, List, Tuple

import importlib.util
import importlib
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "src" / "ume"

tracing_spec = importlib.util.spec_from_file_location("ume.tracing", root / "tracing.py")
assert tracing_spec and tracing_spec.loader
tracing = importlib.util.module_from_spec(tracing_spec)
sys.modules[tracing_spec.name] = tracing
tracing_spec.loader.exec_module(tracing)
TracingGraphAdapter = tracing.TracingGraphAdapter


class DummyGraph:
    def __init__(self) -> None:
        self.called_with: List[Tuple[str, Dict[str, Any]]] = []

    def add_node(self, node_id: str, attributes: Dict[str, Any]) -> None:
        self.called_with.append((node_id, attributes))


def test_tracing_adapter_creates_span() -> None:
    base = DummyGraph()
    tracer = MagicMock()
    cm = MagicMock()
    tracer.start_as_current_span.return_value = cm

    adapter = TracingGraphAdapter(base, tracer)
    adapter.add_node("n1", {})

    tracer.start_as_current_span.assert_called_with("graph.add_node")
    cm.__enter__.assert_called()
