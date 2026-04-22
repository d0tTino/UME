from typing import Any, Dict
import os

from fastapi import HTTPException

from .kernel.graph_adapter import IGraphAdapter
from .events.contract import canonicalize_event, canonical_to_camel_dict, canonical_to_legacy_dict


def ssl_config() -> Dict[str, str]:
    """Return Kafka SSL configuration if cert env vars are set."""
    ca = os.environ.get("KAFKA_CA_CERT")
    cert = os.environ.get("KAFKA_CLIENT_CERT")
    key = os.environ.get("KAFKA_CLIENT_KEY")
    if ca and cert and key:
        return {
            "security.protocol": "SSL",
            "ssl.ca.location": ca,
            "ssl.certificate.location": cert,
            "ssl.key.location": key,
        }
    return {}


def ensure_group_member(
    graph: IGraphAdapter, user_id: str, group_id: str, *, should_exist: bool = True
) -> None:
    """Validate membership of ``user_id`` in ``group_id``.

    Parameters
    ----------
    graph:
        Graph adapter used to fetch group information.
    user_id:
        The user identifier whose membership is being validated.
    group_id:
        The group identifier to check against.
    should_exist:
        If ``True`` (default), ensure the user is already a member of the
        group, raising ``HTTPException`` with status 403 if not. If ``False``,
        ensure the user is **not** a member, raising ``HTTPException`` with
        status 400 if they already belong to the group.
    """

    group = graph.get_node(group_id)
    if not isinstance(group, dict):
        raise HTTPException(status_code=404, detail="Group not found")

    members = group.get("members", [])
    if should_exist:
        if user_id not in members:
            raise HTTPException(status_code=403, detail="User not in group")
    else:
        if user_id in members:
            raise HTTPException(status_code=400, detail="User already in group")


# ----------------------------------------------------------------------------
# Event field conversion helpers



def event_to_snake(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a flat snake_case event dictionary."""
    return canonical_to_legacy_dict(canonicalize_event(data))


def event_to_camel(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a flat camelCase event dictionary."""
    return canonical_to_camel_dict(canonicalize_event(data))
