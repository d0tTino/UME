# mypy: ignore-errors
import asyncio
import importlib.util
from pathlib import Path
import sys

base = Path(__file__).resolve().parents[1] / "src" / "ume"

# Load MessageEnvelope without importing the full package to avoid optional
# dependencies required by ``ume.__init__`` during test collection.
envelope_path = base / "message_bus.py"
envelope_spec = importlib.util.spec_from_file_location(
    "ume.message_bus", envelope_path
)
assert envelope_spec and envelope_spec.loader
envelope_module = importlib.util.module_from_spec(envelope_spec)
sys.modules[envelope_spec.name] = envelope_module
envelope_spec.loader.exec_module(envelope_module)
MessageEnvelope = envelope_module.MessageEnvelope  # type: ignore[attr-defined]

module_path = base / "agent_orchestrator.py"
spec = importlib.util.spec_from_file_location("ume.agent_orchestrator", module_path)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
AgentOrchestrator = module.AgentOrchestrator  # type: ignore[attr-defined]
Supervisor = module.Supervisor  # type: ignore[attr-defined]
Critic = module.Critic  # type: ignore[attr-defined]
AgentTask = module.AgentTask  # type: ignore[attr-defined]
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

    async def worker(msg: dict) -> dict:
        executed.append(msg["content"])
        return MessageEnvelope(content="ok").to_dict()

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

    async def worker(msg: dict) -> dict:
        return MessageEnvelope(content="done").to_dict()

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

    async def worker(msg: dict) -> dict:
        return MessageEnvelope(content="123").to_dict()

    orchestrator.register_worker("worker", worker)
    scores = asyncio.run(orchestrator.execute_objective("t"))

    assert scores == {"worker": 0.0}


class DummyOverseer(module.Overseer):
    def __init__(self):
        self.seen: MessageEnvelope | None = None

    def hallucination_check(self, message: MessageEnvelope, *, task=None, agent_id=None):
        self.seen = message
        if message.content == "bad":
            return MessageEnvelope(content="")
        return message


def test_overseer_intervenes() -> None:
    orchestrator = AgentOrchestrator(DummySupervisor(), DummyCritic(), FilteringReflection(), DummyOverseer())

    async def worker(msg: dict) -> dict:
        return MessageEnvelope(content="bad").to_dict()

    orchestrator.register_worker("worker", worker)
    scores = asyncio.run(orchestrator.execute_objective("t"))

    assert scores == {"worker": 0.0}


def test_envelope_wrapping() -> None:
    overseer = DummyOverseer()
    orchestrator = AgentOrchestrator(DummySupervisor(), DummyCritic(), None, overseer)

    async def worker(msg: dict) -> dict:
        return MessageEnvelope(content="ok").to_dict()

    orchestrator.register_worker("w", worker)
    scores = asyncio.run(orchestrator.execute_objective("t"))

    assert scores == {"w": 1.0}
    assert overseer.seen is not None
    assert overseer.seen.jsonrpc == "2.0"


class FlaggingOverseer(module.Overseer):
    def hallucination_check(self, message: MessageEnvelope, *, task=None, agent_id=None):
        if message.content == "bad":
            meta = message.meta or {}
            meta["hallucination"] = True
            message.meta = meta
        return message


class FlakyWorker:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, msg: dict) -> dict:
        self.calls += 1
        if self.calls == 1:
            return MessageEnvelope(content="bad").to_dict()
        return MessageEnvelope(content="ok").to_dict()


def test_overseer_retry_reduces_hallucination() -> None:
    worker = FlakyWorker()
    orchestrator = AgentOrchestrator(
        DummySupervisor(),
        DummyCritic(),
        FilteringReflection(),
        FlaggingOverseer(),
        max_retries=1,
    )
    orchestrator.register_worker("worker", worker)
    scores = asyncio.run(orchestrator.execute_objective("t"))
    assert worker.calls == 2
    assert scores == {"worker": 1.0}


def test_overseer_no_retry_hallucination() -> None:
    worker = FlakyWorker()
    orchestrator = AgentOrchestrator(
        DummySupervisor(),
        DummyCritic(),
        FilteringReflection(),
        FlaggingOverseer(),
        max_retries=0,
    )
    orchestrator.register_worker("worker", worker)
    scores = asyncio.run(orchestrator.execute_objective("t"))
    assert worker.calls == 1
    assert scores == {"worker": 0.0}

