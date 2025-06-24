# mypy: ignore-errors
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


class DummySupervisor(Supervisor):
    def plan(self, objective: str):
        return [AgentTask(id="t1", payload=objective)]


class DummyCritic(Critic):
    def score(self, result):
        return 1.0 if result == "ok" else 0.0


def test_execution_cycle() -> None:
    orchestrator = AgentOrchestrator(DummySupervisor(), DummyCritic())
    executed: list[str] = []

    def worker(task: AgentTask) -> str:
        executed.append(task.payload)
        return "ok"

    orchestrator.register_worker("worker1", worker)
    scores = orchestrator.execute_objective("test-task")

    assert executed == ["test-task"]
    assert scores == {"worker1:t1": 1.0}
