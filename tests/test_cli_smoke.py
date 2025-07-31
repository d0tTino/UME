# tests/test_cli_smoke.py
import subprocess
import sys
import os
import shlex
import types
from pathlib import Path
import pytest  # For tmp_path if needed later, and general test structure

# Determine the absolute path to ume_cli.py
# Assuming tests are run from the project root or a similar consistent location.
# If ume_cli.py is in the root, and tests/ is a subdir, this should work.
CLI_SCRIPT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "ume_cli.py")
)


# Helper function to run CLI commands
def run_cli_commands(
    commands: list[str],
    cli_args: list[str] | None = None,
    timeout: int = 5,
    env: dict[str, str] | None = None,
) -> tuple[str, str, int]:
    """
    Runs the UME CLI as a subprocess and feeds it a list of commands.

    Args:
        commands: A list of command strings to send to the CLI.
                  Each command should be a separate string (newline will be added).
        timeout: Timeout in seconds for the subprocess communication.

    Returns:
        A tuple (stdout, stderr, returncode) from the CLI process. If the CLI
        exits with a non-zero status, the test fails.
    """
    proc_env = os.environ.copy()
    proc_env["UME_DB_PATH"] = ":memory:"
    proc_env["UME_CLI_DB"] = ":memory:"
    proc_env["UME_ROLE"] = "AnalyticsAgent"

    # Remove coverage-related environment variables that may interfere with
    # subprocess execution. These are added by pytest-cov when running tests
    # with coverage enabled and cause warnings on stderr which break the CLI
    # smoke tests' expectations.
    for key in list(proc_env.keys()):
        if key.startswith("COV_CORE_") or key.startswith("COVERAGE_"):
            proc_env.pop(key, None)
    if env:
        proc_env.update(env)
    process = subprocess.Popen(
        [sys.executable, CLI_SCRIPT_PATH] + (cli_args or []),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",  # Be explicit about encoding
        env=proc_env,
    )
    # Join commands with newlines and ensure a final newline for the last command
    # and to trigger EOF for cmdloop if 'exit' is not the last command.
    input_str = "\n".join(commands) + "\n"

    try:
        stdout, stderr = process.communicate(input_str, timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        pytest.fail(
            f"CLI command sequence timed out after {timeout} seconds. Stdout: {stdout}, Stderr: {stderr}"
        )

    rc = process.returncode
    if rc != 0:
        pytest.fail(f"CLI exited with code {rc}. Stdout: {stdout}, Stderr: {stderr}")

    return stdout, stderr, rc


def test_cli_start_and_exit_eof() -> None:
    """Test starting the CLI and exiting immediately with EOF (Ctrl+D)."""
    # Sending an empty list of commands and relying on EOF from closing stdin.
    # However, communicate('') might not send EOF correctly always.
    # A more reliable way to test exit is an explicit 'exit' command.
    stdout, stderr, rc = run_cli_commands(["exit"])
    assert "Welcome to UME CLI." in stdout
    assert "ume> " in stdout  # Should see at least one prompt
    assert "Goodbye!" in stdout
    assert stderr == ""
    assert rc == 0


def test_cli_help_command() -> None:
    """Test the 'help' command."""
    stdout, stderr, rc = run_cli_commands(["help", "exit"])
    assert "Documented commands (type help <topic>):" in stdout
    assert "new_node" in stdout  # Check for a known command
    assert stderr == ""
    assert rc == 0


def test_cli_show_nodes_empty_and_exit() -> None:
    """Test 'show_nodes' on an empty graph and then exit."""
    stdout, stderr, rc = run_cli_commands(["show_nodes", "exit"])
    assert "Welcome to UME CLI." in stdout
    # assert "Nodes:" in stdout # Older version of CLI printed this - removed as it can be confusing
    assert "No nodes in the graph." in stdout  # New version prints this
    assert "Goodbye!" in stdout
    assert stderr == ""
    assert rc == 0


def test_cli_create_node_then_show_nodes() -> None:
    """Test creating a node and then listing nodes."""
    commands = [
        'new_node test1 \'{"name":"Node One", "value":42}\'',  # Ensure JSON is single-quoted for shlex
        "show_nodes",
        "exit",
    ]
    stdout, stderr, rc = run_cli_commands(commands)

    assert "Node 'test1' created." in stdout
    assert "Nodes:" in stdout
    assert "- test1" in stdout  # list of nodes should include test1
    assert stderr == ""
    assert rc == 0


def test_cli_create_and_show_edge(tmp_path: Path) -> None:  # tmp_path not used here, but good to have for snapshot tests
    """Test creating nodes, an edge, and then showing edges."""
    commands = [
        'new_node source_n \'{"type":"UserMemory"}\'',
        'new_node target_n \'{"type":"UserMemory"}\'',
        "new_edge source_n target_n ASSOCIATED_WITH",
        "show_edges",
        "exit",
    ]
    stdout, stderr, rc = run_cli_commands(commands)

    assert "Node 'source_n' created." in stdout
    assert "Node 'target_n' created." in stdout
    assert "Edge (source_n)->(target_n) [ASSOCIATED_WITH] created." in stdout
    assert "Edges:" in stdout
    assert "- source_n -> target_n [ASSOCIATED_WITH]" in stdout
    assert stderr == ""
    assert rc == 0


def test_cli_redact_node_and_edge() -> None:
    commands = [
        'new_node n1 "{}"',
        'new_node n2 "{}"',
        "new_edge n1 n2 L",
        "redact_node n1",
        "redact_edge n1 n2 L",
        "show_nodes",
        "show_edges",
        "exit",
    ]
    stdout, stderr, rc = run_cli_commands(commands)
    assert "Node 'n1' redacted." in stdout
    assert "Edge (n1)->(n2) [L] redacted." in stdout
    # After redaction only n2 should be listed
    assert "- n1" not in stdout
    assert "- n2" in stdout
    # All edges should be hidden
    assert "No edges in the graph." in stdout
    assert stderr == ""
    assert rc == 0


def test_cli_snapshot_save_and_load_and_verify(tmp_path: Path) -> None:
    """Test snapshot save, clear, load, and verify content."""
    snapshot_file = tmp_path / "cli_test_snapshot.json"
    commands_part1 = [
        'new_node nodeA \'{"data":"A"}\'',
        'new_node nodeB \'{"data":"B"}\'',
        "new_edge nodeA nodeB L",
        f"snapshot_save {shlex.quote(str(snapshot_file))}",  # Use shlex.quote for filepath
    ]
    # Run first part to save
    stdout1, stderr1, rc1 = run_cli_commands(commands_part1 + ["exit"])
    assert f"Snapshot written to {str(snapshot_file)}" in stdout1
    assert stderr1 == ""
    assert rc1 == 0
    assert snapshot_file.is_file()

    commands_part2 = [
        "clear",  # Clear the graph
        "show_nodes",  # Should be empty
        f"snapshot_load {shlex.quote(str(snapshot_file))}",  # Use shlex.quote for filepath
        "show_nodes",  # Should show nodeA, nodeB
        "show_edges",  # Should show the edge
    ]
    # Run second part to clear, load, and verify
    stdout2, stderr2, rc2 = run_cli_commands(commands_part2 + ["exit"])
    assert "Graph cleared." in stdout2
    assert "No nodes in the graph." in stdout2  # After clear
    assert f"Graph restored from {str(snapshot_file)}" in stdout2
    assert "- nodeA" in stdout2
    assert "- nodeB" in stdout2
    assert "- nodeA -> nodeB [L]" in stdout2
    assert stderr2 == ""
    assert rc2 == 0


def test_cli_unknown_command(tmp_path: Path) -> None:  # tmp_path not used but is a standard fixture
    """Test that an unknown command is handled gracefully."""
    commands = ["unknown_command_test", "exit"]
    stdout, stderr, rc = run_cli_commands(commands)
    assert "*** Unknown syntax: unknown_command_test" in stdout  # Default Cmd behavior
    assert stderr == ""
    assert rc == 0


def test_cli_snapshot_load_invalid_snapshot(tmp_path: Path) -> None:
    """Loading a malformed snapshot should print a user-friendly error."""
    bad_snapshot = tmp_path / "bad_snapshot.json"
    # Write an invalid snapshot (nodes should be a dict)
    bad_snapshot.write_text('{"nodes": []}')

    commands = [f"snapshot_load {shlex.quote(str(bad_snapshot))}", "exit"]
    stdout, stderr, rc = run_cli_commands(commands)

    assert "Error loading snapshot" in stdout
    assert stderr == ""
    assert rc == 0


def test_cli_runs_with_show_warnings_flag() -> None:
    """Ensure CLI starts and exits cleanly with the --show-warnings flag."""
    stdout, stderr, rc = run_cli_commands(["exit"], cli_args=["--show-warnings"])
    assert "Welcome to UME CLI." in stdout
    assert "Goodbye!" in stdout
    assert stderr == ""
    assert rc == 0


def test_cli_creates_warnings_log_file(tmp_path: Path) -> None:
    """Running with --warnings-log should create the log file."""
    log_file = tmp_path / "warnings.log"
    stdout, stderr, rc = run_cli_commands(
        ["exit"], cli_args=["--warnings-log", str(log_file)]
    )
    assert log_file.is_file()
    assert "Goodbye!" in stdout
    assert stderr == ""
    assert rc == 0


def test_cli_benchmark_vectors():
    faiss = pytest.importorskip("faiss")
    if not hasattr(faiss, "IndexFlatL2"):
        pytest.skip("faiss is missing required functionality")
    stdout, stderr, rc = run_cli_commands(["benchmark_vectors --num-vectors 10 --num-queries 2", "exit"])
    assert "Avg build time" in stdout
    assert rc == 0


def test_cli_new_node_invalid_json() -> None:
    stdout, stderr, rc = run_cli_commands(["new_node bad '{not_json}'", "exit"])
    assert "Error:" in stdout
    assert rc == 0


def test_cli_sync_without_peer() -> None:
    stdout, _, rc = run_cli_commands(["sync", "exit"])
    assert "Peer cluster not configured" in stdout
    assert rc == 0


def test_cli_set_peer_and_sync_calls_replicator(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    import ume.config as cfg
    import ume.federation as federation
    import ume.cli.prompt as prompt

    importlib.reload(cfg)
    importlib.reload(prompt)

    called: list[str] = []

    class DummyReplicator:
        def __init__(self, _settings: object, peer: str) -> None:
            called.append(f"peer={peer}")

        def replicate_once(self) -> None:
            called.append("replicate_once")

        def stop(self) -> None:
            called.append("stop")

    monkeypatch.setattr(federation, "ClusterReplicator", DummyReplicator)
    prompt = prompt.UMEPrompt()
    prompt.do_set_peer("foo:9092")
    prompt.do_sync("")

    assert "peer=foo:9092" in called
    assert "replicate_once" in called
    assert "stop" in called


def test_cli_up_and_down(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import importlib
    import ume_cli as cli
    from ume.cli import compose

    importlib.reload(cli)
    importlib.reload(compose)

    run_calls: list[list[str]] = []

    def fake_run(cmd: list[str], check: bool = True, **_: object) -> None:
        run_calls.append(cmd)

    def fake_check_output(cmd: list[str], **_: object) -> str:
        if "ps" in cmd:
            return "redpanda healthy\nneo4j healthy\nume-api healthy\n"

        return ""

    monkeypatch.setattr(compose.shutil, "which", lambda name: "/usr/bin/" + name)
    
    monkeypatch.setattr(compose.subprocess, "run", fake_run)
    monkeypatch.setattr(compose.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(compose.time, "sleep", lambda *_: None)
    monkeypatch.setattr(compose, "_ensure_env_file", lambda *_: None)
    monkeypatch.setenv("UME_SKIP_DOCKER_CHECK", "1")
    monkeypatch.setenv("UME_SKIP_NPM_CHECK", "1")

    argv = sys.argv[:]
    sys.argv = ["ume-cli", "up", "--no-confirm"]
    cli.main()
    out_up = capsys.readouterr().out
    sys.argv = argv

    assert any("up" in " ".join(c) for c in run_calls)
    assert "http://localhost:8000/docs" in out_up

    run_calls.clear()
    sys.argv = ["ume-cli", "down"]
    cli.main()
    out_down = capsys.readouterr().out
    sys.argv = argv

    assert any("down" in " ".join(c) for c in run_calls)
    assert "Stack stopped." in out_down


def test_top_level_ume_up(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the top-level ``ume up`` command runs ``_quickstart``."""
    import importlib
    import ume.__main__ as main

    importlib.reload(main)

    called: dict[str, bool] = {}

    def fake_quickstart(
        no_confirm: bool = False, force_build: bool = False
    ) -> None:
        called["no_confirm"] = no_confirm
        called["force_build"] = force_build

    monkeypatch.setattr(main, "_quickstart", fake_quickstart)

    argv = sys.argv[:]
    sys.argv = ["ume", "up", "--no-confirm", "--force-build"]
    main.main()
    sys.argv = argv

    assert called.get("no_confirm") is True
    assert called.get("force_build") is True


def test_cli_up_custom_compose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Start the stack using a temporary compose file."""
    import importlib
    import ume_cli as cli
    from ume.cli import compose

    importlib.reload(cli)
    importlib.reload(compose)

    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        "\n".join(
            [
                "version: '3'",
                "services:",
                "  redpanda:",
                "    image: foo",
                "  privacy-agent:",
                "    image: foo",
                "  ume-api:",
                "    image: foo",
            ]
        )
    )

    run_calls: list[list[str]] = []
    ps_calls: list[list[str]] = []

    def fake_run(cmd: list[str], check: bool = True, **_: object) -> None:
        run_calls.append(cmd)

    def fake_check_output(cmd: list[str], **_: object) -> str:
        ps_calls.append(cmd)
        if "ps" in cmd:
            return "redpanda healthy\nprivacy-agent healthy\nume-api healthy\n"
        return ""

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("UME_SKIP_DOCKER_CHECK", "1")
    monkeypatch.setenv("UME_SKIP_NPM_CHECK", "1")
    monkeypatch.setattr(compose.subprocess, "run", fake_run)
    monkeypatch.setattr(compose.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(compose.time, "sleep", lambda *_: None)
    orig_compose_up = compose._compose_up
    monkeypatch.setattr(
        compose,
        "_compose_up",
        lambda compose_file=compose_file, timeout=120: orig_compose_up(
            compose_file, timeout
        ),
    )

    argv = sys.argv[:]
    sys.argv = ["ume-cli", "up"]
    cli.main()
    sys.argv = argv

    out = capsys.readouterr().out

    assert any(str(compose_file) in " ".join(c) for c in run_calls)
    assert any("ps" in c for cmd in ps_calls for c in cmd)
    assert "http://localhost:8000/docs" in out


def test_cli_quickstart_creates_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import importlib
    import ume_cli as cli
    from ume.cli import compose

    importlib.reload(cli)
    importlib.reload(compose)

    run_calls: list[list[str]] = []

    def fake_run(cmd: list[str], check: bool = True, **_: object) -> None:
        run_calls.append(cmd)

    def fake_check_output(cmd: list[str], **_: object) -> str:
        if "ps" in cmd:
            return "redpanda healthy\nneo4j healthy\nume-api healthy\n"
        return ""

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("UME_SKIP_DOCKER_CHECK", "1")
    monkeypatch.setenv("UME_SKIP_NPM_CHECK", "1")
    monkeypatch.setattr(compose.subprocess, "run", fake_run)
    monkeypatch.setattr(compose.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(compose.time, "sleep", lambda *_: None)

    argv = sys.argv[:]
    sys.argv = ["ume-cli", "quickstart", "--no-confirm"]
    cli.main()
    sys.argv = argv

    capsys.readouterr()  # flush output

    assert (tmp_path / ".env").is_file()
    assert any("generate-certs.sh" in " ".join(c) for c in run_calls)


def test_cli_snapshot_schedule(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import importlib
    import ume.auto_snapshot as auto_snapshot

    # Provide a lightweight stub for the ``ume`` package so ``ume_cli`` can be
    # imported without pulling in optional heavy dependencies.
    stub = types.ModuleType("ume")
    class DummyGraph:
        def __init__(self, *_: object, **__: object) -> None:
            pass

    stub.PersistentGraph = DummyGraph
    stub.RoleBasedGraphAdapter = DummyGraph
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
    sys.modules["ume.auto_snapshot"] = auto_snapshot
    sys.modules["ume.cli"] = cli_pkg
    sys.modules["ume.cli.compose"] = compose_pkg
    sys.modules["ume.cli.prompt"] = prompt_pkg

    import ume_cli as cli
    importlib.reload(cli)

    called: dict[str, object] = {}

    class DummyThread:
        def is_alive(self) -> bool:
            return False

        def join(self, timeout: float | None = None) -> None:
            pass

    def fake_enable(graph: object, path: object, interval: int) -> tuple[DummyThread, callable]:
        called["path"] = str(path)
        called["interval"] = interval

        return DummyThread(), lambda: None

    monkeypatch.setattr(auto_snapshot, "enable_periodic_snapshot", fake_enable)
    monkeypatch.setattr(auto_snapshot, "disable_periodic_snapshot", lambda: None)

    argv = sys.argv[:]
    sys.argv = ["ume-cli", "snapshot-schedule", "--interval", "1"]
    cli.main()
    out = capsys.readouterr().out
    sys.argv = argv

    assert called["interval"] == 1
    assert "Snapshots will be written" in out

    for mod in [
        "ume.cli.compose",
        "ume.cli",
        "ume.auto_snapshot",
        "ume.federation",
        "ume.benchmarks",
        "ume",
    ]:
        sys.modules.pop(mod, None)


def test_cli_ledger_replay(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import importlib
    import types
    from ume.event_ledger import EventLedger

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

    event_mod = types.ModuleType("ume.event_ledger")
    ledger = EventLedger(str(tmp_path / "ledger.db"))
    ledger.append(0, {"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "a", "payload": {"node_id": "a"}})
    event_mod.EventLedger = EventLedger
    event_mod.event_ledger = ledger

    sys.modules["ume"] = stub
    sys.modules["ume.benchmarks"] = bench
    sys.modules["ume.federation"] = feder
    sys.modules["ume.cli"] = cli_pkg
    sys.modules["ume.cli.compose"] = compose_pkg
    sys.modules["ume.cli.prompt"] = prompt_pkg
    sys.modules["ume.event_ledger"] = event_mod

    import ume_cli as cli
    importlib.reload(cli)

    argv = sys.argv[:]
    sys.argv = ["ume-cli", "ledger-replay", "--end-offset", "0"]
    cli.main()
    out = capsys.readouterr().out
    sys.argv = argv

    assert "\"a\"" in out

    for mod in [
        "ume.cli.compose",
        "ume.cli",
        "ume.federation",
        "ume.benchmarks",
        "ume.event_ledger",
        "ume",
    ]:
        sys.modules.pop(mod, None)


def test_cli_dossier_snapshot_schedule(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import importlib
    import ume.dossier.scheduler as sched

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
    dossier_mod = types.ModuleType("ume.dossier")
    class DummyDossier:
        root = Path("/tmp")

        @classmethod
        def load(cls):
            return cls()

    dossier_mod.Dossier = DummyDossier
    dossier_mod.scheduler = sched
    sys.modules["ume.dossier"] = dossier_mod
    sys.modules["ume.dossier.scheduler"] = sched
    sys.modules["ume.cli"] = cli_pkg
    sys.modules["ume.cli.compose"] = compose_pkg
    sys.modules["ume.cli.prompt"] = prompt_pkg

    import ume_cli as cli
    importlib.reload(cli)

    called: dict[str, object] = {}

    class DummyThread:
        def is_alive(self) -> bool:
            return False

        def join(self, timeout: float | None = None) -> None:
            pass

    def fake_start(dossier: object, interval_seconds: int) -> tuple[DummyThread, callable]:
        called["interval"] = interval_seconds
        return DummyThread(), lambda: None

    monkeypatch.setattr(sched, "start_dossier_snapshot_scheduler", fake_start)
    monkeypatch.setattr(sched, "stop_dossier_snapshot_scheduler", lambda: None)

    argv = sys.argv[:]
    sys.argv = ["ume-cli", "dossier", "snapshot-schedule", "--interval", "1"]
    cli.main()
    out = capsys.readouterr().out
    sys.argv = argv

    assert called["interval"] == 1
    assert "Snapshots will be written" in out

    for mod in [
        "ume.cli.compose",
        "ume.cli",
        "ume.dossier.scheduler",
        "ume.federation",
        "ume.benchmarks",
        "ume",
    ]:
        sys.modules.pop(mod, None)


def test_cli_env_file_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import importlib
    from ume.cli import compose

    importlib.reload(compose)

    env_file = tmp_path / ".env"
    env_file.write_text("UME_AUDIT_SIGNING_KEY=default-key\n")  # pragma: allowlist secret

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(compose.secrets, "token_hex", lambda *_: "new-key")

    compose._ensure_env_file()

    out = capsys.readouterr().out
    assert "insecure default key" in out


def test_cli_env_file_no_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import importlib
    from ume.cli import compose

    importlib.reload(compose)

    env_file = tmp_path / ".env"
    env_file.write_text("UME_AUDIT_SIGNING_KEY=old-key\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(compose.secrets, "token_hex", lambda *_: "default-key")

    compose._ensure_env_file()

    out = capsys.readouterr().out
    assert "insecure default key" not in out


def test_cli_up_missing_docker(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """CLI should exit with message when Docker is absent."""
    import importlib
    import ume_cli as cli
    from ume.cli import compose

    importlib.reload(cli)
    importlib.reload(compose)

    monkeypatch.setattr(compose.shutil, "which", lambda name: None if name == "docker" else "/usr/bin/" + name)
    # Ensure previous tests haven't disabled the Docker check.
    monkeypatch.delenv("UME_SKIP_DOCKER_CHECK", raising=False)
    monkeypatch.delenv("UME_SKIP_NPM_CHECK", raising=False)
    monkeypatch.setattr(compose, "_compose_up", lambda *_: None)
    monkeypatch.setattr(compose.subprocess, "run", lambda *_, **__: None)

    argv = sys.argv[:]
    sys.argv = ["ume-cli", "up", "--no-confirm"]
    with pytest.raises(SystemExit):
        cli.main()
    out = capsys.readouterr().out
    sys.argv = argv

    assert "Docker is required" in out


def test_cli_up_missing_node(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """CLI should exit with message when Node/npm is absent."""
    import importlib
    import ume_cli as cli
    from ume.cli import compose

    importlib.reload(cli)
    importlib.reload(compose)

    monkeypatch.setattr(compose.shutil, "which", lambda name: None if name == "npm" else "/usr/bin/" + name)
    # Ensure previous tests haven't disabled the Node check.
    monkeypatch.delenv("UME_SKIP_DOCKER_CHECK", raising=False)
    monkeypatch.delenv("UME_SKIP_NPM_CHECK", raising=False)
    monkeypatch.setattr(compose, "_compose_up", lambda *_: None)
    monkeypatch.setattr(compose.subprocess, "run", lambda *_, **__: None)

    argv = sys.argv[:]
    sys.argv = ["ume-cli", "up", "--no-confirm"]
    with pytest.raises(SystemExit):
        cli.main()
    out = capsys.readouterr().out
    sys.argv = argv

    assert "npm is required" in out


def test_cli_missing_docker_does_not_create_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure .env is not created when Docker is missing."""
    import importlib
    import ume_cli as cli
    from ume.cli import compose

    importlib.reload(cli)
    importlib.reload(compose)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        compose.shutil,
        "which",
        lambda name: None if name == "docker" else "/usr/bin/" + name,
    )
    monkeypatch.delenv("UME_SKIP_DOCKER_CHECK", raising=False)
    monkeypatch.delenv("UME_SKIP_NPM_CHECK", raising=False)

    argv = sys.argv[:]
    sys.argv = ["ume-cli", "up", "--no-confirm"]
    with pytest.raises(SystemExit):
        cli.main()
    sys.argv = argv

    assert not (tmp_path / ".env").exists()


def test_cli_missing_node_does_not_create_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure .env is not created when npm is missing."""
    import importlib
    import ume_cli as cli
    from ume.cli import compose

    importlib.reload(cli)
    importlib.reload(compose)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        compose.shutil,
        "which",
        lambda name: None if name == "npm" else "/usr/bin/" + name,
    )
    monkeypatch.delenv("UME_SKIP_DOCKER_CHECK", raising=False)
    monkeypatch.delenv("UME_SKIP_NPM_CHECK", raising=False)

    argv = sys.argv[:]
    sys.argv = ["ume-cli", "up", "--no-confirm"]
    with pytest.raises(SystemExit):
        cli.main()
    sys.argv = argv

    assert not (tmp_path / ".env").exists()


def test_subprocess_up_creates_env_and_checks_health(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run ``ume_cli.py up`` in a subprocess and verify health checks."""
    stubs = tmp_path / "stubs" / "ume" / "cli"
    stubs.mkdir(parents=True)
    (stubs / "__init__.py").write_text("")
    # stub for ume.logging_utils.configure_logging
    log_dir = tmp_path / "stubs" / "ume"
    (log_dir / "__init__.py").write_text("")
    (log_dir / "logging_utils.py").write_text("def configure_logging():\n    pass\n")
    cfg_dir = log_dir / "config"
    cfg_dir.mkdir()
    (cfg_dir / "__init__.py").write_text(
        "class Settings:\n    UME_CLI_DB = ':memory:'\n\nsettings = Settings()\n"
    )
    prompt_dir = stubs  # already ume/cli
    (prompt_dir / "prompt.py").write_text(
        "class UMEPrompt:\n    def cmdloop(self):\n        pass\n\n"
        "def create_graph_adapter(*a, **k):\n    pass\n"
    )
    # sitecustomize to inject stubs before ``ume_cli`` imports modules
    sitecustomize = tmp_path / "stubs" / "sitecustomize.py"
    sitecustomize.write_text(
        """
import sys, types, importlib.util, pathlib
base = pathlib.Path(__file__).parent
compose_path = base / 'ume' / 'cli' / 'compose.py'
spec = importlib.util.spec_from_file_location('ume.cli.compose', compose_path)
compose = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compose)
ume_pkg = types.ModuleType('ume')
sys.modules.setdefault('ume', ume_pkg)
sys.modules['ume.cli'] = types.ModuleType('ume.cli')
sys.modules['ume.cli.compose'] = compose
prompt = types.ModuleType('ume.cli.prompt')
class UMEPrompt:
    def cmdloop(self):
        pass

def create_graph_adapter(*a, **k):
    pass

prompt.UMEPrompt = UMEPrompt
prompt.create_graph_adapter = create_graph_adapter
sys.modules['ume.cli.prompt'] = prompt
log = types.ModuleType('ume.logging_utils')
log.configure_logging = lambda: None
sys.modules['ume.logging_utils'] = log
conf = types.ModuleType('ume.config')
class Settings:
    UME_CLI_DB = ':memory:'

conf.settings = Settings()
sys.modules['ume.config'] = conf
"""
    )
    compose_stub = stubs / "compose.py"
    compose_stub.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "",
                "def _compose_up(compose_file: Path = Path('docker-compose.yml'), timeout: int = 120) -> None:",
                "    print('redpanda healthy')",
                "    print('ume-api healthy')",
                "    print('Stack running. API docs: http://localhost:8000/docs')",
                "",
                "def _compose_down(compose_file: Path = Path('docker-compose.yml')) -> None:",
                "    print('Stack stopped.')",
                "",
                "def _compose_ps(compose_file: Path = Path('docker-compose.yml')) -> None:",
                "    print('redpanda: healthy')",
                "    print('ume-api: healthy')",
                "",
                "def _ensure_env_file(env_file: Path = Path('.env')) -> None:",
                "    env_file.write_text('UME_AUDIT_SIGNING_KEY=test\\nUME_OAUTH_PASSWORD=test\\n')",
                "    print('Created .env from env.example with random UME_AUDIT_SIGNING_KEY and UME_OAUTH_PASSWORD')",
                "",
                "def _quickstart(no_confirm: bool = False, force_build: bool = False) -> None:",
                "    _ensure_env_file(Path('.env'))",
                "    _compose_up()",
            ]
        )
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{tmp_path / 'stubs'}{os.pathsep}" + env.get("PYTHONPATH", "")
    env.pop("PYTHONHOME", None)

    result = subprocess.run(
        [sys.executable, CLI_SCRIPT_PATH, "up", "--no-confirm"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert (tmp_path / ".env").exists()
    assert "redpanda healthy" in result.stdout
    assert "ume-api healthy" in result.stdout
    assert "http://localhost:8000/docs" in result.stdout

def test_wrapper_script_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """scripts/ume_up.sh should exit with status 0 when tools are present."""
    script = Path(__file__).resolve().parents[1] / "scripts" / "ume_up.sh"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # stub poetry to handle install and run commands
    poetry_stub = bin_dir / "poetry"
    poetry_stub.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = install ]; then exit 0; fi\n"
        "if [ \"$1\" = run ]; then shift; exec \"$@\"; fi\n"
    )
    poetry_stub.chmod(0o755)
    for cmd in ["node", "docker", "ume"]:
        f = bin_dir / cmd
        f.write_text("#!/bin/sh\nexit 0\n")
        f.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}" + env.get("PATH", "")
    result = subprocess.run(["bash", str(script), "--no-confirm"], env=env, capture_output=True, text=True)
    assert result.returncode == 0

