# universal-memory-engine
Event-sourced knowledge-graph memory bus for agents and automations (AKA UME).

UME (Universal Memory Engine) is designed to provide a robust, evolving memory for AI agents and automated systems. At its core, UME captures events from various sources and uses them to build and maintain a dynamic knowledge graph. This means that instead of static memory, agents can tap into a rich, interconnected web of information that reflects the history of their interactions and observations. This allows them to understand context, recall past experiences, and make more informed decisions.

The primary motivation behind UME is to equip AI agents with a form of persistent, long-term memory that can adapt over time. This capability is crucial for enabling more complex reasoning, facilitating nuanced inter-agent communication through shared contextual understanding, and ultimately, building more intelligent and autonomous systems. By structuring memory as an event-sourced knowledge graph, UME aims to offer a flexible and scalable solution for these challenges.

## Project Setup

This section outlines the necessary tools for developing and running the Universal Memory Engine (UME). For step-by-step installation and setup instructions, please refer to the [Quickstart](#quickstart) section.

### Core Tools Required:

*   **Python:** Version 3.12 or newer.
*   **Poetry:** For Python dependency management. Installation instructions can be found at [https://python-poetry.org/docs/#installation](https://python-poetry.org/docs/#installation).
*   **Docker:** Docker Desktop (for Windows/macOS) or Docker Engine + Docker Compose (for Linux) is required to run backend services like Redpanda. Download from [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/).

## Architecture

This section provides a high-level overview of the Universal Memory Engine (UME) demo setup.

The current system consists of the following main components:

1.  **Event Producer (`src/ume/producer_demo.py`):**
    *   This script is responsible for generating and sending events to the message broker.
    *   In the demo, it creates a sample JSON event with a `type`, `timestamp`, and `payload`.
    *   It connects to the Kafka/Redpanda broker at `localhost:9092` and sends the event to a predefined topic.

2.  **Message Broker (Redpanda):**
    *   Redpanda is a Kafka-compatible streaming data platform. It is run locally using Docker, as defined in the `docker/docker-compose.yml` file.
    *   It receives events from producers and stores them durably in topics.
    *   It allows multiple consumers to subscribe to these topics and read events.
    *   The demo uses a topic named `ume_demo`.
    *   The Docker setup also includes Redpanda Console, which provides a UI and schema registry capabilities, accessible typically on `localhost:8081` (for the console) while Redpanda itself exposes a schema registry via Pandaproxy on `localhost:8082`.

3.  **Event Consumer (`src/ume/consumer_demo.py`):**
    *   This script subscribes to topics on the message broker to receive and process events.
    *   In the demo, it connects to the Kafka/Redpanda broker at `localhost:9092`, subscribes to the `ume_demo` topic using the group ID `ume_demo_group`.
    *   Upon receiving an event, it logs the event's content. In a more complete system, this component would be responsible for parsing the event, updating the memory graph, triggering actions, or other processing tasks.

### Event Schema

The events exchanged in the demo have a simple JSON structure. Here's an example and description of its fields:

**Example Event:**

```json
{
  "type": "demo_event",
  "timestamp": 1678886400,
  "payload": {
    "message": "Hello from producer_demo!"
  }
}
```

**Fields:**

*   `type` (string): Describes the kind of event. In the demo, this is hardcoded to `"demo_event"`.
*   `timestamp` (integer): A Unix timestamp (seconds since epoch) indicating when the event was generated.
*   `payload` (object): A JSON object containing the actual data of the event. The structure of the payload can vary depending on the event type. For the demo, it includes a simple `message`.

#### CREATE_EDGE Event

Used to create a new directed, labeled edge between two existing nodes.

**Example JSON:**
```json
{
  "event_type": "CREATE_EDGE",
  "timestamp": 1678954321,
  "event_id": "evt_edge_create_001",
  "source": "application_A",
  "node_id": "source_node_alpha",    // ID of the source node
  "target_node_id": "target_node_beta",  // ID of the target node
  "label": "RELATES_TO"             // Label for the edge
  // "payload" is optional for this event type, defaults to {}
}
```
**Required Fields in Data for `parse_event`:**
*   `event_type`: Must be "CREATE_EDGE".
*   `timestamp`: Integer Unix timestamp.
*   `node_id`: String, ID of the source node.
*   `target_node_id`: String, ID of the target node.
*   `label`: String, label for the edge.
**Optional Fields:** `event_id`, `source`, `payload`.

#### DELETE_EDGE Event

Used to remove a specific directed, labeled edge between two nodes.

**Example JSON:**
```json
{
  "event_type": "DELETE_EDGE",
  "timestamp": 1678954322,
  "event_id": "evt_edge_delete_001",
  "source": "application_B",
  "node_id": "source_node_alpha",    // ID of the source node
  "target_node_id": "target_node_beta",  // ID of the target node
  "label": "RELATES_TO"             // Label of the edge to delete
  // "payload" is optional for this event type, defaults to {}
}
```
**Required Fields in Data for `parse_event`:**
*   `event_type`: Must be "DELETE_EDGE".
*   `timestamp`: Integer Unix timestamp.
*   `node_id`: String, ID of the source node.
*   `target_node_id`: String, ID of the target node.
*   `label`: String, label of the edge.
**Optional Fields:** `event_id`, `source`, `payload`.

**Data Flow:**

The basic data flow is as follows:

*   The `producer_demo.py` script sends an event to the `ume_demo` topic in Redpanda.
*   Redpanda stores this event.
*   The `consumer_demo.py` script, subscribed to the `ume_demo` topic, receives this event from Redpanda.
*   The consumer then processes the event (currently, by logging it).

This setup demonstrates a simple event-driven architecture, which is foundational for the UME concept where events are captured and processed to build up a knowledge graph or memory representation.

## UME Graph Model

A core aspect of the Universal Memory Engine (UME) is its ability to construct a knowledge graph from the events it processes. This graph serves as the dynamic, queryable memory for agents and automations.

The detailed schema of this graph, including node types, relationship types, and their properties, is a key part of UME's design. As the system evolves, this will be critical for understanding how memory is structured and utilized.
Additionally, the graph supports directed, labeled **edges** connecting these nodes, representing relationships such as `(source_node_id, target_node_id, 'RELATES_TO')`. Internally, the `MockGraph` stores edges in an adjacency dictionary for faster lookup, while still exposing them as a list of tuples via `get_all_edges()`.

For current plans and eventual detailed documentation on the UME graph model, please see:

*   [**Graph Model Documentation (docs/GRAPH_MODEL.md)**](docs/GRAPH_MODEL.md)

This documentation will be updated as the graph processing components of UME are developed.

## Testing

This project uses [pytest](https://docs.pytest.org/) for unit and integration testing, and [pytest-cov](https://pytest-cov.readthedocs.io/) for test coverage measurement.

### Prerequisites

Ensure you have installed the development dependencies:
```bash
poetry install --with dev
```
(Note: `poetry install` by default installs dev dependencies unless `--no-dev` is specified. However, explicitly mentioning `--with dev` can be clearer for users who might have installed with `--no-dev` previously).

### Running Tests

1.  **Run all tests:**
    To execute the entire test suite, navigate to the project root directory and run:
    ```bash
    poetry run pytest
    ```
    Alternatively, run pytest directly by setting ``PYTHONPATH`` so the
    source directory is discoverable (Python 3.12 or newer is required):
    ```bash
    PYTHONPATH=src pytest
    ```

2.  **Run tests with coverage report:**
    To run tests and generate a code coverage report for the `src/ume` package, use:
    ```bash
    poetry run pytest --cov=src/ume --cov-report=term-missing
    ```
    This will print a summary to the terminal, including which lines of code are not covered by tests. An HTML report can also be generated for more detailed inspection (see pytest-cov documentation).

### Test Location

*   Test files are located in the `tests/` directory at the project root.
*   Test files follow the naming convention `test_*.py`.

### Writing Tests

When contributing new features or fixing bugs, please include relevant tests:
*   **Unit Tests:** For individual functions, classes, or modules.
*   **Integration Tests:** For interactions between components (e.g., testing event flow through a mock Kafka setup, though this is a future enhancement).

Strive for clear, concise tests that verify specific behaviors and edge cases.

## Quickstart

### Prerequisites
- Python 3.12+
- Poetry (https://python-poetry.org)
- Docker & Docker Compose

### 1. Install Python Dependencies
```bash
git clone https://github.com/d0tTino/universal-memory-engine.git
cd universal-memory-engine
poetry install
```

### 2. Start Redpanda (Kafka) via Docker
```bash
# In the repo root, there is a docker-compose.yml that brings up Redpanda
# (Correction: The docker-compose.yml is in the 'docker/' subdirectory)
docker compose -f docker/docker-compose.yml up -d
```

### 3. Run the Consumer Demo
```bash
poetry run python src/ume/consumer_demo.py
```
This script subscribes to topic `ume_demo` on `localhost:9092` and waits for messages.

### 4. Run the Producer Demo
```bash
poetry run python src/ume/producer_demo.py
```
You should see a log entry in the consumer terminal indicating the event was received, parsed, and processed.

### 5. (Optional) Test Malformed Message Handling
Edit `src/ume/producer_demo.py`, add a bad message:
```python
# Example:
# Find the line: producer.produce(TOPIC, value=data, callback=delivery_report)
# Add before or after it:
producer.produce(TOPIC, value=b'not a json', callback=delivery_report) # Add this line
producer.flush() # Ensure it's flushed
```
Restart both demos and observe the consumer logging an error (e.g., `JSONDecodeError` or `EventError`) rather than crashing. Remember to remove the test line afterwards.

## Basic Usage

This section outlines the basic programmatic steps to interact with the UME components using an event-driven approach. Assumes project setup is complete and services (like Redpanda, if using network-based events) are running.

1.  **Obtain a Graph Adapter Instance:**
    Choose an implementation of `IGraphAdapter`. For local testing or simple use cases, `MockGraph` can be used:
    ```python
    from ume import MockGraph, IGraphAdapter

    graph_adapter: IGraphAdapter = MockGraph()
    ```

2.  **Define Event Data Dictionaries:**
    Event data is typically prepared as Python dictionaries.
    ```python
    import time # Required for timestamp

    # Event to create node_A
    event_data_create_A = {
        "event_type": "CREATE_NODE", "timestamp": int(time.time()),
        "node_id": "node_A", # Field used by CREATE_NODE for the node to create
        "payload": {"name": "Alpha Node", "type": "concept"},
        "source": "my_script"
    }

    # Event to create node_B
    event_data_create_B = {
        "event_type": "CREATE_NODE", "timestamp": int(time.time()) + 1,
        "node_id": "node_B", # Field used by CREATE_NODE for the node to create
        "payload": {"name": "Beta Node", "value": 42},
        "source": "my_script"
    }

    # Event to create an edge from node_A to node_B
    event_data_create_edge_A_B = {
        "event_type": "CREATE_EDGE", "timestamp": int(time.time()) + 2,
        "node_id": "node_A",        # Source node for the edge
        "target_node_id": "node_B", # Target node for the edge
        "label": "KNOWS",           # Label of the edge
        "source": "my_script"
        # "payload" is optional for CREATE_EDGE, defaults to {}
    }
    ```

3.  **Parse and Apply Events:**
    Use `parse_event` to validate and convert raw dictionaries into `Event` objects, then `apply_event_to_graph` to modify the graph.
    ```python
    from ume import parse_event, apply_event_to_graph, EventError, ProcessingError
    # graph_adapter should be initialized as in step 1.

    events_to_process = [event_data_create_A, event_data_create_B, event_data_create_edge_A_B]

    for raw_event_data in events_to_process:
        try:
            print(f"Processing raw event: {raw_event_data.get('event_type')} for node {raw_event_data.get('node_id')}")
            parsed_event = parse_event(raw_event_data)
            print(f"  Parsed event: {parsed_event}")
            apply_event_to_graph(parsed_event, graph_adapter)
            print(f"  Successfully applied event {parsed_event.event_id} to graph.")
        except EventError as e:
            print(f"  Error parsing event: {e}")
        except ProcessingError as e:
            print(f"  Error applying event to graph: {e}")
    ```

4.  **Inspect Graph State (Optional):**
    You can inspect the graph's state using adapter methods:
    ```python
    # Check if nodes exist
    if graph_adapter.node_exists("node_A"):
        print(f"Node 'node_A' data: {graph_adapter.get_node('node_A')}")
    if graph_adapter.node_exists("node_B"):
        print(f"Node 'node_B' data: {graph_adapter.get_node('node_B')}")

    # Get all node IDs
    all_node_ids = graph_adapter.get_all_node_ids()
    print(f"All node IDs in graph: {all_node_ids}")

    # Example for find_connected_nodes
    if graph_adapter.node_exists("node_A"):
        try:
            connected_to_A = graph_adapter.find_connected_nodes("node_A")
            print(f"Nodes connected from 'node_A': {connected_to_A}") # Expected: ['node_B'] if KNOWS edge was added

            connected_with_knows_label = graph_adapter.find_connected_nodes("node_A", edge_label="KNOWS")
            print(f"Nodes connected from 'node_A' with label 'KNOWS': {connected_with_knows_label}") # Expected: ['node_B']
        except ProcessingError as e:
             print(f"Error finding connected nodes for node_A: {e}")

    # Get a serializable dump of the graph
    graph_dump = graph_adapter.dump()
    print(f"Graph dump: {graph_dump}")
    # Expected output might look like:
    # {"nodes": {"node_A": {"name": "Alpha Node", ...}, "node_B": {...}}, "edges": [["node_A", "node_B", "KNOWS"]]}
    ```

5.  **Snapshot Graph to File (Optional):**
    Persist the graph's state to a file:
    ```python
    from ume import snapshot_graph_to_file
    # import pathlib # Ensure pathlib is imported if using Path objects for snapshot_path
    # import json # Ensure json is imported if handling json.JSONDecodeError specifically

    try:
        snapshot_path = "my_graph_snapshot.json"
        snapshot_graph_to_file(graph_adapter, snapshot_path)
        print(f"Graph snapshot saved to {snapshot_path}")
    except Exception as e: # Catch potential IOErrors etc.
        print(f"Error saving snapshot: {e}")
    ```

6.  **Load Graph from Snapshot (Optional):**
    Restore a graph's state from a previously saved snapshot file:
    ```python
    from ume import load_graph_from_file, SnapshotError, IGraphAdapter # Ensure IGraphAdapter for type hint
    import pathlib # For pathlib.Path(...).exists()
    import json # For json.JSONDecodeError

    loaded_graph_adapter: IGraphAdapter = None # Initialize
    try:
        # Assuming snapshot_path = "my_graph_snapshot.json" from previous step
        if 'snapshot_path' in locals() and pathlib.Path(snapshot_path).exists():
            loaded_graph_adapter = load_graph_from_file(snapshot_path)
            print(f"Graph loaded successfully from {snapshot_path}")
            print(f"Loaded graph content: {loaded_graph_adapter.dump()}")
        else:
            print(f"Snapshot file {snapshot_path if 'snapshot_path' in locals() else 'my_graph_snapshot.json'} not found, skipping load example.")
    except FileNotFoundError:
        print(f"Error: Snapshot file not found.")
    except json.JSONDecodeError:
        print(f"Error: Snapshot file contains invalid JSON.")
    except SnapshotError as e:
        print(f"Error: Snapshot file has invalid structure: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while loading snapshot: {e}")

    # You can now work with loaded_graph_adapter
    if loaded_graph_adapter and loaded_graph_adapter.node_exists("node_A"):
        print(f"Node 'node_A' from loaded graph: {loaded_graph_adapter.get_node('node_A')}")
    ```
This provides a basic flow for event handling and graph interaction within UME.

## Command-Line Interface (v0.3.0-dev)

You can interact with UME via an interactive REPL (Read-Eval-Print Loop) command-line interface.

To start the CLI, navigate to the project root directory and run:
```bash
poetry run python ume_cli.py
```
Alternatively, if you make the script executable (`chmod +x ume_cli.py`), you can run it directly:
```bash
./ume_cli.py
```
You will see the prompt: `ume> `. Type `help` or `?` to list available commands, or `help <command>` for details on a specific command.

### Available Commands

*   **`new_node <node_id> <json_attributes>`**: Create a new node.
    *   Example: `new_node user123 '{"name": "Alice", "email": "alice@example.com"}'`
*   **`new_edge <source_id> <target_id> <label>`**: Create a new directed edge between two existing nodes.
    *   Example: `new_edge user123 order456 PLACED_ORDER`
*   **`del_edge <source_id> <target_id> <label>`**: Delete an existing directed edge.
    *   Example: `del_edge user123 order456 PLACED_ORDER`
*   **`show_nodes`**: List all node IDs currently in the graph.
*   **`show_edges`**: List all edges in the graph as `(source -> target) [label]`.
*   **`neighbors <node_id> [<label>]`**: List all target nodes that `<node_id>` connects to. Optionally filter by edge label.
    *   Example: `neighbors user123 PLACED_ORDER`
    *   Example: `neighbors user123`
*   **`snapshot_save <filepath>`**: Save the current graph state (nodes and edges) to the given JSON file.
    *   Example: `snapshot_save memory_backup.json`
*   **`snapshot_load <filepath>`**: Clear the current graph and load state from the given JSON file.
    *   Example: `snapshot_load memory_backup.json`
*   **`clear`**: Remove all nodes and edges from the current graph.
*   **`exit`** or **`quit`** or **`EOF`** (Ctrl+D): Quit the UME CLI.
*   **`help`** or **`?`**: Display help information.

### Example Session

```text
ume> new_node alice '{"age": 30, "city": "Wonderland"}'
Node 'alice' created.
ume> new_node bob '{"age": 25, "city": "LookingGlass"}'
Node 'bob' created.
ume> new_edge alice bob friend_of
Edge (alice)->(bob) [friend_of] created.
ume> neighbors alice
Neighbors of 'alice': ['bob']
ume> neighbors alice friend_of
Neighbors of 'alice' with label 'friend_of': ['bob']
ume> show_edges
Edges:
  - alice -> bob [friend_of]
ume> snapshot_save memory.json
Snapshot written to memory.json
ume> clear
Graph cleared.
ume> show_nodes
No nodes in the graph.
ume> snapshot_load memory.json
Graph restored from memory.json
ume> show_nodes
Nodes:
  - alice
  - bob
ume> exit
Goodbye!
```

## Where to Get Help

If you have questions, encounter issues, or want to discuss ideas related to UME, please feel free to:

*   **Open an Issue:** For bug reports, feature requests, or specific questions, please check the [GitHub Issues](https://github.com/d0tTino/universal-memory-engine/issues) page.
*   **Check our Contributing Guide:** For information on how to contribute to the project, see the [CONTRIBUTING.md](CONTRIBUTING.md) file.
