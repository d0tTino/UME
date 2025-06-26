import pytest

from ume.dag_executor import DAGExecutor, Task


def test_cycle_detection():
    exec = DAGExecutor()
    exec.add_task(Task(name="a", func=lambda: None, dependencies=["b"]))
    exec.add_task(Task(name="b", func=lambda: None, dependencies=["a"]))
    with pytest.raises(ValueError):
        exec._topological_sort()


def test_unknown_resource():
    exec = DAGExecutor(resources={"cpu": 1})
    exec.add_task(Task(name="a", func=lambda: None, resource="gpu"))
    with pytest.raises(ValueError):
        exec.run()


def test_run_simple_dag():
    calls: list[str] = []

    exec = DAGExecutor(resources={"cpu": 2})
    exec.add_task(Task(name="a", func=lambda: calls.append("a")))
    exec.add_task(Task(name="b", func=lambda: calls.append("b"), dependencies=["a"]))
    exec.add_task(Task(name="c", func=lambda: calls.append("c"), dependencies=["a", "b"]))

    result = exec.run()
    assert result == {"a": None, "b": None, "c": None}
    assert calls == ["a", "b", "c"]


def test_stop_execution():
    exec = DAGExecutor()

    def stopper():
        exec.stop()

    exec.add_task(Task(name="a", func=stopper))
    exec.add_task(Task(name="b", func=lambda: None, dependencies=["a"]))

    result = exec.run()
    assert result == {"a": None}


def test_topological_sort_order() -> None:
    exec = DAGExecutor()
    exec.add_task(Task(name="a", func=lambda: None))
    exec.add_task(Task(name="b", func=lambda: None, dependencies=["a"]))
    exec.add_task(Task(name="c", func=lambda: None, dependencies=["b"]))

    assert exec._topological_sort() == ["a", "b", "c"]


def test_add_task_duplicate() -> None:
    exec = DAGExecutor()
    exec.add_task(Task(name="a", func=lambda: None))
    with pytest.raises(ValueError):
        exec.add_task(Task(name="a", func=lambda: None))
