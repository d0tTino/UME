import threading
import time
import pytest

from ume.resource_scheduler import ResourceScheduler, ScheduledTask

def test_scheduler_limits_concurrency() -> None:
    sched = ResourceScheduler(resources={"gpu": 1})
    events: list[tuple[str, float]] = []

    def make(name: str) -> ScheduledTask:
        def _task() -> None:
            events.append((f"{name}_start", time.perf_counter()))
            time.sleep(0.1)
            events.append((f"{name}_end", time.perf_counter()))
        return ScheduledTask(func=_task, resource="gpu")

    sched.run([make("a"), make("b")])
    starts = [t for t in events if t[0].endswith("_start")]
    assert len(starts) == 2
    assert starts[1][1] - starts[0][1] >= 0.09


def test_scheduler_unknown_resource_raises() -> None:
    sched = ResourceScheduler(resources={"cpu": 1})
    with pytest.raises(ValueError):
        sched.run([ScheduledTask(func=lambda: None, resource="gpu")])


def test_scheduler_stop() -> None:
    sched = ResourceScheduler(resources={"cpu": 1})
    ran: list[str] = []
    started = threading.Event()

    def slow() -> None:
        started.set()
        time.sleep(0.2)
        ran.append("slow")

    def fast() -> None:
        ran.append("fast")

    tasks = [ScheduledTask(func=slow), ScheduledTask(func=fast)]
    t = threading.Thread(target=sched.run, args=(tasks,))
    t.start()
    started.wait(0.05)
    sched.stop()
    t.join()
    assert ran == ["slow"]
