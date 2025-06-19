from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Any, Dict, List, Optional
import threading


@dataclass
class Task:
    """A unit of work in the DAG."""

    name: str
    func: Callable[[], Any]
    dependencies: List[str] = field(default_factory=list)
    resource: str = "cpu"


class DAGExecutor:
    """Execute tasks respecting dependencies and resource limits."""

    def __init__(self, resources: Optional[Dict[str, int]] = None) -> None:
        self.tasks: Dict[str, Task] = {}
        self.resources = resources or {"cpu": 1, "gpu": 1}
        for name, count in self.resources.items():
            if count <= 0:
                raise ValueError(f"Resource count for {name} must be positive")
        self.locks: Dict[str, threading.Semaphore] = {
            name: threading.Semaphore(count) for name, count in self.resources.items()
        }

    def add_task(self, task: Task) -> None:
        if task.name in self.tasks:
            raise ValueError(f"Task {task.name} already exists")
        self.tasks[task.name] = task

    def _topological_sort(self) -> List[str]:
        remaining: Dict[str, set[str]] = {
            name: set(task.dependencies) for name, task in self.tasks.items()
        }
        order: List[str] = []
        while remaining:
            ready = [name for name, deps in remaining.items() if not deps]
            if not ready:
                raise ValueError("Cycle detected in task graph")
            for name in ready:
                order.append(name)
                del remaining[name]
            for deps in remaining.values():
                for finished in ready:
                    deps.discard(finished)
        return order

    def run(self) -> Dict[str, Any]:
        remaining: Dict[str, set[str]] = {
            name: set(task.dependencies) for name, task in self.tasks.items()
        }
        results: Dict[str, Any] = {}
        while remaining:
            ready = [name for name, deps in remaining.items() if not deps]
            if not ready:
                raise ValueError("Cycle detected in task graph")
            threads = []
            exceptions: list[Exception] = []
            for name in ready:
                task = self.tasks[name]
                try:
                    sem = self.locks[task.resource]
                except KeyError as exc:
                    raise ValueError(f"Unknown resource {task.resource}") from exc

                def worker(
                    n: str = name,
                    t: Task = task,
                    sem_lock: threading.Semaphore = sem,
                ) -> None:
                    try:
                        with sem_lock:
                            results[n] = t.func()
                    except Exception as exc:
                        exceptions.append(exc)

                thread = threading.Thread(target=worker)
                thread.start()
                threads.append(thread)
            for thread in threads:
                thread.join()
            if exceptions:
                raise exceptions[0]
            for name in ready:
                del remaining[name]
            for deps in remaining.values():
                for finished in ready:
                    deps.discard(finished)
        return results
