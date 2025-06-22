from ume.dag_service import DAGService
from ume.dag_executor import Task


def test_dag_service_start_stop() -> None:
    ran = []

    def work() -> None:
        ran.append(1)

    service = DAGService([Task(name="t", func=work)])
    service.start()
    service.stop()
    assert ran == [1]


def test_dag_service_stop_cancels_pending_tasks() -> None:
    import time
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
