#!/usr/bin/env python3
# ruff: noqa: E402
import argparse
import json
import logging
import shlex
import sys
import time  # Added for timestamp in event creation
import warnings
from pathlib import Path

# Ensure local package import when run directly without installation
_src_path = Path(__file__).resolve().parent / "src"
if _src_path.exists() and str(_src_path) not in sys.path:
    sys.path.insert(0, str(_src_path))

from ume.logging_utils import configure_logging

from ume.config import settings  # noqa: E402
from cmd import Cmd  # noqa: E402
from ume import (  # noqa: E402
    parse_event,
    apply_event_to_graph,
    load_graph_into_existing,
    snapshot_graph_to_file,
    PersistentGraph,
    RoleBasedGraphAdapter,
    enable_snapshot_autosave_and_restore,
    ProcessingError,
    EventError,
    SnapshotError,
    IGraphAdapter,
    log_audit_entry,
    get_audit_entries,
)
from ume.benchmarks import benchmark_vector_store

# It's good practice to handle potential import errors if ume is not installed,
# though for poetry run python ume_cli.py this should be fine.
# For direct ./ume_cli.py, PYTHONPATH or editable install is needed.


class UMEPrompt(Cmd):
    intro = "Welcome to UME CLI. Type help or ? to list commands.\n"
    prompt = "ume> "

    def __init__(self):
        super().__init__()
        db_path = settings.UME_CLI_DB
        base_graph = PersistentGraph(db_path)
        role = settings.UME_ROLE
        if role:
            print(f"INFO: UME-CLI running with role: '{role}'")
            graph: IGraphAdapter = RoleBasedGraphAdapter(base_graph, role)
        else:
            print("INFO: UME-CLI running without a specific role (full permissions).")
            graph = base_graph
        self.graph: IGraphAdapter = graph
        if db_path != ":memory:":
            enable_snapshot_autosave_and_restore(
                base_graph, settings.UME_SNAPSHOT_PATH, 24 * 3600
            )
        self.current_timestamp = int(time.time())

    def _log_audit(self, reason: str) -> None:
        user_id = settings.UME_AGENT_ID
        try:
            log_audit_entry(user_id, reason)
        except Exception as e:  # pragma: no cover - logging failure shouldn't crash
            logging.getLogger(__name__).error("Audit log failure: %s", e)

    def _get_timestamp(self) -> int:
        # Simple incrementing timestamp for demo purposes within a session
        # or could use time.time() for each event
        self.current_timestamp += 1
        return self.current_timestamp

    # ----- Node commands -----
    def do_new_node(self, arg):
        """
        new_node <node_id> <json_attributes>
        Create a new node with the given identifier and JSON attributes.
        Example: new_node user1 '{"name":"Alice","role":"admin"}'
        """
        try:
            parts = shlex.split(arg)
            if len(parts) != 2:
                print("Usage: new_node <node_id> <json_attributes>")
                return
            node_id, json_attrs = parts
            attributes = json.loads(json_attrs)
            # Using a fixed or incrementing timestamp for CLI-generated events
            event_data = {
                "event_type": "CREATE_NODE",
                "node_id": node_id,
                "payload": {"node_id": node_id, "attributes": attributes},
                "timestamp": self._get_timestamp(),
            }
            evt = parse_event(event_data)
            apply_event_to_graph(evt, self.graph)
            print(f"Node '{node_id}' created.")
        except (json.JSONDecodeError, EventError, ProcessingError) as e:
            print(f"Error: {e}")
            self._log_audit(str(e))
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            self._log_audit(str(e))

    # ----- Edge commands -----
    def do_new_edge(self, arg):
        """
        new_edge <source_id> <target_id> <label>
        Create a new directed edge from source to target with the given label.
        Example: new_edge user1 resource42 owns
        """
        try:
            parts = shlex.split(arg)
            if len(parts) != 3:
                print("Usage: new_edge <source_id> <target_id> <label>")
                return
            source_id, target_id, label = parts
            event_data = {
                "event_type": "CREATE_EDGE",
                "node_id": source_id,  # node_id is source for edges
                "target_node_id": target_id,
                "label": label,
                "timestamp": self._get_timestamp(),
            }
            evt = parse_event(event_data)
            apply_event_to_graph(evt, self.graph)
            print(f"Edge ({source_id})->({target_id}) [{label}] created.")
        except (EventError, ProcessingError) as e:
            print(f"Error: {e}")
            self._log_audit(str(e))
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            self._log_audit(str(e))

    def do_del_edge(self, arg):
        """
        del_edge <source_id> <target_id> <label>
        Delete an existing directed edge from source to target with the given label.
        Example: del_edge user1 resource42 owns
        """
        try:
            parts = shlex.split(arg)
            if len(parts) != 3:
                print("Usage: del_edge <source_id> <target_id> <label>")
                return
            source_id, target_id, label = parts
            event_data = {
                "event_type": "DELETE_EDGE",
                "node_id": source_id,  # node_id is source for edges
                "target_node_id": target_id,
                "label": label,
                "timestamp": self._get_timestamp(),
            }
            evt = parse_event(event_data)
            apply_event_to_graph(evt, self.graph)
            print(f"Edge ({source_id})->({target_id}) [{label}] deleted.")
        except (EventError, ProcessingError) as e:
            print(f"Error: {e}")
            self._log_audit(str(e))
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            self._log_audit(str(e))

    def do_redact_node(self, arg):
        """redact_node <node_id>\nMark a node as redacted so it no longer appears in queries."""
        node_id = shlex.split(arg)[0] if arg else None
        if not node_id:
            print("Usage: redact_node <node_id>")
            return
        try:
            self.graph.redact_node(node_id)
            print(f"Node '{node_id}' redacted.")
        except ProcessingError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    def do_redact_edge(self, arg):
        """redact_edge <source_id> <target_id> <label>\nMark an edge as redacted so it no longer appears in queries."""
        try:
            parts = shlex.split(arg)
            if len(parts) != 3:
                print("Usage: redact_edge <source_id> <target_id> <label>")
                return
            source_id, target_id, label = parts
            self.graph.redact_edge(source_id, target_id, label)
            print(f"Edge ({source_id})->({target_id}) [{label}] redacted.")
        except ProcessingError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    # ----- Query commands -----
    def do_show_nodes(self, arg):
        """
        show_nodes
        List all node IDs currently in the graph.
        """
        try:
            nodes = self.graph.get_all_node_ids()
            if not nodes:
                print("No nodes in the graph.")
                return
            print("Nodes:")
            for n in sorted(list(nodes)):  # Sort for consistent output
                print(f"  - {n}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    def do_show_edges(self, arg):
        """
        show_edges
        List all edges in the graph as (source -> target) [label].
        """
        try:
            edges = self.graph.get_all_edges()
            if not edges:
                print("No edges in the graph.")
                return
            print("Edges:")
            # Sort edges for consistent output: by source, then target, then label
            for src, tgt, lbl in sorted(list(edges)):
                print(f"  - {src} -> {tgt} [{lbl}]")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    def do_neighbors(self, arg):
        """
        neighbors <node_id> [<label>]
        List all target nodes that <node_id> connects to. Optionally filter by label.
        Example: neighbors user1 owns
        Example: neighbors user1
        """
        try:
            parts = shlex.split(arg)
            if not parts:
                print("Usage: neighbors <node_id> [<label>]")
                return
            node_id = parts[0]
            label = parts[1] if len(parts) > 1 else None

            targets = self.graph.find_connected_nodes(node_id, label)
            if not targets:
                print(
                    f"No neighbors found for '{node_id}'"
                    + (f" with label '{label}'." if label else ".")
                )
            else:
                print(
                    f"Neighbors of '{node_id}'"
                    + (f" with label '{label}'" if label else "")
                    + f": {sorted(list(targets))}"
                )
        except ProcessingError as e:  # Expected error if node_id not found
            print(f"Error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    def do_show_audit(self, arg):
        """show_audit
        Display audit log entries recorded for rejected or redacted events."""
        entries = get_audit_entries()
        if not entries:
            print("No audit entries.")
            return
        for e in entries:
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(e["timestamp"])))
            print(f"{ts} | {e.get('user_id')} | {e.get('reason')}")

    # ----- Snapshot commands -----
    def do_snapshot_save(self, arg):
        """
        snapshot_save <filepath>
        Save current graph state (nodes + edges) to the given JSON file.
        Example: snapshot_save my_graph.json
        """
        filepath = (
            shlex.split(arg)[0] if arg else None
        )  # shlex.split to handle potential spaces if not quoted
        if not filepath:
            print("Usage: snapshot_save <filepath>")
            return
        try:
            snapshot_graph_to_file(self.graph, filepath)
            print(f"Snapshot written to {filepath}")
        except Exception as e:  # Catch specific IOErrors, etc. if possible
            print(f"Error saving snapshot: {e}")
            self._log_audit(str(e))

    def do_snapshot_load(self, arg):
        """
        snapshot_load <filepath>
        Clear current graph and load state from the given JSON file.
        Example: snapshot_load my_graph.json
        """
        filepath = shlex.split(arg)[0] if arg else None
        if not filepath:
            print("Usage: snapshot_load <filepath>")
            return
        try:
            # Optional: Ask for confirmation before clearing existing graph
            # confirm = input("This will clear the current graph. Proceed? (y/N): ")
            # if confirm.lower() != 'y':
            #     print("Load cancelled.")
            #     return
            load_graph_into_existing(self.graph, filepath)
            print(f"Graph restored from {filepath}")
            self._log_audit(f"snapshot loaded from {filepath}")
        except FileNotFoundError:
            print(f"Error: Snapshot file '{filepath}' not found.")
            self._log_audit("snapshot file not found")
        except (
            json.JSONDecodeError,
            EventError,
            ProcessingError,
            SnapshotError,
        ) as e:  # Catch specific load/parse errors
            print(f"Error loading snapshot: {e}")
            self._log_audit(str(e))
        except Exception as e:
            print(f"An unexpected error occurred during load: {e}")
            self._log_audit(str(e))

    def do_benchmark_vectors(self, arg):
        """benchmark_vectors [--gpu] [--num-vectors N] [--num-queries Q]
        Run a synthetic benchmark of the vector store."""
        parser = argparse.ArgumentParser(prog="benchmark_vectors")
        parser.add_argument("--gpu", action="store_true")
        parser.add_argument("--num-vectors", type=int, default=1000)
        parser.add_argument("--num-queries", type=int, default=100)
        try:
            opts = parser.parse_args(shlex.split(arg))
        except SystemExit:
            return
        result = benchmark_vector_store(
            opts.gpu,
            dim=settings.UME_VECTOR_DIM,
            num_vectors=opts.num_vectors,
            num_queries=opts.num_queries,
        )
        print(
            f"Index build time: {result['build_time']:.2f}s, "
            f"Avg query latency: {result['avg_query_latency']*1000:.3f}ms"
        )

    # ----- Utility commands -----
    def do_clear(self, arg):
        """
        clear
        Remove all nodes and edges from the current graph.
        """
        # Optional: Ask for confirmation
        # confirm = input("Are you sure you want to clear the entire graph? (y/N): ")
        # if confirm.lower() != 'y':
        #     print("Clear cancelled.")
        #     return
        self.graph.clear()
        print("Graph cleared.")
        self._log_audit("graph cleared")

    def do_exit(self, arg):
        """
        exit
        Quit the UME CLI.
        """
        close_method = getattr(self.graph, "close", None)
        if callable(close_method):
            try:
                close_method()
            except (
                Exception
            ) as e:  # pragma: no cover - cleanup failure should not crash CLI
                logging.getLogger(__name__).error("Error closing graph: %s", e)
        print("Goodbye!")
        return True  # returning True exits the Cmd loop

    def do_quit(self, arg):
        """
        quit
        Quit the UME CLI. (Alias for exit)
        """
        return self.do_exit(arg)

    def do_EOF(self, arg):
        """
        EOF (Ctrl+D)
        Quit the UME CLI.
        """
        print("\nGoodbye!")  # Print newline after Ctrl+D
        return True

    # Override to provide custom help intro or suppress default
    # def do_help(self, arg):
    #    Cmd.do_help(self, arg)


def main() -> None:
    """Entry point for the ``ume-cli`` console script."""
    parser = argparse.ArgumentParser(description="UME interactive CLI")
    parser.add_argument(
        "--show-warnings",
        action="store_true",
        help="Display Python warnings during CLI execution",
    )
    parser.add_argument(
        "--warnings-log",
        metavar="PATH",
        help="File to log warnings even when they are not displayed",
    )

    args = parser.parse_args()

    configure_logging()

    _setup_warnings(args.show_warnings, args.warnings_log)

    UMEPrompt().cmdloop()


def _setup_warnings(display: bool, log_file: str | None) -> None:
    """Configure how Python warnings are handled."""
    warnings.simplefilter("default")

    logger = None
    if log_file:
        logger = logging.getLogger("ume_cli.warnings")
        handler = logging.FileHandler(log_file)
        logger.addHandler(handler)
        logger.propagate = False
        logger.setLevel(logging.WARNING)

    orig_showwarning = warnings.showwarning

    def custom_showwarning(
        message: str | Warning,
        category: type[Warning],
        filename: str,
        lineno: int,
        file=None,
        line: str | None = None,
    ) -> None:
        if display:
            orig_showwarning(message, category, filename, lineno, file, line)
        if logger:
            logger.warning(
                "%s:%s: %s: %s", filename, lineno, category.__name__, message
            )

    warnings.showwarning = custom_showwarning


if __name__ == "__main__":
    main()
