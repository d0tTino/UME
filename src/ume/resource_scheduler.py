from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Iterable, Any


@dataclass
class ScheduledTask:
    """Simple task with an associated resource."""

    func: Callable[[], Any]
    resource: str = "cpu"


class ResourceScheduler:
    """Run tasks while enforcing per-resource concurrency limits."""

    def __init__(self, resources: dict[str, int] | None = None) -> None:
        self.resources = resources or {"cpu": 1, "gpu": 1}
        for name, count in self.resources.items():
            if count <= 0:
                raise ValueError(f"Resource count for {name} must be positive")
        self.locks = {
            name: threading.Semaphore(count) for name, count in self.resources.items()
        }
        self._stop_event = threading.Event()

    def stop(self) -> None:  # pragma: no cover - simple setter
        """Request the scheduler to stop starting new tasks."""

        self._stop_event.set()

    def reset_stop_flag(self) -> None:  # pragma: no cover - simple setter
        """Clear the stop flag so the scheduler can be reused."""

        self._stop_event.clear()

    def run(self, tasks: Iterable[ScheduledTask]) -> None:
        threads: list[threading.Thread] = []
        for task in tasks:
            if self._stop_event.is_set():
                break
            try:
                sem = self.locks[task.resource]
            except KeyError as exc:
                raise ValueError(f"Unknown resource {task.resource}") from exc

            def worker(
                t: ScheduledTask = task,
                s: threading.Semaphore = sem,
            ) -> None:
                with s:
                    t.func()

            thread = threading.Thread(target=worker)
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()
