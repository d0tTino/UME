import importlib.util
import sys
import time

DAG_SPEC = importlib.util.spec_from_file_location(
    "ume.dag_executor", "src/ume/dag_executor.py"
)
assert DAG_SPEC is not None and DAG_SPEC.loader is not None
dag_executor = importlib.util.module_from_spec(DAG_SPEC)
sys.modules["ume.dag_executor"] = dag_executor
DAG_SPEC.loader.exec_module(dag_executor)
DAGExecutor = dag_executor.DAGExecutor
Task = dag_executor.Task


def test_dag_execution_order():
    order: list[str] = []

    def a():
        order.append("a")

    def b():
        order.append("b")

    def c():
        order.append("c")

    exec = DAGExecutor()
    exec.add_task(Task(name="a", func=a))
    exec.add_task(Task(name="b", func=b, dependencies=["a"]))
    exec.add_task(Task(name="c", func=c, dependencies=["b"]))
    exec.run()
    assert order == ["a", "b", "c"]


def test_resource_scheduling_sequential_gpu():
    exec = DAGExecutor(resources={"cpu": 1, "gpu": 1})
    events: list[tuple[str, float]] = []

    def make(name: str, delay: float, resource: str):
        def _f():
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
    assert diff >= 0.09
