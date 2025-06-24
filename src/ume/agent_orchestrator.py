from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any, Dict, List


@dataclass
class AgentTask:
    """Simple representation of a unit of work."""

    id: str
    payload: str


class Supervisor:
    """Plan objectives into executable tasks."""

    def plan(self, objective: str) -> List[AgentTask]:
        """Return a list of tasks to accomplish the given objective."""
        return [AgentTask(id="task-1", payload=objective)]


class Critic:
    """Evaluate task outcomes."""

    def score(self, result: Any) -> float:
        """Return a numeric score for the given result."""
        return 1.0 if result is not None else 0.0


class AgentOrchestrator:
    """Coordinate workers executing tasks produced by a :class:`Supervisor`."""

    def __init__(self, supervisor: Supervisor | None = None, critic: Critic | None = None) -> None:
        self.supervisor = supervisor or Supervisor()
        self.critic = critic or Critic()
        self._workers: Dict[str, Callable[[AgentTask], Any]] = {}

    def register_worker(self, agent_id: str, handler: Callable[[AgentTask], Any]) -> None:
        """Register a worker that can execute tasks."""
        self._workers[agent_id] = handler

    def execute_objective(self, objective: str) -> Dict[str, float]:
        """Plan tasks for the objective and execute them across workers."""
        scores: Dict[str, float] = {}
        tasks = self.supervisor.plan(objective)
        for task in tasks:
            for agent_id, worker in self._workers.items():
                result = worker(task)
                key = f"{agent_id}:{task.id}"
                scores[key] = self.critic.score(result)
        return scores
