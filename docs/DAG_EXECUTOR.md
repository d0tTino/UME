# DAGExecutor Guide

The `DAGExecutor` coordinates small units of work that depend on each other. Each
operation is represented by a `Task` which specifies a unique name, the
callable to run, optional dependencies, and the resource it consumes.

```python
from dataclasses import dataclass, field
from typing import Callable, Any, List
import threading

@dataclass
class Task:
    name: str
    func: Callable[[threading.Event], Any]
    dependencies: List[str] = field(default_factory=list)
    resource: str = "cpu"
```

Tasks are added via `add_task()` and referenced by name when declaring
`dependencies`. The executor ensures that tasks run only after all of their
dependencies have finished.

## Resource limits

When creating a `DAGExecutor` you may provide a mapping of resource names to
concurrency limits:

```python
exec = DAGExecutor(resources={"cpu": 2, "gpu": 1})
```

Each task reserves a slot for its `resource` while executing. The executor uses
semaphores so no more than the configured number of tasks can use a resource
simultaneously. Counts must be positive and unknown resources raise a
`ValueError`.

## Minimal example

```python
from ume import DAGExecutor, Task

results = []

def a():
    results.append("a")

def b():
    results.append("b")

exec = DAGExecutor(resources={"cpu": 1, "gpu": 1})
exec.add_task(Task(name="a", func=a))
exec.add_task(Task(name="b", func=b, dependencies=["a"]))
exec.run()
print(results)  # ["a", "b"]
```

This mirrors the behavior tested in `tests/test_dag_executor.py` and shows how to
run tasks in order while respecting resource limits.
