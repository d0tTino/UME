from __future__ import annotations

import threading
from typing import Iterable

from ume.dag_executor import DAGExecutor, Task


class DAGService:
    """Background service for executing tasks with the DAGExecutor."""

    def __init__(self, tasks: Iterable[Task], resources: dict[str, int] | None = None) -> None:
        self._executor = DAGExecutor(resources=resources)
        for t in tasks:
            self._executor.add_task(t)
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread:
            return
        self._thread = threading.Thread(target=self._executor.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._thread:
            return
        # DAGExecutor lacks a stop mechanism; tasks should exit on their own.
        self._thread.join()
        self._thread = None
