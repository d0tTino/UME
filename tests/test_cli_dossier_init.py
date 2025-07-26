import importlib
import sys
import types
from pathlib import Path
import pytest


def test_cli_dossier_init(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import ume.dossier as real_dossier

    stub = types.ModuleType("ume")
    stub.PersistentGraph = object
    stub.RoleBasedGraphAdapter = object
    stub.enable_snapshot_autosave_and_restore = lambda *_, **__: None
    stub.parse_event = lambda *_: None
    stub.apply_event_to_graph = lambda *_: None
    stub.load_graph_into_existing = lambda *_: None
    stub.snapshot_graph_to_file = lambda *_: None
    stub.ProcessingError = Exception
    stub.EventError = Exception
    stub.SnapshotError = Exception
    stub.IGraphAdapter = object
    stub.log_audit_entry = lambda *_: None
    stub.get_audit_entries = lambda *_: []
    stub.DEFAULT_SCHEMA_MANAGER = object()
    stub.dossier = real_dossier

    bench = types.ModuleType("ume.benchmarks")
    bench.benchmark_vector_store = lambda *_: None
    feder = types.ModuleType("ume.federation")
    feder.MirrorMakerDriver = object  # type: ignore[assignment]
    cli_pkg = types.ModuleType("ume.cli")
    compose_pkg = types.ModuleType("ume.cli.compose")
    compose_pkg._compose_down = lambda *_, **__: None
    compose_pkg._compose_ps = lambda *_, **__: None
    compose_pkg._quickstart = lambda *_, **__: None
    cli_pkg.compose = compose_pkg
    prompt_pkg = types.ModuleType("ume.cli.prompt")
    prompt_pkg.UMEPrompt = object
    prompt_pkg.create_graph_adapter = lambda *_, **__: None

    sys.modules["ume"] = stub
    sys.modules["ume.benchmarks"] = bench
    sys.modules["ume.federation"] = feder
    sys.modules["ume.cli"] = cli_pkg
    sys.modules["ume.cli.compose"] = compose_pkg
    sys.modules["ume.cli.prompt"] = prompt_pkg
    sys.modules["ume.dossier"] = real_dossier

    import ume_cli as cli
    importlib.reload(cli)

    monkeypatch.setenv("UME_DOSSIER_PATH", str(tmp_path))

    argv = sys.argv[:]
    sys.argv = ["ume-cli", "dossier", "init", "d1"]
    cli.main()
    out = capsys.readouterr().out
    sys.argv = argv

    dossier_dir = tmp_path / "d1"
    assert (dossier_dir / "profile.yaml").is_file()
    assert "initialized" in out

    for mod in [
        "ume.cli.compose",
        "ume.cli",
        "ume.federation",
        "ume.benchmarks",
        "ume",
    ]:
        sys.modules.pop(mod, None)
