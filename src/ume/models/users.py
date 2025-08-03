"""User node model and factory helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import uuid

SCHEMA_VERSION = "1.0"


@dataclass
class User:
    """Represents a user in the graph."""

    id: str
    name: str
    email: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    schema_version: str = SCHEMA_VERSION


def create_user(
    name: str,
    email: str | None = None,
    *,
    user_id: str | None = None,
    created_at: datetime | None = None,
) -> User:
    """Factory helper to build :class:`User` instances."""

    return User(
        id=user_id or str(uuid.uuid4()),
        name=name,
        email=email,
        created_at=created_at or datetime.utcnow(),
    )
