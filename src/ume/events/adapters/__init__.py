"""Transport-specific ingress adapters."""

from .cli import adapt_cli_payload
from .grpc import adapt_grpc_payload
from .kafka import adapt_kafka_payload

__all__ = ["adapt_cli_payload", "adapt_grpc_payload", "adapt_kafka_payload"]
