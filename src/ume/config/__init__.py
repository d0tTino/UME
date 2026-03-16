import logging
import os
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_AUDIT_SIGNING_KEY = "default-key"


class Settings(BaseSettings):  # type: ignore[misc]
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # UME Core
    UME_ENV: str = "development"
    UME_DB_PATH: str = "ume_graph.db"
    UME_GRAPH_BACKEND: str = "sqlite"  # sqlite, postgres, redis, or neo4j
    UME_GRAPH_ADAPTER_MODULES: str | None = None
    UME_SNAPSHOT_PATH: str = "ume_snapshot.json"
    UME_SNAPSHOT_DIR: str = "."
    UME_COLD_DB_PATH: str = "ume_cold.db"
    UME_COLD_SNAPSHOT_PATH: str = "ume_cold_snapshot.json"
    UME_COLD_EVENT_AGE_DAYS: int = 180
    UME_AUDIT_LOG_PATH: str = "audit.log"
    UME_AUDIT_SIGNING_KEY: str = DEFAULT_AUDIT_SIGNING_KEY
    UME_ENCRYPTION_ENABLED: bool = False
    UME_ENCRYPTION_KEY: str | None = None
    UME_CONSENT_LEDGER_PATH: str = "consent_ledger.db"
    UME_EVENT_LEDGER_PATH: str = "event_ledger.db"
    UME_FEEDBACK_DB_PATH: str = "feedback.db"
    UME_AGENT_ID: str = "SYSTEM"
    UME_EMBED_MODEL: str = "all-MiniLM-L6-v2"
    UME_CLI_DB: str = "ume_graph.db"
    UME_DOSSIER_PATH: str = "~/.ume_dossier"
    UME_ROLE: str | None = None
    UME_API_ROLE: str | None = None
    UME_RATE_LIMIT_REDIS: str | None = None
    UME_LOG_LEVEL: str = "INFO"
    UME_LOG_JSON: bool = False
    UME_GRAPH_RETENTION_DAYS: int = 30
    UME_LEDGER_OFFSET_WINDOW: int = 1000
    UME_LEDGER_COMPACTION_INTERVAL: float = 24 * 3600
    UME_RELIABILITY_THRESHOLD: float = 0.5
    WATCH_PATHS: list[str] = ["."]
    DAG_RESOURCES: dict[str, int] = {"cpu": 1, "io": 1}
    UME_VALUE_STORE_PATH: str | None = None
    UME_ENABLE_DASHBOARD_STREAM: bool = True
    UME_DASHBOARD_STREAM_TRANSPORT: str = "sse"
    UME_DASHBOARD_REST_FALLBACK: bool = True

    # Vector store
    UME_VECTOR_BACKEND: str = "faiss"  # faiss, chroma, or plugin name
    UME_VECTOR_DIM: int = 2
    UME_VECTOR_INDEX: str = "vectors.faiss"
    UME_VECTOR_USE_GPU: bool = False
    UME_VECTOR_GPU_MEM_MB: int = 256
    UME_VECTOR_MAX_AGE_DAYS: int = 90
    UME_MILVUS_URI: str = "http://localhost:19530"
    UME_MILVUS_USER: str | None = None
    UME_MILVUS_PASSWORD: str | None = None
    UME_PINECONE_API_KEY: str | None = None
    UME_PINECONE_ENVIRONMENT: str | None = None
    UME_PINECONE_INDEX: str = "ume-vectors"

    # ArangoDB connection
    ARANGO_URL: str = "http://localhost:8529"
    ARANGO_USER: str = "root"
    ARANGO_PASSWORD: str = "password"
    ARANGO_DB_NAME: str = "ume"

    # Neo4j connection for optional gRPC server
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # Kafka/Redpanda
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_SECURITY_PROTOCOL: str = "PLAINTEXT"
    KAFKA_SASL_MECHANISM: str | None = None
    KAFKA_SASL_USERNAME: str | None = None
    KAFKA_SASL_PASSWORD: str | None = None
    KAFKA_CA_CERT: str | None = None
    KAFKA_CLIENT_CERT: str | None = None
    KAFKA_CLIENT_KEY: str | None = None
    KAFKA_RAW_EVENTS_TOPIC: str = "ume-raw-events"
    KAFKA_CLEAN_EVENTS_TOPIC: str = "ume-clean-events"
    KAFKA_QUARANTINE_TOPIC: str = "ume-quarantine-events"
    KAFKA_EDGE_TOPIC: str = "ume_edges"
    KAFKA_NODE_TOPIC: str = "ume_nodes"
    KAFKA_ROUTING_FALLBACK_TOPIC: str = "ume-misc-events"
    KAFKA_ROUTING_DEAD_LETTER_TOPIC: str = "ume-dead-letter-events"
    KAFKA_GROUP_ID: str = "ume_client_group"
    KAFKA_PRIVACY_AGENT_GROUP_ID: str = "ume-privacy-agent-group"
    # Number of messages to batch before calling `Producer.flush()` in the privacy agent
    KAFKA_PRODUCER_BATCH_SIZE: int = 10

    # API authentication (OAuth2 Password grant)
    UME_OAUTH_USERNAME: str = "ume"
    UME_OAUTH_PASSWORD: str = "password"
    UME_OAUTH_ROLE: str = "AnalyticsAgent"
    UME_OAUTH_TTL: int = 3600

    # API token used for test clients and simple auth
    UME_API_TOKEN: str | None = None
    UME_INGEST_LENIENT_VALIDATION: bool = False

    # gRPC authentication token
    UME_GRPC_TOKEN: str | None = None

    # Remote OPA configuration
    OPA_URL: str | None = None
    OPA_TOKEN: str | None = None

    REGO_POLICY_PATHS: str | None = None
    UME_POLICY_GRAPH_MAX_SNAPSHOT_NODES: int = 500
    UME_POLICY_GRAPH_NEIGHBORHOOD_DEPTH: int = 1
    UME_POLICY_GRAPH_MAX_NEIGHBORHOOD_NODES: int = 200

    # OpenTelemetry
    UME_OTLP_ENDPOINT: str | None = None

    # LLM Ferry
    LLM_FERRY_API_URL: str = "https://example.com/api"
    LLM_FERRY_API_KEY: str = ""

    # Tweet bot
    TWITTER_BEARER_TOKEN: str | None = None

    # Finance engine
    FINANCE_ENGINE_URL: str = "http://finance-engine:8000"

    # Tino-storm classifier
    TINO_STORM_URL: str | None = None
    TINO_STORM_LOCAL_MODEL: str | None = None

    # Angel Bridge
    ANGEL_BRIDGE_LOOKBACK_HOURS: int = 24

    def model_post_init(self, __context: Any) -> None:  # noqa: D401
        """Validate settings after initialization."""
        logger = logging.getLogger(__name__)
        self.apply_secret_file_overrides()

        errors: list[str] = []
        warnings: list[str] = []
        dev_mode = self.UME_ENV.lower() in {"dev", "development", "test"}

        if self.UME_AUDIT_SIGNING_KEY == DEFAULT_AUDIT_SIGNING_KEY:
            msg = "UME_AUDIT_SIGNING_KEY must be set to a non-default value"
            if dev_mode:
                warnings.append(msg)
            else:
                errors.append(msg)

        if not self.UME_API_TOKEN:
            msg = "UME_API_TOKEN is required for non-development deployments"
            if dev_mode:
                warnings.append(msg)
            else:
                errors.append(msg)

        if self.UME_OAUTH_PASSWORD == "password":
            msg = "UME_OAUTH_PASSWORD must not use the default value"
            if dev_mode:
                warnings.append(msg)
            else:
                errors.append(msg)

        protocol = self.KAFKA_SECURITY_PROTOCOL.upper()
        if protocol in {"SSL", "SASL_SSL"}:
            if not self.KAFKA_CA_CERT:
                errors.append("KAFKA_CA_CERT is required when Kafka TLS is enabled")
            if protocol == "SSL" and (not self.KAFKA_CLIENT_CERT or not self.KAFKA_CLIENT_KEY):
                errors.append(
                    "KAFKA_CLIENT_CERT and KAFKA_CLIENT_KEY are required for KAFKA_SECURITY_PROTOCOL=SSL"
                )

        if protocol in {"SASL_SSL", "SASL_PLAINTEXT"} and (
            not self.KAFKA_SASL_USERNAME or not self.KAFKA_SASL_PASSWORD
        ):
            errors.append(
                "KAFKA_SASL_USERNAME and KAFKA_SASL_PASSWORD are required for SASL Kafka protocols"
            )

        for msg in warnings:
            logger.warning(msg)
        if errors:
            raise ValueError("; ".join(errors))

    def apply_secret_file_overrides(self) -> None:
        file_mappings = {
            "UME_AUDIT_SIGNING_KEY_FILE": "UME_AUDIT_SIGNING_KEY",
            "UME_ENCRYPTION_KEY_FILE": "UME_ENCRYPTION_KEY",
            "UME_OAUTH_PASSWORD_FILE": "UME_OAUTH_PASSWORD",
            "UME_API_TOKEN_FILE": "UME_API_TOKEN",
            "NEO4J_PASSWORD_FILE": "NEO4J_PASSWORD",
            "KAFKA_SASL_PASSWORD_FILE": "KAFKA_SASL_PASSWORD",
        }
        for file_env, target in file_mappings.items():
            path = os.environ.get(file_env)
            if not path:
                continue
            try:
                value = open(path, "r", encoding="utf-8").read().strip()
            except OSError as exc:
                raise ValueError(f"Failed to read secret file {file_env}: {exc}") from exc
            object.__setattr__(self, target, value)

from .loader import load_settings  # noqa: E402
load_settings.cache_clear()

# Create a single, importable instance
settings = load_settings()

__all__ = ["Settings", "settings", "load_settings", "DEFAULT_AUDIT_SIGNING_KEY"]
