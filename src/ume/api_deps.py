"""Shared FastAPI dependency functions used across routers."""

from __future__ import annotations

import logging
import time
import threading
import inspect
from pathlib import Path
from typing import Dict, Any

from fastapi import Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer

from .config import settings
from .rbac_adapter import RoleBasedGraphAdapter
from .graph_adapter import IGraphAdapter
from .async_graph_adapter import IAsyncGraphAdapter
from .query import Neo4jQueryEngine
from . import VectorStore
from .permissions_adapter import PermissionsGraphAdapter


logger = logging.getLogger(__name__)

# Directory containing local Rego policy files
POLICY_DIR = Path(__file__).with_name("plugins") / "alignment" / "policies"

# OAuth2 configuration and issued tokens
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")
TOKENS: Dict[str, tuple[str, float]] = {}
TOKENS_LOCK = threading.Lock()


def configure_graph(graph: IGraphAdapter | None = None) -> None:
    """Create and register the API's graph adapter."""
    from .api import app  # Local import to avoid circular dependency

    if graph is None:
        from .factories import create_graph_adapter

        graph = create_graph_adapter()

    role = settings.UME_API_ROLE
    if role:
        graph = RoleBasedGraphAdapter(graph, role=role)
        # Ensure tokens issued after configuration use the same role so that
        # access checks remain consistent. This is helpful in tests that set
        # ``UME_API_ROLE`` without adjusting the OAuth role.
        object.__setattr__(settings, "UME_OAUTH_ROLE", role)
        # Reset the global API role after wrapping so later calls start from a
        # clean slate.
        object.__setattr__(settings, "UME_API_ROLE", None)
    app.state.graph = graph
    if settings.UME_API_TOKEN:
        expires_at = time.time() + settings.UME_OAUTH_TTL
        with TOKENS_LOCK:
            TOKENS[settings.UME_API_TOKEN] = (
                settings.UME_OAUTH_ROLE,
                expires_at,
            )


def configure_vector_store(store: VectorStore) -> None:
    """Inject a :class:`VectorStore` instance into the application state."""
    from .api import app  # Local import to avoid circular dependency

    existing = getattr(app.state, "vector_store", None)
    if existing is not None and hasattr(existing, "close"):
        try:
            existing.close()
        except Exception as exc:  # pragma: no cover - unexpected failure
            logger.exception("Failed to close existing vector store", exc_info=exc)
    app.state.vector_store = store


def remove_expired_tokens() -> None:
    """Delete tokens from ``TOKENS`` that have expired."""
    now = time.time()
    with TOKENS_LOCK:
        expired = [tok for tok, (_, exp) in TOKENS.items() if exp < now]
        for tok in expired:
            TOKENS.pop(tok, None)


def get_current_role(token: str = Depends(oauth2_scheme)) -> str:
    if token == settings.UME_API_TOKEN:
        return settings.UME_API_ROLE or ""
    with TOKENS_LOCK:
        entry = TOKENS.get(token)
        if entry is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        role, expiry = entry
        if expiry < time.time():
            TOKENS.pop(token, None)
            raise HTTPException(status_code=401, detail="Token expired")
        return role


def require_token(_: str = Depends(oauth2_scheme)) -> None:
    """Dependency ensuring a bearer token is provided."""
    return None


def get_query_engine() -> Neo4jQueryEngine:
    from .api import app  # Local import to avoid circular dependency

    engine = app.state.query_engine
    if engine is None:
        raise HTTPException(status_code=500, detail="Query engine not configured")
    return engine


def get_graph(role: str = Depends(get_current_role)) -> IGraphAdapter:
    from .api import app  # Local import to avoid circular dependency

    graph = app.state.graph
    if graph is None:
        raise HTTPException(status_code=500, detail="Graph not configured")
    if role:
        return RoleBasedGraphAdapter(graph, role=role)
    return graph


def get_permissions_graph(
    user_id: str = Query(..., description="User performing the request"),
    group_id: str | None = Query(None, description="Optional group context"),
    graph: IGraphAdapter = Depends(get_graph),
) -> PermissionsGraphAdapter:
    """Return a :class:`PermissionsGraphAdapter` for the current request."""

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    return PermissionsGraphAdapter(graph, user_id=user_id, group_id=group_id)


def get_vector_store() -> VectorStore:
    from .api import app  # Local import to avoid circular dependency

    store = app.state.vector_store
    if store is None:
        raise HTTPException(status_code=500, detail="Vector store not configured")
    return store


async def get_entity(
    type: str,
    id: str,
    perm_graph: PermissionsGraphAdapter = Depends(get_permissions_graph),
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Return attributes for node ``id`` if its ``type`` matches."""

    attrs = perm_graph.get_node(id)
    if attrs is not None and attrs.get("type") == type:
        return attrs

    func = getattr(graph, "get_node")
    if inspect.iscoroutinefunction(func) or isinstance(graph, IAsyncGraphAdapter):
        base_attrs = await func(id)  # type: ignore[misc]
    else:
        base_attrs = func(id)

    if base_attrs is None or base_attrs.get("type") != type:
        raise HTTPException(status_code=404, detail="Entity not found")

    raise HTTPException(status_code=403, detail="Access denied")

