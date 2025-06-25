from __future__ import annotations

from dataclasses import dataclass
import asyncio
from collections import defaultdict
from typing import Callable, Any, Dict, List, Awaitable

from .persistent_graph import PersistentGraph


@dataclass
class AgentTask:
    """Simple representation of a unit of work."""

    id: str
    payload: str


class Supervisor:
    """Plan objectives into executable tasks."""

    def plan(self, objective: str) -> List[AgentTask]:
        """Return a list of tasks to accomplish the given objective."""
        parts = [p.strip() for p in objective.split(";") if p.strip()]
        if not parts:
            parts = [objective]
        return [
            AgentTask(id=f"task-{i+1}", payload=part)
            for i, part in enumerate(parts)
        ]


class Critic:
    """Evaluate task outcomes and persist scores."""

    def __init__(self, graph: PersistentGraph | None = None) -> None:
        self.graph = graph or PersistentGraph(":memory:")

    def score(
        self,
        result: Any,
        *,
        task: AgentTask | None = None,
        agent_id: str | None = None,
    ) -> float:
        """Return a numeric score for ``result`` and persist it."""
        score = 1.0 if result is not None else 0.0
        self.graph.add_score(task.id if task else None, agent_id, score)
        return score


class AgentOrchestrator:
    """Coordinate workers executing tasks produced by a :class:`Supervisor`."""

    def __init__(self, supervisor: Supervisor | None = None, critic: Critic | None = None) -> None:
        self.supervisor = supervisor or Supervisor()
        self.critic = critic or Critic()
        self._workers: Dict[str, Callable[[AgentTask], Awaitable[Any]]] = {}

    def register_worker(
        self, agent_id: str, handler: Callable[[AgentTask], Awaitable[Any]]
    ) -> None:
        """Register a worker that can execute tasks."""
        self._workers[agent_id] = handler

    async def execute_objective(self, objective: str) -> Dict[str, float]:
        """Plan tasks for the objective and execute them across workers."""
        tasks = self.supervisor.plan(objective)

        async def _run(
            worker: Callable[[AgentTask], Awaitable[Any]],
            agent_id: str,
            task: AgentTask,
        ) -> tuple[str, float]:
            result = await worker(task)
            return agent_id, self.critic.score(
                result, task=task, agent_id=agent_id
            )

        coros = [
            _run(worker, agent_id, task)
            for task in tasks
            for agent_id, worker in self._workers.items()
        ]

        scores_map: Dict[str, List[float]] = defaultdict(list)
        for agent_id, score in await asyncio.gather(*coros):
            scores_map[agent_id].append(score)

        return {
            agent_id: sum(values) / len(values)
            for agent_id, values in scores_map.items()
        }
