#!/usr/bin/env python3
import json
import shlex
import time # Added for timestamp in event creation
from cmd import Cmd
from ume import parse_event, apply_event_to_graph, load_graph_from_file, snapshot_graph_to_file
from ume import MockGraph, ProcessingError, EventError, IGraphAdapter # Added IGraphAdapter for type hint

# It's good practice to handle potential import errors if ume is not installed,
# though for poetry run python ume_cli.py this should be fine.
# For direct ./ume_cli.py, PYTHONPATH or editable install is needed.

class UMEPrompt(Cmd):
    intro = "Welcome to UME CLI. Type help or ? to list commands.\n"
    prompt = "ume> "

    def __init__(self):
        super().__init__()
        self.graph: IGraphAdapter = MockGraph() # Use interface type hint
        self.current_timestamp = int(time.time()) # For consistent timestamps in a session if needed, or increment

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
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

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
                "node_id": source_id, # node_id is source for edges
                "target_node_id": target_id,
                "label": label,
                "timestamp": self._get_timestamp()
            }
            evt = parse_event(event_data)
            apply_event_to_graph(evt, self.graph)
            print(f"Edge ({source_id})->({target_id}) [{label}] created.")
        except (EventError, ProcessingError) as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")


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
                "node_id": source_id, # node_id is source for edges
                "target_node_id": target_id,
                "label": label,
                "timestamp": self._get_timestamp()
            }
            evt = parse_event(event_data)
            apply_event_to_graph(evt, self.graph)
            print(f"Edge ({source_id})->({target_id}) [{label}] deleted.")
        except (EventError, ProcessingError) as e:
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
            for n in sorted(list(nodes)): # Sort for consistent output
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
                 print(f"No neighbors found for '{node_id}'" + (f" with label '{label}'." if label else "."))
            else:
                print(f"Neighbors of '{node_id}'" + (f" with label '{label}'" if label else "") + f": {sorted(list(targets))}")
        except ProcessingError as e: # Expected error if node_id not found
            print(f"Error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    # ----- Snapshot commands -----
    def do_snapshot_save(self, arg):
        """
        snapshot_save <filepath>
        Save current graph state (nodes + edges) to the given JSON file.
        Example: snapshot_save my_graph.json
        """
        filepath = shlex.split(arg)[0] if arg else None # shlex.split to handle potential spaces if not quoted
        if not filepath:
            print("Usage: snapshot_save <filepath>")
            return
        try:
            snapshot_graph_to_file(self.graph, filepath)
            print(f"Snapshot written to {filepath}")
        except Exception as e: # Catch specific IOErrors, etc. if possible
            print(f"Error saving snapshot: {e}")

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
            new_graph = load_graph_from_file(filepath)
            self.graph = new_graph # Replace current graph
            print(f"Graph restored from {filepath}")
        except FileNotFoundError:
            print(f"Error: Snapshot file '{filepath}' not found.")
        except (json.JSONDecodeError, EventError, ProcessingError) as e: # Catch specific load/parse errors
             print(f"Error loading snapshot: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during load: {e}")


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

    def do_exit(self, arg):
        """
        exit
        Quit the UME CLI.
        """
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
        print("\nGoodbye!") # Print newline after Ctrl+D
        return True

    # Override to provide custom help intro or suppress default
    # def do_help(self, arg):
    #    Cmd.do_help(self, arg)

if __name__ == "__main__":
    UMEPrompt().cmdloop()

