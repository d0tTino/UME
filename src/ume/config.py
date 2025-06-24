from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Extra
from typing import Any


class Settings(BaseSettings):  # type: ignore[misc]
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra=Extra.ignore
    )

    # UME Core
    UME_DB_PATH: str = "ume_graph.db"
    UME_SNAPSHOT_PATH: str = "ume_snapshot.json"
    UME_AUDIT_LOG_PATH: str = "audit.log"
    UME_AUDIT_SIGNING_KEY: str = "default-key"
    UME_AGENT_ID: str = "SYSTEM"
    UME_EMBED_MODEL: str = "all-MiniLM-L6-v2"
    UME_CLI_DB: str = "ume_graph.db"
    UME_ROLE: str | None = None
    UME_API_ROLE: str | None = None
    UME_LOG_LEVEL: str = "INFO"
    UME_LOG_JSON: bool = False
    UME_GRAPH_RETENTION_DAYS: int = 30
    UME_RELIABILITY_THRESHOLD: float = 0.5
    WATCH_PATHS: list[str] = ["."]
    DAG_RESOURCES: dict[str, int] = {"cpu": 1, "io": 1}
    UME_RELIABILITY_THRESHOLD: float = 0.5

    # Vector store
    UME_VECTOR_DIM: int = 1536
    UME_VECTOR_INDEX: str = "vectors.faiss"
    UME_VECTOR_USE_GPU: bool = False
    UME_VECTOR_GPU_MEM_MB: int = 256

    # Neo4j connection for optional gRPC server
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # Kafka/Redpanda
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_RAW_EVENTS_TOPIC: str = "ume-raw-events"
    KAFKA_CLEAN_EVENTS_TOPIC: str = "ume-clean-events"
    KAFKA_QUARANTINE_TOPIC: str = "ume-quarantine-events"
    KAFKA_EDGE_TOPIC: str = "ume_edges"
    KAFKA_NODE_TOPIC: str = "ume_nodes"
    KAFKA_GROUP_ID: str = "ume_client_group"
    KAFKA_PRIVACY_AGENT_GROUP_ID: str = "ume-privacy-agent-group"
    # Number of messages to batch before calling `Producer.flush()` in the privacy agent
    KAFKA_PRODUCER_BATCH_SIZE: int = 10

    # API authentication (OAuth2 Password grant)
    UME_OAUTH_USERNAME: str = "ume"
    UME_OAUTH_PASSWORD: str = "password"
    UME_OAUTH_ROLE: str = "AnalyticsAgent"
    UME_OAUTH_TTL: int = 3600
    UME_API_TOKEN: str = "test-token"

    # API token used for test clients and simple auth
    UME_API_TOKEN: str = "secret-token"

    # LLM Ferry
    LLM_FERRY_API_URL: str = "https://example.com/api"
    LLM_FERRY_API_KEY: str = ""

    # Alignment / policy configuration
    OPA_URL: str | None = None
    REGO_POLICY_PATHS: list[str] | None = None
    OPA_TOKEN: str | None = None

    def model_post_init(self, __context: Any) -> None:  # noqa: D401
        """Validate settings after initialization."""
        if self.UME_AUDIT_SIGNING_KEY == "default-key":
            raise ValueError(
                "UME_AUDIT_SIGNING_KEY must be set to a non-default value"
            )

# Create a single, importable instance
settings = Settings()
