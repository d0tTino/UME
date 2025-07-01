import threading
import time
import pytest
from ume.resource_scheduler import ResourceScheduler, ScheduledTask


@pytest.fixture(autouse=True)  # type: ignore[misc]
def fast_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch ``time.sleep`` to avoid delays in tests."""
    orig_sleep = time.sleep
    monkeypatch.setattr(time, "sleep", lambda t: orig_sleep(min(t, 0.001)))

def test_scheduler_limits_concurrency() -> None:
    sched = ResourceScheduler(resources={"gpu": 1})
    events: list[tuple[str, float]] = []

    def make(name: str) -> ScheduledTask:
        def _task(stop_event: threading.Event) -> None:
            events.append((f"{name}_start", time.perf_counter()))
            time.sleep(0.1)
            events.append((f"{name}_end", time.perf_counter()))
        return ScheduledTask(func=_task, resource="gpu")

    sched.run([make("a"), make("b")])
    starts = [t for t in events if t[0].endswith("_start")]
    assert len(starts) == 2
    assert starts[1][1] - starts[0][1] > 0


def test_scheduler_unknown_resource_raises() -> None:
    sched = ResourceScheduler(resources={"cpu": 1})
    with pytest.raises(ValueError):
        sched.run([ScheduledTask(func=lambda _e: None, resource="gpu")])


def test_scheduler_stop() -> None:
    sched = ResourceScheduler(resources={"cpu": 1})
    ran: list[str] = []
    started = threading.Event()

    def slow(stop_event: threading.Event) -> None:
        started.set()
        for _ in range(20):
            if stop_event.is_set():
                return
            time.sleep(0.01)
        ran.append("slow")

    def fast(_stop_event: threading.Event) -> None:
        ran.append("fast")

    tasks = [ScheduledTask(func=slow), ScheduledTask(func=fast)]
    t = threading.Thread(target=sched.run, args=(tasks,))
    t.start()
    started.wait(0.05)
    sched.stop()
    t.join()
    assert ran == []
