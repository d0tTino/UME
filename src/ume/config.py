from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # UME Core
    UME_DB_PATH: str = "ume_graph.db"
    UME_SNAPSHOT_PATH: str = "ume_snapshot.json"
    UME_AUDIT_LOG_PATH: str = "audit.log"
    UME_AUDIT_SIGNING_KEY: str = "default-key"
    UME_AGENT_ID: str = "SYSTEM"

    # Kafka/Redpanda
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_IN_TOPIC: str = "ume_demo"
    KAFKA_EDGE_TOPIC: str = "ume_edges"
    KAFKA_NODE_TOPIC: str = "ume_nodes"
    KAFKA_GROUP_ID: str = "ume_client_group"

    # API
    UME_API_TOKEN: str = "secret-token"

# Create a single, importable instance
settings = Settings()

