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
