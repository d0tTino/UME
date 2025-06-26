# mypy: ignore-errors
import asyncio
import importlib.util
from pathlib import Path
import sys

module_path = Path(__file__).resolve().parents[1] / "src" / "ume" / "agent_orchestrator.py"
spec = importlib.util.spec_from_file_location("ume.agent_orchestrator", module_path)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
AgentOrchestrator = module.AgentOrchestrator  # type: ignore[attr-defined]
Supervisor = module.Supervisor  # type: ignore[attr-defined]
Critic = module.Critic  # type: ignore[attr-defined]
AgentTask = module.AgentTask  # type: ignore[attr-defined]
MessageEnvelope = module.MessageEnvelope  # type: ignore[attr-defined]
ReflectionAgent = module.ReflectionAgent  # type: ignore[attr-defined]


class DummySupervisor(Supervisor):
    def plan(self, objective: str):
        return [AgentTask(id="t1", payload=objective)]


class DummyCritic(Critic):
    def score(self, result, *, task=None, agent_id=None):  # type: ignore[override]
        return 1.0 if result == "ok" else 0.0


class FilteringReflection(ReflectionAgent):
    def review(self, message: MessageEnvelope) -> MessageEnvelope:
        if message.content.isdigit():
            return MessageEnvelope(content="")
        return message


def test_execution_cycle() -> None:
    orchestrator = AgentOrchestrator(DummySupervisor(), DummyCritic())
    executed: list[str] = []

    async def worker(task: AgentTask) -> str:
        executed.append(task.payload)
        return "ok"

    orchestrator.register_worker("worker1", worker)
    scores = asyncio.run(orchestrator.execute_objective("test-task"))

    assert executed == ["test-task"]
    assert scores == {"worker1": 1.0}


def test_supervisor_decomposes_objective() -> None:
    supervisor = Supervisor()
    tasks = supervisor.plan("step1;step2;step3")
    assert [t.payload for t in tasks] == ["step1", "step2", "step3"]


def test_scoring_persists_across_workers() -> None:
    graph = module.PersistentGraph(":memory:")  # type: ignore[attr-defined]
    critic = Critic(graph)
    orchestrator = AgentOrchestrator(Supervisor(), critic)

    async def worker(task: AgentTask) -> str:
        return "done"

    orchestrator.register_worker("a", worker)
    orchestrator.register_worker("b", worker)
    scores = asyncio.run(orchestrator.execute_objective("one;two"))
    assert scores == {"a": 1.0, "b": 1.0}
    stored = graph.get_scores()
    assert len(stored) == 4
    agents = {agent_id for _, agent_id, _ in stored}
    tasks = {task_id for task_id, _, _ in stored}
    assert agents == {"a", "b"}
    assert tasks == {"task-1", "task-2"}


def test_reflection_filters_hallucinations() -> None:
    orchestrator = AgentOrchestrator(DummySupervisor(), DummyCritic(), FilteringReflection())

    async def worker(task: AgentTask) -> MessageEnvelope:
        return MessageEnvelope(content="123")

    orchestrator.register_worker("worker", worker)
    scores = asyncio.run(orchestrator.execute_objective("t"))

    assert scores == {"worker": 0.0}

