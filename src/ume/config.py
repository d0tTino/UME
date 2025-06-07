from dataclasses import dataclass

@dataclass
class Settings:
    """Configuration options for UME components."""

    bootstrap_servers: str = "localhost:9092"
    topic: str = "ume_demo"
    group_id: str = "ume_client_group"

