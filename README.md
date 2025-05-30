# universal-memory-engine
Event-sourced knowledge-graph memory bus for agents and automations (AKA UME).

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
