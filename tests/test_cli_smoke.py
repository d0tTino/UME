# tests/test_cli_smoke.py
import subprocess
import sys
import os
import shlex
import pytest  # For tmp_path if needed later, and general test structure

# Determine the absolute path to ume_cli.py
# Assuming tests are run from the project root or a similar consistent location.
# If ume_cli.py is in the root, and tests/ is a subdir, this should work.
CLI_SCRIPT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "ume_cli.py")
)


# Helper function to run CLI commands
def run_cli_commands(
    commands: list[str], cli_args: list[str] | None = None, timeout: int = 5
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
    env = os.environ.copy()
    env["UME_DB_PATH"] = ":memory:"
    process = subprocess.Popen(
        [sys.executable, CLI_SCRIPT_PATH] + (cli_args or []),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",  # Be explicit about encoding
        env=env,
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


def test_cli_start_and_exit_eof():
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


def test_cli_help_command():
    """Test the 'help' command."""
    stdout, stderr, rc = run_cli_commands(["help", "exit"])
    assert "Documented commands (type help <topic>):" in stdout
    assert "new_node" in stdout  # Check for a known command
    assert stderr == ""
    assert rc == 0


def test_cli_show_nodes_empty_and_exit():
    """Test 'show_nodes' on an empty graph and then exit."""
    stdout, stderr, rc = run_cli_commands(["show_nodes", "exit"])
    assert "Welcome to UME CLI." in stdout
    # assert "Nodes:" in stdout # Older version of CLI printed this - removed as it can be confusing
    assert "No nodes in the graph." in stdout  # New version prints this
    assert "Goodbye!" in stdout
    assert stderr == ""
    assert rc == 0


def test_cli_create_node_then_show_nodes():
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


def test_cli_create_and_show_edge(
    tmp_path,
):  # tmp_path not used here, but good to have for snapshot tests
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


def test_cli_redact_node_and_edge():
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


def test_cli_snapshot_save_and_load_and_verify(tmp_path):
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


def test_cli_unknown_command(tmp_path):  # tmp_path not used but is a standard fixture
    """Test that an unknown command is handled gracefully."""
    commands = ["unknown_command_test", "exit"]
    stdout, stderr, rc = run_cli_commands(commands)
    assert "*** Unknown syntax: unknown_command_test" in stdout  # Default Cmd behavior
    assert stderr == ""
    assert rc == 0


def test_cli_snapshot_load_invalid_snapshot(tmp_path):
    """Loading a malformed snapshot should print a user-friendly error."""
    bad_snapshot = tmp_path / "bad_snapshot.json"
    # Write an invalid snapshot (nodes should be a dict)
    bad_snapshot.write_text('{"nodes": []}')

    commands = [f"snapshot_load {shlex.quote(str(bad_snapshot))}", "exit"]
    stdout, stderr, rc = run_cli_commands(commands)

    assert "Error loading snapshot" in stdout
    assert stderr == ""
    assert rc == 0


def test_cli_runs_with_show_warnings_flag():
    """Ensure CLI starts and exits cleanly with the --show-warnings flag."""
    stdout, stderr, rc = run_cli_commands(["exit"], cli_args=["--show-warnings"])
    assert "Welcome to UME CLI." in stdout
    assert "Goodbye!" in stdout
    assert stderr == ""
    assert rc == 0


def test_cli_creates_warnings_log_file(tmp_path):
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
    stdout, stderr, rc = run_cli_commands(["benchmark_vectors --num-vectors 10 --num-queries 2", "exit"])
    assert "Index build time" in stdout
    assert rc == 0
