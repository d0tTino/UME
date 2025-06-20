import time

from ume import PersistentGraph


def test_persistent_graph_created_at_columns():
    graph = PersistentGraph(":memory:")
    cur = graph.conn.execute("PRAGMA table_info('nodes')")
    cols = {row[1] for row in cur.fetchall()}
    assert "created_at" in cols

    cur = graph.conn.execute("PRAGMA table_info('edges')")
    cols = {row[1] for row in cur.fetchall()}
    assert "created_at" in cols


def test_purge_old_records_removes_old_entries():
    graph = PersistentGraph(":memory:")
    graph.add_node("n1", {})
    graph.add_node("n2", {})
    graph.add_edge("n1", "n2", "LINK")

    old_ts = int(time.time()) - 10 * 86400
    with graph.conn:
        graph.conn.execute("UPDATE nodes SET created_at=? WHERE id='n1'", (old_ts,))
        graph.conn.execute("UPDATE edges SET created_at=?", (old_ts,))

    graph.purge_old_records(5 * 86400)

    assert not graph.node_exists("n1")
    assert graph.node_exists("n2")
    assert graph.get_all_edges() == []
