import os
import pytest

from ume.event_ledger import EventLedger
from ume.postgres_graph import PostgresGraph
from ume.event import parse_event
from ume.processing import apply_event_to_graph


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("UME_DOCKER_TESTS"), reason="Docker tests disabled")
def test_postgres_replay_from_timestamp(tmp_path, postgres_service):
    ledger = EventLedger(str(tmp_path / "ledger.db"))
    for i in range(5):
        ledger.append(
            i,
            {
                "event_type": "CREATE_NODE",
                "timestamp": i,
                "node_id": f"n{i}",
                "payload": {"node_id": f"n{i}"},
            },
        )

    graph = PostgresGraph(postgres_service["dsn"])

    def replay(end_ts: int) -> None:
        graph.clear()
        for off, data in ledger.range():
            if data.get("timestamp", 0) > end_ts:
                break
            evt = parse_event(data)
            apply_event_to_graph(evt, graph)

    replay(2)
    assert set(graph.get_all_node_ids()) == {"n0", "n1", "n2"}

    replay(4)
    assert set(graph.get_all_node_ids()) == {"n0", "n1", "n2", "n3", "n4"}

    graph.clear()
    graph.close()
    ledger.close()
