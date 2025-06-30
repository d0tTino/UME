from __future__ import annotations

from dataclasses import dataclass
import asyncio
from collections import defaultdict
from typing import Callable, Any, Dict, List, Awaitable

from .audit import log_audit_entry
from .config import settings

from .persistent_graph import PersistentGraph
from .message_bus import MessageEnvelope
from .value_overseer import ValueOverseer


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


class Overseer:
    """Monitor worker outputs for hallucinations."""

    def is_allowed(self, task: AgentTask) -> bool:  # pragma: no cover - default passthrough
        """Return ``True`` if the task is permitted."""
        return True

    def hallucination_check(
        self,
        message: MessageEnvelope,
        *,
        task: AgentTask | None = None,
        agent_id: str | None = None,
    ) -> MessageEnvelope:  # pragma: no cover - default passthrough
        return message


class ReflectionAgent:
    """Optional agent that can post-process worker output."""

    def review(self, message: MessageEnvelope) -> MessageEnvelope:  # pragma: no cover - default passthrough
        return message


class AgentOrchestrator:
    """Coordinate workers executing tasks produced by a :class:`Supervisor`."""

    def __init__(
        self,
        supervisor: Supervisor | None = None,
        critic: Critic | None = None,
        reflection: ReflectionAgent | None = None,
        overseer: ValueOverseer | None = None,
        max_retries: int | None = None,

    ) -> None:
        self.supervisor = supervisor or Supervisor()
        self.critic = critic or Critic()
        self.reflection = reflection or ReflectionAgent()
        self.overseer = overseer or ValueOverseer()
        self.max_retries = max_retries or 0

        self._workers: Dict[str, Callable[[Dict[str, Any]], Awaitable[Any]]] = {}

    def register_worker(
        self, agent_id: str, handler: Callable[[Dict[str, Any]], Awaitable[Any]]
    ) -> None:
        """Register a worker that can execute tasks."""
        self._workers[agent_id] = handler

    async def execute_objective(self, objective: str) -> Dict[str, float]:
        """Plan tasks for the objective and execute them across workers."""
        tasks = self.supervisor.plan(objective)
        allowed_tasks: list[AgentTask] = []
        for task in tasks:
            if self.overseer.is_allowed(task):
                allowed_tasks.append(task)
            else:
                user_id = settings.UME_AGENT_ID
                log_audit_entry(user_id, f"blocked_task {task.payload}")
        tasks = allowed_tasks

        async def _run(
            worker: Callable[[Dict[str, Any]], Awaitable[Any]],
            agent_id: str,
            task: AgentTask,
        ) -> tuple[str, float]:
            envelope = MessageEnvelope(content=task.payload, id=task.id)
            attempts = 0
            while True:
                result = await worker(envelope.to_dict())
                if isinstance(result, MessageEnvelope):
                    resp = result
                elif isinstance(result, dict):
                    resp = MessageEnvelope.from_dict(result)
                else:
                    resp = MessageEnvelope(content=str(result))
                checked = self.overseer.hallucination_check(
                    resp, task=task, agent_id=agent_id
                )
                if checked.meta and checked.meta.get("hallucination"):
                    attempts += 1
                    if attempts <= self.max_retries:
                        continue
                reviewed = self.reflection.review(checked)
                return agent_id, self.critic.score(
                    reviewed.content, task=task, agent_id=agent_id
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
