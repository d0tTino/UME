import sys
import types
import time
import threading
import pytest
from ume import DAGExecutor, Task  # noqa: E402


@pytest.fixture(autouse=True)  # type: ignore[misc]
def fast_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch ``time.sleep`` to avoid delays."""
    monkeypatch.setattr(time, "sleep", lambda _: None)

sys.modules.setdefault("faiss", types.ModuleType("faiss"))


def test_dag_execution_order() -> None:
    order: list[str] = []

    def a(_e: threading.Event) -> None:
        order.append("a")

    def b(_e: threading.Event) -> None:
        order.append("b")

    def c(_e: threading.Event) -> None:
        order.append("c")

    exec = DAGExecutor()
    exec.add_task(Task(name="a", func=a))
    exec.add_task(Task(name="b", func=b, dependencies=["a"]))
    exec.add_task(Task(name="c", func=c, dependencies=["b"]))
    exec.run()
    assert order == ["a", "b", "c"]


def test_resource_scheduling_sequential_gpu() -> None:
    exec = DAGExecutor(resources={"cpu": 1, "gpu": 1})
    events: list[tuple[str, float]] = []

    def make(name: str, delay: float, resource: str) -> Task:
        def _f(stop_event: threading.Event) -> None:
            events.append((name + "_start", time.perf_counter()))
            time.sleep(delay)
            events.append((name + "_end", time.perf_counter()))
        return Task(name=name, func=_f, resource=resource)

    exec.add_task(make("gpu1", 0.1, "gpu"))
    exec.add_task(make("gpu2", 0.1, "gpu"))
    exec.run()

    starts = [t for t in events if t[0].endswith("_start")]
    assert len(starts) == 2
    diff = starts[1][1] - starts[0][1]
    assert diff > 0


def test_dag_executor_zero_resource_raises() -> None:
    with pytest.raises(ValueError):
        DAGExecutor(resources={"cpu": 1, "gpu": 0})


def test_public_imports() -> None:
    from ume import DAGExecutor as PublicDAGExecutor, Task as PublicTask

    assert PublicDAGExecutor is DAGExecutor
    assert PublicTask is Task


def test_run_raises_on_task_error() -> None:
    exec = DAGExecutor()

    exec.add_task(Task(name="ok", func=lambda _e: None))

    def boom(_e: threading.Event) -> None:
        raise RuntimeError("boom")

    exec.add_task(Task(name="bad", func=boom))

    with pytest.raises(RuntimeError):
        exec.run()
