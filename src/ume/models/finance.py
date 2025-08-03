"""Finance transaction node model and factory helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import uuid

SCHEMA_VERSION = "1.0"


@dataclass
class Transaction:
    """Represents a financial transaction in the graph."""

    id: str
    amount: float
    currency: str = "USD"
    description: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    schema_version: str = SCHEMA_VERSION


def create_transaction(
    amount: float,
    *,
    currency: str = "USD",
    description: str | None = None,
    transaction_id: str | None = None,
    timestamp: datetime | None = None,
) -> Transaction:
    """Factory helper to build :class:`Transaction` instances."""

    return Transaction(
        id=transaction_id or str(uuid.uuid4()),
        amount=amount,
        currency=currency,
        description=description,
        timestamp=timestamp or datetime.utcnow(),
    )
