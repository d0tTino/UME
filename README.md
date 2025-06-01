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
- Python 3.9+
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

## Where to Get Help

If you have questions, encounter issues, or want to discuss ideas related to UME, please feel free to:

*   **Open an Issue:** For bug reports, feature requests, or specific questions, please check the [GitHub Issues](https://github.com/your-username/universal-memory-engine/issues) page (please replace `your-username/universal-memory-engine` with the actual repository path).
*   **Check our Contributing Guide:** For information on how to contribute to the project, see the [CONTRIBUTING.md](CONTRIBUTING.md) file.
