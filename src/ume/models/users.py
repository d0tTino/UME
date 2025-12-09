"""User node model and factory helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import uuid

from ..graph_schema import get_default_node_version

# Keep in sync with the default ``schema_version`` on :class:`User`.
SCHEMA_VERSION = get_default_node_version("User")


@dataclass
class User:
    """Represents a user in the graph."""

    user_id: str
    name: str
    email: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    schema_version: str = field(default=SCHEMA_VERSION)

    @property
    def id(self) -> str:  # pragma: no cover - compatibility layer
        """Backward compatible alias for ``user_id``."""
        return self.user_id

    @id.setter
    def id(self, value: str) -> None:  # pragma: no cover - compatibility layer
        self.user_id = value


def create_user(
    name: str,
    email: str | None = None,
    *,
    user_id: str | None = None,
    created_at: datetime | None = None,
) -> User:
    """Factory helper to build :class:`User` instances."""

    return User(
        user_id=user_id or str(uuid.uuid4()),
        name=name,
        email=email,
        created_at=created_at or datetime.utcnow(),
    )
