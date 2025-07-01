"""Shared FastAPI dependency functions used across routers."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from .config import settings
from .rbac_adapter import RoleBasedGraphAdapter
from .graph_adapter import IGraphAdapter
from .query import Neo4jQueryEngine
from . import VectorStore


logger = logging.getLogger(__name__)

# Directory containing local Rego policy files
POLICY_DIR = Path(__file__).with_name("plugins") / "alignment" / "policies"

# OAuth2 configuration and issued tokens
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
TOKENS: Dict[str, tuple[str, float]] = {}


def configure_graph(graph: IGraphAdapter) -> None:
    """Set ``app.state.graph`` applying RBAC if configured."""
    from .api import app  # Local import to avoid circular dependency

    role = settings.UME_API_ROLE
    if role:
        graph = RoleBasedGraphAdapter(graph, role=role)
    app.state.graph = graph
    if settings.UME_API_TOKEN:
        expires_at = time.time() + settings.UME_OAUTH_TTL
        TOKENS[settings.UME_API_TOKEN] = (settings.UME_OAUTH_ROLE, expires_at)


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


def get_current_role(token: str = Depends(oauth2_scheme)) -> str:
    if token == settings.UME_API_TOKEN:
        return settings.UME_API_ROLE or ""
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


def get_vector_store() -> VectorStore:
    from .api import app  # Local import to avoid circular dependency

    store = app.state.vector_store
    if store is None:
        raise HTTPException(status_code=500, detail="Vector store not configured")
    return store

