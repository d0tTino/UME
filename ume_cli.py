#!/usr/bin/env python3
import json
import shlex
import time 
from cmd import Cmd
import pathlib # For consistency, though CLI_SNAPSHOT_PATH is already Path

from ume import (
    parse_event, apply_event_to_graph, 
    load_graph_from_file, snapshot_graph_to_file,
    CLI_SNAPSHOT_PATH, # For auto-load/save path
    MockGraph, IGraphAdapter, 
    ProcessingError, EventError, SnapshotError # Ensure SnapshotError is imported
)

class UMEPrompt(Cmd):
    # intro is set in __init__ based on load status
    prompt = "ume> "

    def __init__(self):
        # Auto-load graph on startup
        try:
            self.graph: IGraphAdapter = load_graph_from_file(CLI_SNAPSHOT_PATH)
            self.intro = f"Welcome to UME CLI. Graph loaded from {CLI_SNAPSHOT_PATH}. Type help or ? to list commands.\n"
        except SnapshotError as e: 
            self.intro = f"Welcome to UME CLI. Snapshot Error: {e}. Starting with an empty graph. Type help or ? to list commands.\n"
            self.graph: IGraphAdapter = MockGraph()
        except Exception as e: # Catch any other unexpected error during load
            self.intro = f"Welcome to UME CLI. An unexpected error occurred loading snapshot: {e}. Starting with an empty graph. Type help or ? to list commands.\n"
            self.graph: IGraphAdapter = MockGraph()
        
        self.current_timestamp = int(time.time()) 
        super().__init__() # Call super AFTER self.intro is set


    def _get_timestamp(self) -> int:
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
            node_id_val, json_attrs = parts # Renamed to avoid conflict with Event field
            attributes = json.loads(json_attrs)
            event_data = {
                "event_type": "CREATE_NODE",
                "node_id": node_id_val,    # This is the node_id for the node being created
                "payload": attributes,     # This is the payload for the node
                "timestamp": self._get_timestamp(),
                "source": "cli"
            }
            evt = parse_event(event_data)
            apply_event_to_graph(evt, self.graph)
            print(f"Node '{node_id_val}' created.")
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
            source_id, target_id, label_val = parts # Renamed to avoid conflict
            event_data = {
                "event_type": "CREATE_EDGE",
                "node_id": source_id, 
                "target_node_id": target_id,
                "label": label_val,
                "timestamp": self._get_timestamp(),
                "source": "cli"
            }
            evt = parse_event(event_data)
            apply_event_to_graph(evt, self.graph)
            print(f"Edge ({source_id})->({target_id}) [{label_val}] created.")
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
            source_id, target_id, label_val = parts # Renamed
            event_data = {
                "event_type": "DELETE_EDGE",
                "node_id": source_id, 
                "target_node_id": target_id,
                "label": label_val,
                "timestamp": self._get_timestamp(),
                "source": "cli"
            }
            evt = parse_event(event_data)
            apply_event_to_graph(evt, self.graph)
            print(f"Edge ({source_id})->({target_id}) [{label_val}] deleted.")
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
            for n in sorted(list(nodes)):
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
            node_id_val = parts[0] # Renamed
            label_val = parts[1] if len(parts) > 1 else None # Renamed
        
            targets = self.graph.find_connected_nodes(node_id_val, label_val)
            if not targets:
                 print(f"No neighbors found for '{node_id_val}'" + (f" with label '{label_val}'." if label_val else "."))
            else:
                print(f"Neighbors of '{node_id_val}'" + (f" with label '{label_val}'" if label_val else "") + f": {sorted(list(targets))}")
        except ProcessingError as e: 
            print(f"Error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    # ----- Snapshot commands -----
    def do_snapshot_save(self, arg):
        """
        snapshot_save [<filepath>]
        Save current graph state to the given JSON file, or default CLI path if none.
        Example: snapshot_save my_graph.json
        Example: snapshot_save
        """
        parts = shlex.split(arg)
        filepath = parts[0] if parts else CLI_SNAPSHOT_PATH
        try:
            snapshot_graph_to_file(self.graph, filepath)
            print(f"Snapshot written to {filepath}")
        except SnapshotError as e:
            print(f"Error saving snapshot: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during save: {e}")

    def do_snapshot_load(self, arg):
        """
        snapshot_load [<filepath>]
        Clear current graph and load state from JSON file, or default CLI path if none.
        Example: snapshot_load my_graph.json
        Example: snapshot_load
        """
        parts = shlex.split(arg)
        filepath = parts[0] if parts else CLI_SNAPSHOT_PATH
        try:
            new_graph = load_graph_from_file(filepath)
            self.graph = new_graph 
            print(f"Graph restored from {filepath}")
        except SnapshotError as e: 
             print(f"Error loading snapshot: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during load: {e}")

    # ----- Utility commands -----
    def do_clear(self, arg):
        """
        clear
        Remove all nodes and edges from the current graph.
        """
        self.graph.clear()
        print("Graph cleared.")

    def _save_graph_on_exit(self):
        """Helper to save graph, used by exit methods and interrupt handler."""
        try:
            snapshot_graph_to_file(self.graph, CLI_SNAPSHOT_PATH)
            print(f"Graph saved to {CLI_SNAPSHOT_PATH}.")
        except SnapshotError as e:
            print(f"Warning: Failed to save snapshot to {CLI_SNAPSHOT_PATH}: {e}")
        except Exception as e:
            print(f"Warning: An unexpected error occurred while saving snapshot: {e}")

    def do_exit(self, arg):
        """
        exit
        Quit the UME CLI (auto-saves current graph to default snapshot).
        """
        self._save_graph_on_exit()
        print("Goodbye!")
        return True

    def do_quit(self, arg):
        """
        quit
        Quit the UME CLI. (Alias for exit, auto-saves graph)
        """
        return self.do_exit(arg)

    def do_EOF(self, arg):
        """
        EOF (Ctrl+D)
        Quit the UME CLI. (Auto-saves graph)
        """
        print() # Newline after ^D
        self._save_graph_on_exit()
        print("Goodbye!")
        return True

if __name__ == "__main__":
    prompt_instance = UMEPrompt()
    try:
        prompt_instance.cmdloop()
    except KeyboardInterrupt:
        print("\nInterrupted. Saving graph...", end="") 
        if hasattr(prompt_instance, 'graph') and hasattr(prompt_instance, '_save_graph_on_exit'):
            prompt_instance._save_graph_on_exit()
        else:
            print(" Graph instance not available for saving.") 
        print("Exiting.")
```
