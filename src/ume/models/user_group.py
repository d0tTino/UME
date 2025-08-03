"""User group node model and factory helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
import uuid


@dataclass
class UserGroup:
    """Represents a group of users."""

    group_id: str
    name: str
    members: list[str] = field(default_factory=list)


def create_user_group(
    name: str,
    members: list[str] | None = None,
    *,
    group_id: str | None = None,
) -> UserGroup:
    """Factory helper to build :class:`UserGroup` instances."""

    return UserGroup(
        group_id=group_id or str(uuid.uuid4()),
        name=name,
        members=members or [],
    )
