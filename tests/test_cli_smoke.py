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
def run_cli_commands(commands: list[str], timeout: int = 5) -> tuple[str, str]:
    """
    Runs the UME CLI as a subprocess and feeds it a list of commands.

    Args:
        commands: A list of command strings to send to the CLI.
                  Each command should be a separate string (newline will be added).
        timeout: Timeout in seconds for the subprocess communication.

    Returns:
        A tuple (stdout, stderr) from the CLI process.
    """
    env = os.environ.copy()
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
    env["PYTHONPATH"] = os.pathsep.join([src_dir, env.get("PYTHONPATH", "")])
    process = subprocess.Popen(
        [sys.executable, CLI_SCRIPT_PATH],
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

    return stdout, stderr


def test_cli_start_and_exit_eof():
    """Test starting the CLI and exiting immediately with EOF (Ctrl+D)."""
    # Sending an empty list of commands and relying on EOF from closing stdin.
    # However, communicate('') might not send EOF correctly always.
    # A more reliable way to test exit is an explicit 'exit' command.
    stdout, stderr = run_cli_commands(["exit"])
    assert "Welcome to UME CLI." in stdout
    assert "ume> " in stdout  # Should see at least one prompt
    assert "Goodbye!" in stdout
    assert stderr == ""


def test_cli_help_command():
    """Test the 'help' command."""
    stdout, stderr = run_cli_commands(["help", "exit"])
    assert "Documented commands (type help <topic>):" in stdout
    assert "new_node" in stdout  # Check for a known command
    assert stderr == ""


def test_cli_show_nodes_empty_and_exit():
    """Test 'show_nodes' on an empty graph and then exit."""
    stdout, stderr = run_cli_commands(["show_nodes", "exit"])
    assert "Welcome to UME CLI." in stdout
    # assert "Nodes:" in stdout # Older version of CLI printed this - removed as it can be confusing
    assert "No nodes in the graph." in stdout  # New version prints this
    assert "Goodbye!" in stdout
    assert stderr == ""


def test_cli_create_node_then_show_nodes():
    """Test creating a node and then listing nodes."""
    commands = [
        'new_node test1 \'{"name":"Node One", "value":42}\'',  # Ensure JSON is single-quoted for shlex
        "show_nodes",
        "exit",
    ]
    stdout, stderr = run_cli_commands(commands)

    assert "Node 'test1' created." in stdout
    assert "Nodes:" in stdout
    assert "- test1" in stdout  # list of nodes should include test1
    assert stderr == ""


def test_cli_create_and_show_edge(
    tmp_path,
):  # tmp_path not used here, but good to have for snapshot tests
    """Test creating nodes, an edge, and then showing edges."""
    commands = [
        'new_node source_n \'{"type":"source"}\'',
        'new_node target_n \'{"type":"target"}\'',
        "new_edge source_n target_n IS_CONNECTED_TO",
        "show_edges",
        "exit",
    ]
    stdout, stderr = run_cli_commands(commands)

    assert "Node 'source_n' created." in stdout
    assert "Node 'target_n' created." in stdout
    assert "Edge (source_n)->(target_n) [IS_CONNECTED_TO] created." in stdout
    assert "Edges:" in stdout
    assert "- source_n -> target_n [IS_CONNECTED_TO]" in stdout
    assert stderr == ""


def test_cli_snapshot_save_and_load_and_verify(tmp_path):
    """Test snapshot save, clear, load, and verify content."""
    snapshot_file = tmp_path / "cli_test_snapshot.json"
    commands_part1 = [
        'new_node nodeA \'{"data":"A"}\'',
        'new_node nodeB \'{"data":"B"}\'',
        "new_edge nodeA nodeB LINKED_TO",
        f"snapshot_save {shlex.quote(str(snapshot_file))}",  # Use shlex.quote for filepath
    ]
    # Run first part to save
    stdout1, stderr1 = run_cli_commands(commands_part1 + ["exit"])
    assert f"Snapshot written to {str(snapshot_file)}" in stdout1
    assert stderr1 == ""
    assert snapshot_file.is_file()

    commands_part2 = [
        "clear",  # Clear the graph
        "show_nodes",  # Should be empty
        f"snapshot_load {shlex.quote(str(snapshot_file))}",  # Use shlex.quote for filepath
        "show_nodes",  # Should show nodeA, nodeB
        "show_edges",  # Should show the edge
    ]
    # Run second part to clear, load, and verify
    stdout2, stderr2 = run_cli_commands(commands_part2 + ["exit"])
    assert "Graph cleared." in stdout2
    assert "No nodes in the graph." in stdout2  # After clear
    assert f"Graph restored from {str(snapshot_file)}" in stdout2
    assert "- nodeA" in stdout2
    assert "- nodeB" in stdout2
    assert "- nodeA -> nodeB [LINKED_TO]" in stdout2
    assert stderr2 == ""


def test_cli_unknown_command(tmp_path):  # tmp_path not used but is a standard fixture
    """Test that an unknown command is handled gracefully."""
    commands = ["unknown_command_test", "exit"]
    stdout, stderr = run_cli_commands(commands)
    assert "*** Unknown syntax: unknown_command_test" in stdout  # Default Cmd behavior
    assert stderr == ""
