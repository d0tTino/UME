import nbformat
from nbconvert.preprocessors import ExecutePreprocessor
from pathlib import Path
import pytest

pytestmark = pytest.mark.integration

NOTEBOOKS = [
    Path('examples/langgraph_workflow.ipynb'),
    Path('examples/letta_workflow.ipynb'),
]

@pytest.mark.parametrize('nb_path', NOTEBOOKS)
def test_notebook_runs(nb_path, tmp_path):
    with nb_path.open() as f:
        nb = nbformat.read(f, as_version=4)
    root = Path(__file__).resolve().parents[2]
    setup = nbformat.v4.new_code_cell(
        "import sys, pathlib\n"
        "sys.path.insert(0, str(pathlib.Path('" + str(root / 'src') + "')))")
    stub = nbformat.v4.new_code_cell(
        "import types, sys\n"
        "class _Resp:\n"
        "    def raise_for_status(self):\n"
        "        pass\n"
        "    def json(self):\n"
        "        return {}\n"
        "    def iter_lines(self):\n"
        "        return []\n"
        "class _Client:\n"
        "    def __init__(self, *a, **k):\n"
        "        pass\n"
        "    def post(self, *a, **k):\n"
        "        return _Resp()\n"
        "    def get(self, *a, **k):\n"
        "        return _Resp()\n"
        "sys.modules['httpx'] = types.SimpleNamespace(Client=_Client, HTTPError=Exception)\n"
        "yaml_stub = types.ModuleType('yaml')\n"
        "yaml_stub.safe_load = lambda _ : {}\n"
        "sys.modules.setdefault('yaml', yaml_stub)\n"
        "prom_stub = types.ModuleType('prometheus_client')\n"
        "class _D:\n"
        "    def __init__(self, *a, **k):\n"
        "        self.v=0\n"
        "    def inc(self, amount=1):\n"
        "        self.v+=amount\n"
        "    def labels(self, *a, **k):\n"
        "        return self\n"
        "prom_stub.Counter = _D\n"
        "prom_stub.Histogram = _D\n"
        "prom_stub.Gauge = _D\n"
        "sys.modules.setdefault('prometheus_client', prom_stub)\n"
        "numpy_stub = types.ModuleType('numpy')\n"
        "numpy_stub.asarray = lambda x, dtype=None: list(x)\n"
        "sys.modules.setdefault('numpy', numpy_stub)\n"
        "numpy_typing = types.ModuleType('numpy.typing')\n"
        "numpy_typing.NDArray = list\n"
        "sys.modules.setdefault('numpy.typing', numpy_typing)\n"
    )
    nb.cells.insert(0, stub)
    nb.cells.insert(0, setup)
    ep = ExecutePreprocessor(timeout=600, kernel_name='python3')
    ep.preprocess(nb, {'metadata': {'path': str(root)}})

