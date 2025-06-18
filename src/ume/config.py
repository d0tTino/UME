from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Extra


class Settings(BaseSettings):
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

    # Vector store
    UME_VECTOR_DIM: int = 1536
    UME_VECTOR_INDEX: str = "vectors.faiss"
    UME_VECTOR_USE_GPU: bool = False
    UME_VECTOR_GPU_MEM_MB: int = 256

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

    # API
    UME_API_TOKEN: str = "secret-token"

    # LLM Ferry
    LLM_FERRY_API_URL: str = "https://example.com/api"
    LLM_FERRY_API_KEY: str = ""


# Create a single, importable instance
settings = Settings()
