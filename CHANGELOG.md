# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (though currently in pre-release/development phase).

## [0.3.0-dev] - 2023-10-27

### Added

-   **Command-Line Interface (`ume_cli.py`):**
    -   Added an interactive REPL/CLI script (`ume_cli.py`) in the project root for interacting with the UME.
    -   Uses Python's `cmd` module for the command loop.
    -   Initializes and uses an in-memory `MockGraph` instance.
    -   Provides commands for:
        -   Node management: `new_node <node_id> <json_attributes>`
        -   Edge management: `new_edge <src> <tgt> <lbl>`, `del_edge <src> <tgt> <lbl>`
        -   Graph queries: `show_nodes`, `show_edges`, `neighbors <node_id> [<lbl>]`
        -   Snapshotting: `snapshot_save <path>`, `snapshot_load <path>`
        -   Utility: `clear` (graph), `exit`, `quit`, `help`
    -   Graph mutations via the CLI are event-sourced (using `parse_event` and `apply_event_to_graph`).
    -   Includes error handling for UME exceptions and user input.
-   **CLI Smoke Tests (`tests/test_cli_smoke.py`):**
    -   Added basic smoke tests for `ume_cli.py` using `subprocess` to verify:
        -   CLI startup and basic commands (`exit`, `help`).
        -   Node creation and listing (`new_node`, `show_nodes`).
        -   Edge creation and listing (`new_edge`, `show_edges`).
        -   Snapshot save and load functionality.
        -   Handling of unknown commands.
-   **Documentation:**
    -   `README.md`: Added a new "Command-Line Interface (v0.3.0-dev)" section with usage instructions, command overview, and an example session.

### Changed

*(No specific changes to existing features noted for this version yet, primarily new additions)*

### Fixed

-   *(No specific bug fixes noted for this version yet, primarily new features)*

## [0.2.0-dev] - 2023-10-27

### Added

-   **Event-Driven Edge Management:**
    -   `Event` dataclass (`src/ume/event.py`): Extended to support edge operations by making `node_id` optional and adding optional `target_node_id` and `label` fields.
    -   `parse_event()`: Updated to validate new event types "CREATE_EDGE" and "DELETE_EDGE", ensuring required fields (`node_id` as source, `target_node_id`, `label`) are present and correctly typed.
    -   `IGraphAdapter` (`src/ume/graph_adapter.py`): Added `delete_edge()` abstract method.
    -   `MockGraph` (`src/ume/graph.py`): Implemented `delete_edge()` method.
    -   `apply_event_to_graph()` (`src/ume/processing.py`): Extended to handle "CREATE_EDGE" and "DELETE_EDGE" events, calling the appropriate `IGraphAdapter` methods (`add_edge`, `delete_edge`).
-   **Testing:**
    -   Added unit tests in `tests/test_event.py` for parsing "CREATE_EDGE" and "DELETE_EDGE" event types, including valid and invalid cases.
    -   Added unit tests in `tests/test_processing.py` for `apply_event_to_graph` processing of "CREATE_EDGE" and "DELETE_EDGE" events (success and error propagation from adapter).
    -   Added unit tests in `tests/test_graph.py` for `MockGraph.delete_edge()` method (success and error cases).
-   **Documentation:**
    *   `README.md`:
        *   "Event Schema" section updated with JSON examples and descriptions for "CREATE_EDGE" and "DELETE_EDGE" events.
        *   "Basic Usage" section refactored to demonstrate an event-centric approach for creating nodes and edges via `apply_event_to_graph(parse_event(...))`. Query and dump examples updated to reflect edge presence.

### Changed

-   The `node_id` field in the `Event` dataclass is now `Optional[str]` (was `str`), with `parse_event` enforcing its presence for specific event types.
-   `apply_event_to_graph()` now includes defensive checks for string types of IDs and labels for new edge events before calling adapter methods.

### Fixed

-   *(No specific bug fixes noted for this version yet, primarily new features)*

## [0.1.0-dev] - 2023-10-27

### Added

-   **Core Event Handling:**
    -   `Event` dataclass for structured event representation (`src/ume/event.py`).
    -   `parse_event` function for validating and parsing raw event data into `Event` objects.
    -   `EventError` custom exception for event parsing issues.
-   **Graph Abstraction Layer:**
    -   `IGraphAdapter` interface defining standard graph operations (`src/ume/graph_adapter.py`), including query methods (`get_all_node_ids()`, `find_connected_nodes()`) and new edge management methods (`add_edge()`, `get_all_edges()`).
    -   `MockGraph` implementation of `IGraphAdapter` for in-memory graph representation and testing (`src/ume/graph.py`). Includes methods for node manipulation, queries, and new implementations for `add_edge()` and `get_all_edges()`.
-   **Event Processing Logic:**
    -   `apply_event_to_graph` function to apply parsed `Event` objects to an `IGraphAdapter` instance (`src/ume/processing.py`).
    -   Initial support for `CREATE_NODE` and `UPDATE_NODE_ATTRIBUTES` event types.
    *   `ProcessingError` custom exception for event application issues.
-   **Snapshotting:**
    -   `MockGraph.dump()` method to export graph state (nodes only currently).
    -   `snapshot_graph_to_file` function to save graph dump to a JSON file (`src/ume/snapshot.py`).
    -   `load_graph_from_file` function to restore graph state from a JSON snapshot (`src/ume/snapshot.py`).
    -   `SnapshotError` custom exception for snapshot loading issues.
-   **Testing Framework:**
    -   Setup `pytest` and `pytest-cov` for unit testing and coverage.
    -   Comprehensive unit tests for:
        -   Event parsing (`tests/test_event.py`).
        -   `MockGraph` implementation of `IGraphAdapter` (`tests/test_graph.py`), including new query and edge methods (`add_edge`, `get_all_edges`, updated `find_connected_nodes`, `clear`).
        -   Event processing logic (`tests/test_processing.py`).
        -   Graph serialization and snapshotting (`tests/test_graph_serialization.py`), including `load_graph_from_file` tests and handling of edges in snapshots.
-   **CI Workflow:**
    -   GitHub Actions CI pipeline (`.github/workflows/ci.yml`) for automated testing, linting (Ruff), formatting checks (Ruff), and coverage reporting on pushes/PRs to main.
-   **Documentation:**
    -   Comprehensive `README.md`: Updated "UME Graph Model" and "Basic Usage" sections to reflect edge support, including examples for `add_edge`, `find_connected_nodes` with edges, and snapshot examples showing edge data.
    -   Detailed docstrings for all core modules, public classes, and functions (reviewed and updated).
    -   `CONTRIBUTING.md` guide.
-   **Project Setup:**
    -   `pyproject.toml` configured for Poetry, with dependencies (e.g., `confluent-kafka`) and dev dependencies (e.g., `pytest`, `pytest-cov`, `ruff`).
    -   Demo scripts (`producer_demo.py`, `consumer_demo.py`) for basic Kafka interaction (though full execution was limited by environment).

### Changed

-   Refactored `MockGraph` to strictly implement `IGraphAdapter` (distinct `add_node` and `update_node` methods).
-   Refactored `apply_event_to_graph` to operate on the `IGraphAdapter` interface, decoupling it from `MockGraph`.
-   Improved validation logic in `apply_event_to_graph` for event payloads.
-   Consolidated and parametrized unit tests for better maintainability.
-   **`MockGraph` Updates for Edge Support:**
    -   `find_connected_nodes()` method now uses the internal edge list to find actual connections.
    -   `dump()` method now includes an "edges" list in its output.
    -   `clear()` method now also clears stored edges.
-   **Snapshotting (`src/ume/snapshot.py`):**
    -   `load_graph_from_file()` function updated to load and validate edge data from snapshots if present.

### Known Issues / Limitations (as of this version)

-   Full end-to-end testing of demo scripts involving Kafka/Redpanda was blocked by environmental issues preventing `confluent-kafka` installation in the test execution environment. Unit tests for core logic are passing.
-   `MockGraph` now includes basic support for directed, labeled edges (storage, retrieval, and inclusion in snapshots). Advanced edge querying or property support is future work.
-   Graph persistence is limited to manual snapshotting of `MockGraph` to a file; no automated persistence or database backend yet.

```
