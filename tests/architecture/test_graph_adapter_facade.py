import ast
from pathlib import Path

from ume import graph_adapter as facade
from ume.kernel import graph_adapter as kernel


ROOT = Path(__file__).resolve().parents[2]


def _class_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}


def test_graph_adapter_contract_has_single_source_file() -> None:
    kernel_path = ROOT / "src/ume/kernel/graph_adapter.py"
    facade_path = ROOT / "src/ume/graph_adapter.py"

    kernel_classes = _class_names(kernel_path)
    facade_classes = _class_names(facade_path)

    assert {"IGraphAdapter", "AsyncAdapterMixin"}.issubset(kernel_classes)
    assert "IGraphAdapter" not in facade_classes
    assert "AsyncAdapterMixin" not in facade_classes


def test_graph_adapter_facade_exports_aliases() -> None:
    assert facade.IGraphAdapter is kernel.IGraphAdapter
    assert facade.AsyncAdapterMixin is kernel.AsyncAdapterMixin
