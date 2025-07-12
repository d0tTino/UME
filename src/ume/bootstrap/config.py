import importlib
import sys
import types
from types import SimpleNamespace

__all__ = ["load_config"]

def _make_stub(name: str) -> types.ModuleType:
    stub = types.ModuleType(name)
    return stub

def load_config(package: str) -> tuple[types.ModuleType, type]:
    """Load config module, returning (module, Settings class)."""
    try:
        config = importlib.import_module(".config", package)
        Settings = config.Settings
        setattr(sys.modules[package], "config", config)
    except Exception:  # pragma: no cover - fall back to stub on any failure
        stub = _make_stub(f"{package}.config")
        sys.modules[f"{package}.config"] = stub
        stub.settings = SimpleNamespace(  # type: ignore[attr-defined]
            UME_DB_PATH="ume_graph.db",
            UME_SNAPSHOT_PATH="ume_snapshot.json",
            UME_SNAPSHOT_DIR=".",
            UME_COLD_DB_PATH="ume_cold.db",
            UME_COLD_SNAPSHOT_PATH="ume_cold_snapshot.json",
            UME_COLD_EVENT_AGE_DAYS=180,
            UME_AUDIT_LOG_PATH="/tmp/audit.log",
            UME_AUDIT_SIGNING_KEY="stub",
            UME_CONSENT_LEDGER_PATH="consent_ledger.db",
            UME_EVENT_LEDGER_PATH="event_ledger.db",
            UME_FEEDBACK_DB_PATH="feedback.db",
            UME_AGENT_ID="SYSTEM",
            UME_EMBED_MODEL="all-MiniLM-L6-v2",
            UME_CLI_DB="ume_graph.db",
            UME_ROLE=None,
            UME_API_ROLE=None,
            UME_RATE_LIMIT_REDIS=None,
            UME_LOG_LEVEL="INFO",
            UME_LOG_JSON=False,
            UME_GRAPH_RETENTION_DAYS=30,
            UME_RELIABILITY_THRESHOLD=0.5,
            WATCH_PATHS=["."],
            DAG_RESOURCES={"cpu": 1, "io": 1},
            UME_VALUE_STORE_PATH=None,
            UME_VECTOR_BACKEND="faiss",
            UME_VECTOR_DIM=0,
            UME_VECTOR_INDEX="vectors.faiss",
            UME_VECTOR_USE_GPU=False,
            UME_VECTOR_GPU_MEM_MB=256,
            UME_VECTOR_MAX_AGE_DAYS=90,
            NEO4J_URI="bolt://localhost:7687",
            NEO4J_USER="neo4j",
            NEO4J_PASSWORD="password",  # pragma: allowlist secret
            KAFKA_BOOTSTRAP_SERVERS="localhost:9092",
            KAFKA_RAW_EVENTS_TOPIC="ume-raw-events",
            KAFKA_CLEAN_EVENTS_TOPIC="ume-clean-events",
            KAFKA_QUARANTINE_TOPIC="ume-quarantine-events",
            KAFKA_EDGE_TOPIC="ume_edges",
            KAFKA_NODE_TOPIC="ume_nodes",
            KAFKA_GROUP_ID="ume_client_group",
            KAFKA_PRIVACY_AGENT_GROUP_ID="ume-privacy-agent-group",
            KAFKA_PRODUCER_BATCH_SIZE=10,
            UME_OAUTH_USERNAME="ume",
            UME_OAUTH_PASSWORD="password",  # pragma: allowlist secret
            UME_OAUTH_ROLE="AnalyticsAgent",
            UME_OAUTH_TTL=3600,
            UME_API_TOKEN=None,
            OPA_URL=None,
            OPA_TOKEN=None,
            UME_OTLP_ENDPOINT=None,
            LLM_FERRY_API_URL="https://example.com/api",
            LLM_FERRY_API_KEY="",
            TWITTER_BEARER_TOKEN=None,
            ANGEL_BRIDGE_LOOKBACK_HOURS=24,
        )

        class _StubSettings:
            pass

        Settings = _StubSettings
        stub.Settings = _StubSettings  # type: ignore[attr-defined]
        config = stub
        setattr(sys.modules[package], "config", stub)
    return config, Settings
