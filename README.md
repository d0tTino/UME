# universal-memory-engine
Event-sourced knowledge-graph memory bus for agents and automations (AKA UME).

UME (Universal Memory Engine) is designed to provide a robust, evolving memory for AI agents and automated systems. At its core, UME captures events from various sources and uses them to build and maintain a dynamic knowledge graph. This means that instead of static memory, agents can tap into a rich, interconnected web of information that reflects the history of their interactions and observations. This allows them to understand context, recall past experiences, and make more informed decisions.

The primary motivation behind UME is to equip AI agents with a form of persistent, long-term memory that can adapt over time. This capability is crucial for enabling more complex reasoning, facilitating nuanced inter-agent communication through shared contextual understanding, and ultimately, building more intelligent and autonomous systems. By structuring memory as an event-sourced knowledge graph, UME aims to offer a flexible and scalable solution for these challenges.

## Core Modules
The engine is built from a few key components:
- **Privacy Agent** (`src/ume/pipeline/privacy_agent.py`)
  - Redacts personally identifiable information (PII) from incoming events using Presidio.
  - Forwards sanitized events to downstream Kafka topics.
- **FastAPI API** (`src/ume/api.py`)
  - HTTP service exposing graph queries and analytics endpoints.
  - Enforces role-based access to graph operations.
- **Graph Adapters** (`src/ume/graph_adapter.py`, `src/ume/neo4j_graph.py`)
  - Define a common interface for manipulating different graph backends.
  - Includes adapters for in-memory, SQLite, and Neo4j storage as well as RBAC wrappers.
- **Vector Store** (`src/ume/vector_store.py`)
  - Maintains a FAISS index of node embeddings for similarity search.
  - Use `create_default_store()` to instantiate one from environment settings.
- **CLI** (`ume_cli.py`)
  - Command-line utility for producing events, inspecting the graph, and running maintenance tasks.

### Event Flow
```
Producer --> ume-raw-events --> Privacy Agent --> ume-clean-events --> Graph Consumer --> Graph Adapter --> Storage (SQLite/Neo4j)
```

## Project Setup

This section outlines the necessary tools for developing and running the Universal Memory Engine (UME). For step-by-step installation and setup instructions, please refer to the [Quickstart](#quickstart) section.

### Core Tools Required:

*   **Python:** Version **3.10** or newer is required.
*   **Poetry:** For Python dependency management. Installation instructions can be found at [https://python-poetry.org/docs/#installation](https://python-poetry.org/docs/#installation).
*   **Docker:** Docker Desktop (for Windows/macOS) or Docker Engine + Docker Compose (for Linux) is required to run backend services like Redpanda. Download from [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/).

After installing these tools and cloning the repository, install all Python
dependencies (including development requirements) with:

```bash
poetry install --with dev
```
This installs core dependencies such as `faust-streaming` for stream processing
and `faiss-cpu` for the vector store.

## Architecture

This section provides a high-level overview of the Universal Memory Engine (UME) demo setup.
For a diagram that shows how each module maps to the pillars in the roadmap, see [docs/ARCHITECTURE_OVERVIEW.md](docs/ARCHITECTURE_OVERVIEW.md).

The current system consists of the following main components:

1.  **Event Producer (`src/ume/producer_demo.py`):**
    *   This script is responsible for generating and sending events to the message broker.
    *   In the demo, it creates a sample JSON event with a `type`, `timestamp`, and `payload`.
    *   It connects to the Kafka/Redpanda broker at `localhost:9092` and sends the event to a predefined topic.

2.  **Message Broker (Redpanda):**
    *   Redpanda is a Kafka-compatible streaming data platform. It is run locally using Docker, as defined in the `docker/docker-compose.yml` file.
    *   It receives events from producers and stores them durably in topics.
    *   It allows multiple consumers to subscribe to these topics and read events.
    *   The demo uses a topic named `ume-clean-events`, configured for unlimited retention and immutable append-only storage so it acts as the canonical audit trail.
    *   The Docker setup also includes Redpanda Console, which provides a UI and schema registry capabilities, accessible typically on `localhost:8081` (for the console) while Redpanda itself exposes a schema registry via Pandaproxy on `localhost:8082`.

3.  **Event Consumer (`src/ume/consumer_demo.py`):**
    *   This script subscribes to topics on the message broker to receive and process events.
    *   In the demo, it connects to the Kafka/Redpanda broker at `localhost:9092`, subscribes to the `ume-clean-events` topic using the group ID `ume_client_group`.
    *   Upon receiving an event, it logs the event's content. In a more complete system, this component would be responsible for parsing the event, updating the memory graph, triggering actions, or other processing tasks.

### Event Schema

The events exchanged in the demo have a simple JSON structure. Here's an example and description of its fields:

**Example Event:**

```json
{
  "event_type": "demo_event",
  "timestamp": 1678886400,
  "payload": {
    "message": "Hello from producer_demo!"
  }
}
```

**Fields:**

*   `event_type` (string): Describes the kind of event. In the demo, this is hardcoded to `"demo_event"`.
*   `timestamp` (integer): A Unix timestamp (seconds since epoch) indicating when the event was generated.
*   `payload` (object): A JSON object containing the actual data of the event. The structure of the payload can vary depending on the event type. For the demo, it includes a simple `message`.

All official event types such as `CREATE_NODE` or `CREATE_EDGE` have
corresponding JSON Schema definitions under `src/ume/schemas`.  Producers
should validate events using `ume.validate_event_dict()` before publishing to
Kafka or any other broker.

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

**Event Flow:** *(see the full diagram in [docs/ARCHITECTURE_OVERVIEW.md](docs/ARCHITECTURE_OVERVIEW.md))*

```
Producer --> ume-raw-events --> Privacy Agent --> ume-clean-events
     --> Graph Consumer --> Graph Adapter --> Storage (SQLite/Neo4j) & Vector Store
```

1. `producer_demo.py` publishes raw events to the `ume-raw-events` Kafka topic.
2. The **Privacy Agent** consumes these events, redacts PII, and forwards sanitized messages to `ume-clean-events`.
3. A graph consumer reads sanitized events and applies them via the configured **Graph Adapter**.
4. The adapter persists nodes and edges to the chosen backend, such as SQLite or Neo4j, and writes embeddings to a vector store.

When nodes include textual attributes, the consumer generates vector embeddings using the configured model. These embeddings are stored in the vector store and queried via similarity search to locate relevant nodes before running graph traversals.

This pipeline demonstrates how UME transforms incoming events into a persistent knowledge graph.

## UME Graph Model

A core aspect of the Universal Memory Engine (UME) is its ability to construct a knowledge graph from the events it processes. This graph serves as the dynamic, queryable memory for agents and automations.

The detailed schema of this graph, including node types, relationship types, and their properties, is a key part of UME's design. As the system evolves, this will be critical for understanding how memory is structured and utilized.
Additionally, the graph supports directed, labeled **edges** connecting these nodes, representing relationships such as `(source_node_id, target_node_id, 'RELATES_TO')`. The default implementation, `PersistentGraph`, stores this data in a lightweight SQLite database for durability while still exposing edges as a list of tuples via `get_all_edges()`.

For current plans and eventual detailed documentation on the UME graph model, please see:

*   [**Graph Model Documentation (docs/GRAPH_MODEL.md)**](docs/GRAPH_MODEL.md)
*   [**Graph Listener Guide (docs/GRAPH_LISTENERS.md)**](docs/GRAPH_LISTENERS.md)
*   [**LLM Ferry (docs/LLM_FERRY.md)**](docs/LLM_FERRY.md)
*   [**Angel Bridge (docs/ANGEL_BRIDGE.md)**](docs/ANGEL_BRIDGE.md)
*   [**API Reference (docs/API_REFERENCE.md)**](docs/API_REFERENCE.md)
*   [**Self-Hosted Runner Setup (docs/SELF_HOSTED_RUNNER.md)**](docs/SELF_HOSTED_RUNNER.md)
*   [**DAGExecutor Guide (docs/DAG_EXECUTOR.md)**](docs/DAG_EXECUTOR.md)
*   [**Resource Scheduler**](#resource-scheduler)

## Resource Scheduler

The `ResourceScheduler` provides a lightweight way to limit how many tasks
can use a given resource simultaneously. Concurrency counts are configured per
resource.

```python
from ume import ResourceScheduler, ScheduledTask

sched = ResourceScheduler(resources={"gpu": 1})
sched.run([
    ScheduledTask(func=lambda e: do_gpu_work(), resource="gpu"),
    ScheduledTask(func=lambda e: more_gpu_work(), resource="gpu"),
])
```

This documentation will be updated as the graph processing components of UME are developed.

## Testing

This project uses [pytest](https://docs.pytest.org/) for unit and integration testing, and [pytest-cov](https://pytest-cov.readthedocs.io/) for test coverage measurement.

### Prerequisites

You must run the tests with **Python 3.10** or newer.

Ensure you have installed the development dependencies:
```bash
poetry install --with dev
```
(This project uses `pre-commit` for linting and type checks. To run the same
checks as CI, execute:)
```bash
pre-commit run --all-files
```
(Optional) regenerate the detect-secrets baseline with:
```bash
detect-secrets scan > .secrets.baseline
```
(Note: `poetry install` by default installs dev dependencies unless `--no-dev` is specified. However, explicitly mentioning `--with dev` can be clearer for users who might have installed with `--no-dev` previously).

To determine if your changes require running tests and linters, execute:
```bash
python scripts/ci_should_run.py && echo "Run tests" || echo "Docs only, skipping"
```
If the repository does not have an `origin/main` branch, the helper falls back
to comparing against the previous commit, so it will still return a meaningful
result.


### Running Tests

1.  **Run all tests:**
    To execute the entire test suite, navigate to the project root directory and run:
    ```bash
    poetry run pytest
    ```
    Alternatively, run pytest directly by setting ``PYTHONPATH`` so the
    source directory is discoverable (Python 3.10 or newer is required):
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

## CI Workflow

This project uses GitHub Actions to run linting, type checks, unit tests, and
coverage reporting. The `coverage` job executes on a self-hosted runner as
described in [docs/SELF_HOSTED_RUNNER.md](docs/SELF_HOSTED_RUNNER.md). It uses
`concurrency` with `cancel-in-progress` to terminate earlier runs on the same
branch. Steps are skipped when only documentation or comments change, so tests
and linters run only for code modifications.

## Access Control

UME enforces access restrictions for both Kafka topics and graph operations.
Example ACL commands for Redpanda and a description of roles are provided in
[docs/ACCESS_CONTROL.md](docs/ACCESS_CONTROL.md).

## Alignment Plugins

Before events modify the graph, UME runs any installed *alignment plugins*.
Plugins implement a simple interface with a `validate(event)` method and are
loaded from the `ume.plugins.alignment` package. A plugin should raise
`PolicyViolationError` if an event violates its policy. When this happens the
event is rejected and the error propagates to the caller.

The repository includes a basic example plugin that forbids creating a node with
ID `"forbidden"`. Additional policies can be added by dropping new modules in
`ume/plugins/alignment/` that register themselves using
`register_plugin()`.

### Rego Policy Engine

If the optional `policy` extras are installed (`poetry install --with policy`),
UME also loads any `.rego` files found in `ume/plugins/alignment/policies/` and
evaluates them using the built-in `RegoPolicyEngine`. Policies should define
`allow` rules under the `ume` package. Events are rejected when the query
`data.ume.allow` does not evaluate to `true` for the event input.

## Quickstart

### Prerequisites
- Python **3.10** or newer
- Poetry (https://python-poetry.org)
- Docker & Docker Compose
- A non-default `UME_AUDIT_SIGNING_KEY` environment variable
- See [docs/WINDOWS_QUICKSTART.md](docs/WINDOWS_QUICKSTART.md) for Windows-specific instructions

### 1. Install Python Dependencies
```bash
git clone https://github.com/d0tTino/universal-memory-engine.git
cd universal-memory-engine
poetry install --with dev
# Include optional embedding dependencies to run the full test suite
poetry install --with embedding
poetry run python -m spacy download en_core_web_lg
```
To automate the above steps (including installing development tools), you can
run the helper script:
```bash
./codex_setup.sh
```
This script installs Python 3.10 if missing, installs all dependencies and
development tools, automatically installs the pre-commit hooks, and fixes the
lock file if needed. After running it, you can verify the environment with:
```bash
pre-commit run --all-files
PYTHONPATH=src pytest

```

Create a `.env` file in the project root before starting any services. Copy the
template from [`docs/ENV_EXAMPLE.md`](docs/ENV_EXAMPLE.md) and set a
non-default `UME_AUDIT_SIGNING_KEY` or UME will refuse to start:

```bash
# .env
UME_AUDIT_SIGNING_KEY=my-ume-key
```

See [`docs/ENV_EXAMPLE.md`](docs/ENV_EXAMPLE.md) for the full list of available
settings.

### 2. Start the Docker Stack
The `ume` CLI can spin up all services for local development. From the repository root run:


```bash
poetry run python ume_cli.py up
```

The command waits for the services to become healthy and then prints the main URLs:

```
http://localhost:8000/docs
http://localhost:8000/recall

```

If you want to enable TLS for the broker and API, generate certificates first:
```bash
bash docker/generate-certs.sh
```
Stop the services with:
```bash
poetry run python ume_cli.py down
```
See [docs/SSL_SETUP.md](docs/SSL_SETUP.md) for details.

### 3. Run the Consumer Demo
```bash
poetry run python src/ume/consumer_demo.py
```
This script subscribes to topic `ume-clean-events` on `localhost:9092` and waits for messages.

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

### 6. Run the Test Suite
After installing dependencies, you can run the unit tests to verify everything works:
```bash
poetry run pytest
# or
PYTHONPATH=src pytest
```

### 7. Run the Agent Integration Example
This example shows how an AutoDev agent can send events to UME and forward them
to Culture.ai:
```bash
poetry run python examples/agent_integration.py
```

### 8. Start the Frontend Demo
The API now runs on `localhost:8000` via Docker Compose. Interact with it using
the web interface or the small CLI demo in `frontend/app.py`:

```bash
# open frontend/index.html in your browser (e.g. with `python -m http.server`)
poetry run python frontend/app.py --username ume --password password query "MATCH (n) RETURN n"
```
You can also search the vector store with either UI:

```bash
poetry run python frontend/app.py --username ume --password password search "1,0,0" --k 3
```

### 9. Integration Notebooks

Simple wrappers for [LangGraph](https://github.com/langchain-ai/langgraph) and
[Letta](https://github.com/stratusphd/letta) forward events to the UME API. They
are installed with the optional `integrations` extras:

```bash
pip install ume[integrations]
```

See [`examples/langgraph_integration.ipynb`](examples/langgraph_integration.ipynb)
and [`examples/letta_integration.ipynb`](examples/letta_integration.ipynb) for
usage.

### Building and Deploying the Frontend

The React dashboard in `frontend/` is fully static and does not require a build
step. Serve the files with any web server:

```bash
cd frontend
python -m http.server 8001
```

Visit `http://localhost:8001/` after starting the API to log in with your API
credentials. To deploy, copy the contents of `frontend/` to your preferred
static hosting service or configure your production web server to serve the
files alongside the FastAPI application.

### API Authentication

Obtain an OAuth2 token via the `/token` endpoint using the password grant:

```bash
curl -X POST -d "username=ume&password=password" http://localhost:8000/token
```

Include the returned access token in the `Authorization` header for subsequent
requests:

```http
Authorization: Bearer <token>
```
Tokens expire after `UME_OAUTH_TTL` seconds (default 3600).

The only unauthenticated route is `/metrics`, which exposes Prometheus metrics.
See [`docs/ENV_EXAMPLE.md`](docs/ENV_EXAMPLE.md) for a sample `.env` file.

### Posting Events

Events can be sent directly to the API using the `/events` endpoint. The JSON
body must follow the schema expected by `ume.parse_event`.

```bash
curl -X POST http://localhost:8000/events \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"event_type": "CREATE_NODE", "timestamp": 1, "node_id": "n1", "payload": {"node_id": "n1", "attributes": {"name": "demo"}}}'
```

The event is validated and immediately applied to the configured graph adapter.

### Recall Nodes
Use the `/recall` endpoint to retrieve the nearest nodes for a search query or
vector:

```bash
curl "http://localhost:8000/recall?query=demo&k=3" \
  -H "Authorization: Bearer <token>"
```

The API returns the matching node attributes ordered by similarity.

## Configuration Templates

Sample configuration files for common environments are provided in
[`docs/CONFIG_TEMPLATES.md`](docs/CONFIG_TEMPLATES.md). These templates
demonstrate how to select different storage backends or event stores for
development, staging, and production setups. The same document also lists
every environment variable understood by UME along with its default value.

### Runtime Settings

Configuration defaults live in [`src/ume/config.py`](src/ume/config.py). This
module exposes a `Settings` dataclass whose attributes correspond to the various
UME options. When imported it first loads a `.env` file from the project root if
present and then applies any matching environment variables, allowing you to
override the defaults without modifying the code.

See [`docs/ENV_EXAMPLE.md`](docs/ENV_EXAMPLE.md) for a minimal `.env` template.

## Federated Deployments

Running UME in multiple data centers may require synchronizing memory across
regions. Several strategies are summarized in
[`docs/FEDERATION.md`](docs/FEDERATION.md).

## Basic Usage

This section outlines the basic programmatic steps to interact with the UME components using an event-driven approach. Assumes project setup is complete and services (like Redpanda, if using network-based events) are running.

1.  **Obtain a Graph Adapter Instance:**
    Factory helpers simplify adapter creation. Use `create_graph_adapter()` to
    build the default adapter from environment settings. You can still
    instantiate specific adapters directly if needed:
    ```python
    from ume import create_graph_adapter, PersistentGraph, Neo4jGraph, IGraphAdapter

    # Default SQLite-backed adapter
    graph_adapter: IGraphAdapter = create_graph_adapter()

    # Or connect to Neo4j explicitly
    neo4j_graph = Neo4jGraph("bolt://localhost:7687", "neo4j", "password")
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
    The `PersistentGraph` persists automatically, but you can manually dump the graph to a JSON file:
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

    To automatically restore a previous snapshot and save updates at regular
    intervals, use:

    ```python
    from ume import enable_snapshot_autosave_and_restore

    enable_snapshot_autosave_and_restore(graph_adapter, "ume_snapshot.json")
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

### Swapping Backends
UME exposes small factory helpers that make it easy to change the storage
implementation without modifying other code.  To switch the graph adapter or
vector store used by the API, call the configuration functions:

```python
from ume import PersistentGraph, Neo4jGraph
from ume.api import configure_graph, configure_vector_store
from ume.vector_store import create_default_store

# SQLite graph
configure_graph(PersistentGraph("my.db"))
configure_vector_store(create_default_store())

# Later swap to Neo4j
configure_graph(Neo4jGraph("bolt://localhost:7687", "neo4j", "password"))
```

These helpers allow embedding applications to experiment with different
backends—such as Neo4j for production and the lightweight SQLite adapter for
local testing—without rewriting initialization code.

## How to Use UMEClient

`UMEClient` is a small helper for publishing events to the broker. It validates
the payload using UME's schemas before sending so your application only needs to
prepare a dictionary and handle any errors. Configuration values can be read
from :class:`ume.config.Settings` and overridden by environment variables at
runtime.

```python
from ume.config import Settings
from ume.client import UMEClient, UMEClientError
import time

# Create Settings (environment variables may override defaults)
settings = Settings()

# Connect to the broker and topic defined in Settings
with UMEClient(settings) as client:
    # Example event dictionary (CREATE_NODE)
    event = {
        "event_type": "CREATE_NODE",
        "timestamp": int(time.time()),
        "node_id": "demo_node",
        "payload": {"name": "Demo"},
        "source": "umeclient_example",
    }

    try:
        # Schema validation and Kafka publishing happen inside produce_event
        client.produce_event(event)
        print("Event produced successfully")
    except UMEClientError as e:
        print(f"Failed to produce event: {e}")
```

The client raises `UMEClientError` for issues such as failed validation or
broker communication errors so they can be handled cleanly.

## Command-Line Interface (v0.3.0-dev)

You can interact with UME via an interactive REPL (Read-Eval-Print Loop) command-line interface.

To start the CLI, run the console script installed by Poetry:
```bash
poetry run ume-cli
```
If you have installed UME into your environment, you can simply run `ume-cli`.
For development purposes you can still execute the module directly:
```bash
poetry run python ume_cli.py
```
You will see the prompt: `ume> `. Type `help` or `?` to list available commands, or `help <command>` for details on a specific command.

Pass `--show-warnings` to display Python warnings or `--warnings-log <file>` to
log them for debugging.

You can set `UME_CLI_DB` to override where the CLI stores its SQLite database.
If you define `UME_ROLE`, the CLI will run with that role's permissions and
display an informational message at startup.

### Available Commands

*   **`new_node <node_id> <json_attributes>`**: Create a new node.
    *   Example: `new_node user123 '{"name": "Alice", "email": "alice@example.com"}'`
*   **`new_edge <source_id> <target_id> <label>`**: Create a new directed edge between two existing nodes.
    *   Example: `new_edge user123 order456 PLACED_ORDER`
*   **`del_edge <source_id> <target_id> <label>`**: Delete an existing directed edge.
    *   Example: `del_edge user123 order456 PLACED_ORDER`
*   **`redact_node <node_id>`**: Mark a node as redacted so it no longer shows up in queries.
*   **`redact_edge <source_id> <target_id> <label>`**: Mark a specific edge as redacted.
*   **`show_nodes`**: List all node IDs currently in the graph.
*   **`show_edges`**: List all edges in the graph as `(source -> target) [label]`.
*   **`neighbors <node_id> [<label>]`**: List all target nodes that `<node_id>` connects to. Optionally filter by edge label.
    *   Example: `neighbors user123 PLACED_ORDER`
    *   Example: `neighbors user123`
*   **`snapshot_save <filepath>`**: Save the current graph state (nodes and edges) to the given JSON file.
    *   Example: `snapshot_save memory_backup.json`
*   **`snapshot_load <filepath>`**: Clear the current graph and load state from the given JSON file.
    *   Example: `snapshot_load memory_backup.json`
*   **`watch [path1,path2]`**: Start the dev-log watcher for the provided paths (defaults to `WATCH_PATHS`).
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
ume> redact_node alice
Node 'alice' redacted.
ume> show_nodes
Nodes:
  - bob
ume> exit
Goodbye!
```

## Graph Analytics with Neo4j GDS

When using `Neo4jGraph` with the `use_gds=True` option, UME can delegate graph
analytics to Neo4j's Graph Data Science (GDS) library. Functions in
`ume.analytics` such as `pagerank_centrality`, `betweenness_centrality`,
`find_communities`, `node_similarity`, `temporal_community_detection`, and
`time_varying_centrality` will execute the corresponding GDS procedures instead
of using NetworkX.

```python
from ume import Neo4jGraph
from ume.analytics import pagerank_centrality, time_varying_centrality

graph = Neo4jGraph("bolt://localhost:7687", "neo4j", "password", use_gds=True)
scores = pagerank_centrality(graph)
recent = time_varying_centrality(graph, past_n_days=7)
print(scores)
print(recent)
```

If GDS is not available or another adapter is used, these functions fall back to
`networkx` implementations.

### Graph Similarity

You can also measure how similar two graphs are using `graph_similarity`:

```python
from ume import Neo4jGraph
from ume.analytics import graph_similarity

g1 = Neo4jGraph("bolt://localhost:7687", "neo4j", "password", use_gds=True)
g2 = Neo4jGraph("bolt://localhost:7687", "neo4j", "password", use_gds=True)
score = graph_similarity(g1, g2)
print(score)
```

## Embedding Model

Text attributes can be converted to vector embeddings using a Sentence
Transformers model. Set `UME_EMBED_MODEL` to the desired Hugging Face
model name (defaults to `all-MiniLM-L6-v2`). Install the optional
dependencies with:

```bash
poetry install --with embedding
```

## Vector Store

UME can optionally maintain a FAISS index of node embeddings. Use
`create_vector_store()` to obtain a store configured from environment
variables. When a `CREATE_NODE` or `UPDATE_NODE_ATTRIBUTES` event contains an
`embedding` field in its attributes, the vector is added to the index via
`VectorStoreListener`.

Set the following environment variables to configure the store:

- `UME_VECTOR_DIM` – dimension of the embedding vectors (default `1536`).
- `UME_VECTOR_INDEX` – path of the FAISS index file.
- `UME_VECTOR_USE_GPU` – set to `true` to build the index on a GPU (requires
  FAISS compiled with GPU support).
- `UME_VECTOR_GPU_MEM_MB` – temporary memory (in MB) allocated for FAISS GPU
operations (default `256`). Increase or decrease this to tune GPU memory usage
when building the index.
  The same value can be passed to `VectorStore(gpu_mem_mb=...)` when
  constructing a store programmatically.

If the file specified by `UME_VECTOR_INDEX` exists, it is loaded automatically
when the store is created. New vectors are written back to this file whenever
they are added and when the store is closed.

Install GPU support with:

```bash
poetry install --with vector
```

See [Vector Store Benchmark](docs/VECTOR_BENCHMARKS.md) for sample GPU results.

## Logging

UME uses ``structlog`` for structured application logs. By default logs are
formatted for human readability. Set ``UME_LOG_JSON=1`` to output JSON lines and
``UME_LOG_LEVEL=DEBUG`` for verbose logging. These environment variables apply
to the CLI, API server and demo scripts.

## Where to Get Help

If you have questions, encounter issues, or want to discuss ideas related to UME, please feel free to:

*   **Open an Issue:** For bug reports, feature requests, or specific questions, please check the [GitHub Issues](https://github.com/d0tTino/universal-memory-engine/issues) page.
*   **Check our Contributing Guide:** For information on how to contribute to the project, see the [CONTRIBUTING.md](CONTRIBUTING.md) file.
*   **Be Mindful of Our Code of Conduct:** Please review our [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before participating.
