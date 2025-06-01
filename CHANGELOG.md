# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (though currently in pre-release/development phase).

## [0.1.0-dev] - 2023-10-27

### Added

-   **Core Event Handling:**
    -   `Event` dataclass for structured event representation (`src/ume/event.py`).
    -   `parse_event` function for validating and parsing raw event data into `Event` objects.
    -   `EventError` custom exception for event parsing issues.
-   **Graph Abstraction Layer:**
    -   `IGraphAdapter` interface defining standard graph operations (`src/ume/graph_adapter.py`).
    -   `MockGraph` implementation of `IGraphAdapter` for in-memory graph representation and testing (`src/ume/graph.py`). Includes methods like `add_node`, `update_node`, `get_node`, `node_exists`, `clear`, `dump`.
-   **Event Processing Logic:**
    -   `apply_event_to_graph` function to apply parsed `Event` objects to an `IGraphAdapter` instance (`src/ume/processing.py`).
    -   Initial support for `CREATE_NODE` and `UPDATE_NODE_ATTRIBUTES` event types.
    *   `ProcessingError` custom exception for event application issues.
-   **Snapshotting:**
    -   `MockGraph.dump()` method to export graph state (nodes only currently).
    -   `snapshot_graph_to_file` function to save graph dump to a JSON file (`src/ume/snapshot.py`).
-   **Testing Framework:**
    -   Setup `pytest` and `pytest-cov` for unit testing and coverage.
    -   Comprehensive unit tests for:
        -   Event parsing (`tests/test_event.py`).
        -   `MockGraph` implementation of `IGraphAdapter` (`tests/test_graph.py`).
        -   Event processing logic (`tests/test_processing.py`).
        -   Graph serialization and snapshotting (`tests/test_graph_serialization.py`).
-   **CI Workflow:**
    -   GitHub Actions CI pipeline (`.github/workflows/ci.yml`) for automated testing, linting (Ruff), formatting checks (Ruff), and coverage reporting on pushes/PRs to main.
-   **Documentation:**
    -   Comprehensive `README.md` with sections for Overview, Project Setup, Quickstart, Basic Usage, Architecture, Graph Model (planned), Testing, and Where to Get Help.
    -   Detailed docstrings for all core modules, public classes, and functions.
    -   `CONTRIBUTING.md` guide.
-   **Project Setup:**
    -   `pyproject.toml` configured for Poetry, with dependencies (e.g., `confluent-kafka`) and dev dependencies (e.g., `pytest`, `pytest-cov`, `ruff`).
    -   Demo scripts (`producer_demo.py`, `consumer_demo.py`) for basic Kafka interaction (though full execution was limited by environment).

### Changed

-   Refactored `MockGraph` to strictly implement `IGraphAdapter` (distinct `add_node` and `update_node` methods).
-   Refactored `apply_event_to_graph` to operate on the `IGraphAdapter` interface, decoupling it from `MockGraph`.
-   Improved validation logic in `apply_event_to_graph` for event payloads.
-   Consolidated and parametrized unit tests for better maintainability.

### Known Issues / Limitations (as of this version)

-   Full end-to-end testing of demo scripts involving Kafka/Redpanda was blocked by environmental issues preventing `confluent-kafka` installation in the test execution environment. Unit tests for core logic are passing.
-   `MockGraph` currently only handles nodes; edge representation and processing are future work.
-   Graph persistence is limited to manual snapshotting of `MockGraph` to a file; no automated persistence or database backend yet.

```
