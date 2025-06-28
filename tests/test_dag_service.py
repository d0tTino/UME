# ruff: noqa: E402
import sys
import types
from pathlib import Path

# Avoid executing ume/__init__.py which imports optional dependencies.
pkg_root = Path(__file__).resolve().parents[1] / "src" / "ume"
if "ume" not in sys.modules:
    stub = types.ModuleType("ume")
    stub.__path__ = [str(pkg_root)]
    sys.modules["ume"] = stub

from ume.dag_service import DAGService
from ume.dag_executor import Task
import pytest
import time


@pytest.fixture(autouse=True)  # type: ignore[misc]
def fast_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    orig_sleep = time.sleep
    monkeypatch.setattr(time, "sleep", lambda t: orig_sleep(min(t, 0.001)))


def test_dag_service_start_stop() -> None:
    ran = []

    def work() -> None:
        ran.append(1)

    service = DAGService([Task(name="t", func=work)])
    service.start()
    service.stop()
    assert ran == [1]


def test_dag_service_stop_cancels_pending_tasks() -> None:
    import threading

    ran: list[str] = []
    started = threading.Event()

    def slow() -> None:
        started.set()
        time.sleep(0.2)
        ran.append("slow")

    def should_not_run() -> None:
        ran.append("fast")

    service = DAGService(
        [
            Task(name="slow", func=slow),
            Task(name="fast", func=should_not_run, dependencies=["slow"]),
        ]
    )
    service.start()
    started.wait(0.1)
    service.stop()
    assert ran == ["slow"]


def test_dag_service_start_idempotent() -> None:
    service = DAGService([Task(name="t", func=lambda: None)])
    service.start()
    first = service._thread
    service.start()
    second = service._thread
    service.stop()
    assert first is second


def test_dag_service_stop_without_start() -> None:
    service = DAGService([])
    service.stop()


def test_dag_service_task_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail() -> None:
        raise RuntimeError("boom")

    service = DAGService([Task(name="t", func=fail)])
    service.start()
    assert service._thread is not None
    service._thread.join()
    assert not service._thread.is_alive()
    service.stop()
