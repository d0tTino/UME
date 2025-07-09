import os
from pathlib import Path
import pytest



def test_umeprompt_commands(tmp_path: Path) -> None:
    os.environ["UME_CLI_DB"] = ":memory:"
    os.environ["UME_ROLE"] = "AnalyticsAgent"
    import importlib
    import ume_cli as cli
    import ume.config as cfg
    importlib.reload(cfg)
    importlib.reload(cli)
    UMEPrompt = cli.UMEPrompt
    _setup_warnings = cli._setup_warnings
    prompt = UMEPrompt()
    prompt.do_new_node('n1 "{}"')
    prompt.do_new_node('n2 "{}"')
    prompt.do_new_edge("n1 n2 L")
    assert set(prompt.graph.get_all_node_ids()) == {"n1", "n2"}
    assert ("n1", "n2", "L") in prompt.graph.get_all_edges()

    prompt.do_register_schema(
        "2.0.0 src/ume/schemas/graph_schema_v2.yaml ume.protos.graph_v2_pb2"
    )
    prompt.do_migrate_schema("1.0.0 2.0.0")

    snap = tmp_path / "snap.json"
    prompt.do_snapshot_save(str(snap))
    assert snap.is_file()

    prompt.do_del_edge("n1 n2 LINKS_TO")
    assert prompt.graph.get_all_edges() == []

    prompt.do_redact_node("n1")
    assert prompt.graph.get_node("n1") is None

    prompt.do_clear("")
    assert prompt.graph.get_all_node_ids() == []

    prompt.do_snapshot_load(str(snap))
    assert set(prompt.graph.get_all_node_ids()) == {"n1", "n2"}

    # exercise query and audit related commands
    prompt.do_show_nodes("")
    prompt.do_show_edges("")
    prompt.do_neighbors("n1")
    prompt.do_show_audit("")

    _setup_warnings(True, str(tmp_path / "warn.log"))
    prompt.do_exit("")


def test_compose_ps(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import importlib
    import ume_cli as cli

    importlib.reload(cli)

    def fake_check_output(cmd: list[str], **_: object) -> str:
        assert "ps" in cmd
        return "api healthy\nagent unhealthy"

    monkeypatch.setattr(cli.subprocess, "check_output", fake_check_output)

    cli._compose_ps()

    out = capsys.readouterr().out
    assert "api: healthy" in out
    assert "agent: unhealthy" in out


def test_up_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    import sys
    import ume_cli as cli

    importlib.reload(cli)

    calls: list[str] = []

    def fake_compose_up(*_: object, **__: object) -> None:
        calls.append("up")

    monkeypatch.setattr(cli, "_compose_up", fake_compose_up)
    monkeypatch.setattr(cli, "_ensure_env_file", lambda *_: None)
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **k: None)

    sys.argv = ["ume_cli.py", "up", "--no-confirm"]
    cli.main()
    sys.argv = ["ume_cli.py", "quickstart", "--no-confirm"]
    cli.main()

    assert calls == ["up", "up"]
