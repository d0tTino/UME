import importlib
import sys
import types


def test_replay_graph_builds_graph(monkeypatch, capsys):
    """Ensure `ume replay-graph` rebuilds graph from a small ledger."""

    # Stub required modules imported by ume_cli
    logging_utils = types.ModuleType("ume.logging_utils")
    logging_utils.configure_logging = lambda *_, **__: None
    config_mod = types.ModuleType("ume.config")
    config_mod.settings = types.SimpleNamespace()
    cli_pkg = types.ModuleType("ume.cli")
    compose_pkg = types.ModuleType("ume.cli.compose")
    compose_pkg._compose_down = lambda *_, **__: None
    compose_pkg._compose_ps = lambda *_, **__: None
    compose_pkg._quickstart = lambda *_, **__: None
    cli_pkg.compose = compose_pkg
    prompt_pkg = types.ModuleType("ume.cli.prompt")
    prompt_pkg.UMEPrompt = object
    prompt_pkg.create_graph_adapter = lambda *_, **__: None

    # Simple in-memory ledger and graph implementation
    class DummyGraph:
        def __init__(self) -> None:
            self.nodes: set[str] = set()
            self.edges: list[tuple[str, str, str]] = []

        def get_all_node_ids(self) -> list[str]:
            return list(self.nodes)

        def get_all_edges(self) -> list[tuple[str, str, str]]:
            return list(self.edges)

    class DummyLedger:
        def __init__(self) -> None:
            self.events: list[tuple[int, dict[str, object]]] = []

        def append(self, offset: int, event: dict[str, object]) -> None:
            self.events.append((offset, event))

        def range(self, start: int = 0, end: int | None = None):
            for off, data in self.events:
                if end is not None and off > end:
                    break
                yield off, data

    ledger = DummyLedger()
    ledger.append(0, {"event_type": "CREATE_NODE", "timestamp": 0, "node_id": "a", "payload": {"node_id": "a"}})
    ledger.append(1, {"event_type": "CREATE_NODE", "timestamp": 0, "node_id": "b", "payload": {"node_id": "b"}})
    ledger.append(2, {"event_type": "CREATE_EDGE", "timestamp": 0, "node_id": "a", "target_node_id": "b", "label": "L"})

    def graph_from_event_ledger(*_, **__):
        graph = DummyGraph()
        for _, data in ledger.range(end=2):
            if data["event_type"] == "CREATE_NODE":
                graph.nodes.add(data["node_id"])
            elif data["event_type"] == "CREATE_EDGE":
                graph.edges.append((data["node_id"], data["target_node_id"], data["label"]))
        return graph

    replay_mod = types.ModuleType("ume.replay")
    replay_mod.graph_from_event_ledger = graph_from_event_ledger

    stub = types.ModuleType("ume")
    stub.replay = replay_mod

    monkeypatch.setitem(sys.modules, "ume.logging_utils", logging_utils)
    monkeypatch.setitem(sys.modules, "ume.config", config_mod)
    monkeypatch.setitem(sys.modules, "ume.cli", cli_pkg)
    monkeypatch.setitem(sys.modules, "ume.cli.compose", compose_pkg)
    monkeypatch.setitem(sys.modules, "ume.cli.prompt", prompt_pkg)
    monkeypatch.setitem(sys.modules, "ume.replay", replay_mod)
    monkeypatch.setitem(sys.modules, "ume", stub)

    import ume_cli
    importlib.reload(ume_cli)

    argv = sys.argv[:]
    sys.argv = ["ume-cli", "replay-graph", "--db-path", ":memory:", "--end-offset", "2"]
    ume_cli.main()
    out = capsys.readouterr().out
    sys.argv = argv
    sys.modules.pop("ume_cli", None)

    assert "Rebuilt graph" in out
    assert "2 nodes" in out
    assert "1 edges" in out
