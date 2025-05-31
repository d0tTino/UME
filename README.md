# universal-memory-engine
Event-sourced knowledge-graph memory bus for agents and automations (AKA UME).

UME (Universal Memory Engine) is designed to provide a robust, evolving memory for AI agents and automated systems. At its core, UME captures events from various sources and uses them to build and maintain a dynamic knowledge graph. This means that instead of static memory, agents can tap into a rich, interconnected web of information that reflects the history of their interactions and observations. This allows them to understand context, recall past experiences, and make more informed decisions.

The primary motivation behind UME is to equip AI agents with a form of persistent, long-term memory that can adapt over time. This capability is crucial for enabling more complex reasoning, facilitating nuanced inter-agent communication through shared contextual understanding, and ultimately, building more intelligent and autonomous systems. By structuring memory as an event-sourced knowledge graph, UME aims to offer a flexible and scalable solution for these challenges.

## Project Setup

This section provides instructions for setting up the development environment for the Universal Memory Engine (UME).

### Prerequisites

Before you begin, ensure you have the following installed:

*   **Python:** Version 3.12 or newer. This project uses Poetry, which will manage project-specific Python versions if configured, but a base Python installation is required.
*   **Poetry:** A Python dependency management and packaging tool. Installation instructions can be found at [https://python-poetry.org/docs/#installation](https://python-poetry.org/docs/#installation).
*   **Docker:** Docker Desktop (for Windows/macOS) or Docker Engine + Docker Compose (for Linux). This is required to run backend services like Redpanda. Download from [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/).

### Setup Steps

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    ```
    (Replace `<repository-url>` with the actual URL of this repository)

2.  **Navigate to the project directory:**
    ```bash
    cd universal-memory-engine
    ```

3.  **Install Python dependencies using Poetry:**
    ```bash
    poetry install
    ```
    This command reads the `pyproject.toml` file, which lists the project's dependencies. Poetry resolves these dependencies and installs them into a dedicated virtual environment, ensuring a consistent and isolated development setup.

4.  **Verify Docker Compose installation:**
    ```bash
    docker compose version
    ```
    This command checks if Docker Compose is installed and accessible. Docker Compose is used to manage multi-container Docker applications, including the services UME relies on.

5.  **Start the required services using Docker Compose:**
    ```bash
    docker compose -f docker/docker-compose.yml up -d
    ```
    This command starts the services defined in the `docker/docker-compose.yml` file in detached mode (`-d`), meaning they run in the background. The services started are:
    *   **Redpanda:** A Kafka-compatible event streaming platform used as the message broker.
    *   **Redpanda Console:** A web-based UI for managing and monitoring Redpanda, which also includes a Schema Registry.

6.  **(Optional) Quick Redpanda Test via Docker:**
    If you want to quickly test Redpanda without using Docker Compose, or if you only need Redpanda running, you can use the following Docker command:
    ```bash
    docker run -d --name=redpanda --rm \
        -p 9092:9092 -p 9644:9644 \
        docker.vectorized.io/vectorized/redpanda:latest \
        redpanda start
    ```
    This command downloads the latest Redpanda image (if not already present) and starts a Redpanda container named `redpanda`. It maps port `9092` for Kafka client connections and `9644` for the Redpanda admin API. The `--rm` flag ensures the container is removed when stopped. This is an alternative for running just Redpanda and is useful for quick tests or simpler setups.

## Quickstart

This section guides you through running a minimal demo to produce and consume an event using UME with Redpanda.

1.  **Start Redpanda and Services:**
    Ensure Docker is running. Navigate to the project root directory and start the Redpanda message broker and Redpanda Console (which includes a schema registry) using Docker Compose:
    ```bash
    docker compose -f docker/docker-compose.yml up -d
    ```
    This command reads the `docker/docker-compose.yml` file and starts the defined services in detached mode. You can check the status of the containers with `docker ps`.

2.  **Install Python Dependencies:**
    If you haven't already, install the necessary Python packages using Poetry:
    ```bash
    poetry install
    ```
    This command sets up a virtual environment and installs dependencies specified in `pyproject.toml`.

3.  **Run the Consumer:**
    Open a terminal window, navigate to the project root, and start the demo consumer script:
    ```bash
    poetry run python src/ume/consumer_demo.py
    ```
    The consumer will start, subscribe to the `ume_demo` topic, and wait for messages. You should see log output indicating it's waiting.

4.  **Run the Producer:**
    Open a *new* terminal window (keeping the consumer running), navigate to the project root, and run the demo producer script:
    ```bash
    poetry run python src/ume/producer_demo.py
    ```
    The producer will send a sample event to the `ume_demo` topic.

5.  **Observe the Output:**
    *   In the **producer's terminal**, you should see log messages indicating the event was produced and delivered successfully. For example:
        ```
        INFO:producer_demo:Producing event to topic 'ume_demo': {'type': 'demo_event', 'timestamp': ..., 'payload': {'message': 'Hello from producer_demo!'}}
        INFO:producer_demo:Message delivered to ume_demo [...] at offset ...
        ```
    *   In the **consumer's terminal**, you should see log messages indicating the event was received. For example:
        ```
        INFO:consumer_demo:Received event: {'type': 'demo_event', 'timestamp': ..., 'payload': {'message': 'Hello from producer_demo!'}}
        ```

This demonstrates a basic event flow through the system using the provided demo scripts and Redpanda. To stop the consumer, press `Ctrl+C` in its terminal. To stop the Redpanda services, run `docker compose -f docker/docker-compose.yml down`.

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

## Where to Get Help

If you have questions, encounter issues, or want to discuss ideas related to UME, please feel free to:

*   **Open an Issue:** For bug reports, feature requests, or specific questions, please check the [GitHub Issues](https://github.com/your-username/universal-memory-engine/issues) page (please replace `your-username/universal-memory-engine` with the actual repository path).
*   **Check our Contributing Guide:** For information on how to contribute to the project, see the [CONTRIBUTING.md](CONTRIBUTING.md) file.
