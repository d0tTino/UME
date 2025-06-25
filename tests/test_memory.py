import time
from ume import Event, EventType
from ume.memory import EpisodicMemory, SemanticMemory


def test_episodic_memory_save_load(tmp_path):
    mem = EpisodicMemory(db_path=":memory:")
    evt = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=int(time.time()),
        payload={"node_id": "e1", "attributes": {"text": "hello"}},
    )
    mem.record_event(evt)
    assert mem.get_episode("e1") == {"text": "hello"}

    snapshot = tmp_path / "episodic.json"
    mem.save(snapshot)
    mem.close()

    mem2 = EpisodicMemory.load(str(snapshot))
    assert mem2.get_episode("e1") == {"text": "hello"}
    mem2.close()


def test_semantic_memory_save_load(tmp_path):
    mem = SemanticMemory(db_path=":memory:")
    mem.add_fact("f1", {"value": 1})
    mem.relate_facts("f1", "f1", "SELF")
    assert mem.get_fact("f1") == {"value": 1}
    assert mem.related_facts("f1") == ["f1"]

    path = tmp_path / "sem.json"
    mem.save(path)
    mem.close()

    loaded = SemanticMemory.load(str(path))
    assert loaded.get_fact("f1") == {"value": 1}
    assert loaded.related_facts("f1") == ["f1"]
    loaded.close()


def test_log_replayed_on_new_instance(tmp_path):
    log = tmp_path / "events.log"
    mem = EpisodicMemory(db_path=":memory:", log_path=str(log))
    evt = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=int(time.time()),
        node_id="e2",
        payload={"node_id": "e2", "attributes": {"text": "hi"}},
    )
    mem.record_event(evt)
    mem.close()

    mem2 = EpisodicMemory(db_path=":memory:", log_path=str(log))
    assert mem2.get_episode("e2") == {"text": "hi"}
    mem2.close()


def test_log_rotation_no_data_loss(tmp_path):
    log = tmp_path / "events.log"
    mem = EpisodicMemory(db_path=":memory:", log_path=str(log), flush_interval=0)
    evt1 = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=int(time.time()),
        node_id="r1",
        payload={"node_id": "r1", "attributes": {"text": "one"}},
    )
    mem.record_event(evt1)
    mem.rotate_logs(max_bytes=1)
    evt2 = Event(
        event_type=EventType.CREATE_NODE,
        timestamp=int(time.time()),
        node_id="r2",
        payload={"node_id": "r2", "attributes": {"text": "two"}},
    )
    mem.record_event(evt2)
    mem.close()

    mem2 = EpisodicMemory(db_path=":memory:", log_path=str(log))
    assert mem2.get_episode("r1") == {"text": "one"}
    assert mem2.get_episode("r2") == {"text": "two"}
    mem2.close()
