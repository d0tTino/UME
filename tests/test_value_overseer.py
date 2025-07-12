import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path


def load_modules():
    base = Path(__file__).resolve().parents[1] / "src" / "ume"
    modules = {}
    for name in ["config", "audit", "value_overseer", "agent_orchestrator", "message_bus"]:
        full = f"ume.{name}"
        sys.modules.pop(full, None)
        path = base / f"{name}.py"
        if not path.exists():
            path = base / name / "__init__.py"
        spec = importlib.util.spec_from_file_location(full, path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules[full] = mod
        spec.loader.exec_module(mod)
        modules[name] = mod
    return modules


class DummySupervisor:
    def __init__(self, base):
        self._base = base

    def plan(self, objective: str):
        AgentTask = self._base["agent_orchestrator"].AgentTask
        return [AgentTask(id="t1", payload=objective)]


def setup_env(tmp_path, blocked):
    store = tmp_path / "values.json"
    store.write_text(json.dumps({"blocked": blocked}))
    log = tmp_path / "audit.log"
    os.environ["UME_VALUE_STORE_PATH"] = str(store)
    os.environ["UME_AUDIT_LOG_PATH"] = str(log)
    os.environ["UME_AUDIT_SIGNING_KEY"] = "test-key"
    os.environ["UME_AGENT_ID"] = "tester"
    open(log, "w").close()
    return load_modules()


def test_disallowed_task_blocks_execution(tmp_path):
    mods = setup_env(tmp_path, ["bad"])
    AgentOrchestrator = mods["agent_orchestrator"].AgentOrchestrator
    MessageEnvelope = mods["message_bus"].MessageEnvelope
    get_audit_entries = mods["audit"].get_audit_entries

    orchestrator = AgentOrchestrator(DummySupervisor(mods))
    executed = []

    async def worker(msg: dict) -> dict:
        executed.append(msg["content"])
        return MessageEnvelope(content="ok").to_dict()

    orchestrator.register_worker("w", worker)
    asyncio.run(orchestrator.execute_objective("bad"))

    assert executed == []
    entries = get_audit_entries()
    assert len(entries) == 1
    assert "bad" in str(entries[0]["reason"])


def test_allowed_task_runs(tmp_path):
    mods = setup_env(tmp_path, ["bad"])
    AgentOrchestrator = mods["agent_orchestrator"].AgentOrchestrator
    MessageEnvelope = mods["message_bus"].MessageEnvelope
    get_audit_entries = mods["audit"].get_audit_entries

    orchestrator = AgentOrchestrator(DummySupervisor(mods))
    executed = []

    async def worker(msg: dict) -> dict:
        executed.append(msg["content"])
        return MessageEnvelope(content="ok").to_dict()

    orchestrator.register_worker("w", worker)
    asyncio.run(orchestrator.execute_objective("good"))

    assert executed == ["good"]
    assert get_audit_entries() == []
