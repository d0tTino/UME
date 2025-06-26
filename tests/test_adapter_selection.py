import time
from ume import Event, apply_event_to_graph
from ume.adapters import Neo4jAdapter, LanceDBAdapter
from ume_cli import UMEPrompt


def test_prompt_env_adapter(monkeypatch):
    monkeypatch.setenv("UME_GRAPH_ADAPTER", "neo4j")
    prompt = UMEPrompt()
    assert isinstance(prompt.graph, Neo4jAdapter)


def test_prompt_cli_arg_adapter():
    prompt = UMEPrompt(adapter_name="lancedb")
    assert isinstance(prompt.graph, LanceDBAdapter)
    event = Event(
        event_type="CREATE_NODE",
        timestamp=int(time.time()),
        payload={"node_id": "n1"},
    )
    apply_event_to_graph(event, prompt.graph)
    assert prompt.graph.node_exists("n1")
