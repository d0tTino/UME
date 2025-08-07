"""HTTP API exposing graph queries and analytics."""

from __future__ import annotations

import logging
import time
import asyncio
from typing import Any, Awaitable, Callable, cast
from collections import defaultdict

try:  # pragma: no cover - optional dependency
    import redis
except Exception:  # pragma: no cover - allow tests without redis installed
    redis = None
from fastapi_limiter import FastAPILimiter

from .config import settings
from .logging_utils import configure_logging
from .tracing import configure_tracing, is_tracing_enabled

try:  # pragma: no cover - optional dependency
    from opentelemetry import trace
except Exception:  # pragma: no cover - allow tests without opentelemetry installed
    trace = None
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette_graphene3 import GraphQLApp, make_graphiql_handler

from .metrics import REQUEST_COUNT, REQUEST_LATENCY
from .retention import (
    start_ledger_compaction_scheduler,
    stop_ledger_compaction_scheduler,
)

from .rbac_adapter import AccessDeniedError
from .graph_adapter import IGraphAdapter  # noqa: F401
from . import VectorStore, create_vector_store  # noqa: F401
from .vector_store import VectorStoreListener
from ._internal.listeners import register_listener, unregister_listener


from .graph_routes import router as graph_router
from .vector_routes import router as vector_router
from .policy_routes import router as policy_router
from .auth_routes import router as auth_router
from .metrics_routes import router as metrics_router
from .dashboard_routes import router as dashboard_router
from .pii_routes import router as pii_router
from .recommendations_routes import router as recommendations_router
from .feedback_routes import router as feedback_router
from .snapshot_routes import router as snapshot_router
from .ledger_routes import router as ledger_router
from .dossier_routes import router as dossier_router
from .consent_ledger import consent_ledger  # noqa: F401
from .graphql_api import schema as graphql_schema

from . import api_deps

POLICY_DIR = api_deps.POLICY_DIR  # noqa: F401 re-exported for tests
TOKENS = api_deps.TOKENS  # noqa: F401 re-exported for tests
configure_graph = api_deps.configure_graph  # noqa: F401 re-exported for tests
configure_vector_store = api_deps.configure_vector_store  # noqa: F401 re-exported for tests

# Interval between token cleanup runs in seconds
TOKEN_CLEANUP_INTERVAL = 60.0

_token_cleanup_task: asyncio.Task | None = None
_ledger_compaction_stop: Callable[[], None] | None = None
_vector_listener: VectorStoreListener | None = None


logger = logging.getLogger(__name__)

configure_logging()
configure_tracing()

app = FastAPI(
    title="UME API",
    version="0.1.0",
    description="HTTP API for the Universal Memory Engine.",
)

if is_tracing_enabled() and trace is not None:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app, tracer_provider=trace.get_tracer_provider())

app.include_router(graph_router)
app.include_router(vector_router)
app.include_router(policy_router)
app.include_router(auth_router)
app.include_router(metrics_router)
app.include_router(dashboard_router)
app.include_router(pii_router)
app.include_router(recommendations_router)
app.include_router(feedback_router)
app.include_router(snapshot_router)
app.include_router(ledger_router)
app.include_router(dossier_router)
# Some unit tests replace ``fastapi.FastAPI`` with a minimal stub that lacks
# ``add_route``. Guard the GraphQL route registration so those tests can import
# this module without the real FastAPI implementation.
if hasattr(app, "add_route"):  # pragma: no cover - exercised only in tests
    app.add_route(
        "/graphql",
        GraphQLApp(
            graphql_schema,
            on_get=make_graphiql_handler(),
            context_value=lambda request: {"app": app},
        ),
        methods=["GET", "POST"],
    )



class _MemoryRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = defaultdict(int)

    async def script_load(self, _: str) -> str:
        return "mem"

    async def evalsha(self, __: str, _k: int, key: str, limit: str, _exp: str) -> int:
        lim = int(limit)
        if self.counts[key] >= lim:
            return 1
        self.counts[key] += 1
        return 0

    async def ping(self) -> None:
        return None

    async def close(self) -> None:
        self.counts.clear()


@app.on_event("startup")
async def _init_limiter() -> None:
    """Initialize rate limiting using Redis or an in-memory fallback."""
    url = settings.UME_RATE_LIMIT_REDIS
    if url and redis:
        try:
            redis_client = redis.from_url(
                url, encoding="utf-8", decode_responses=True
            )
            await redis_client.ping()
        except Exception:  # pragma: no cover - connection issue
            redis_client = _MemoryRedis()
    else:
        redis_client = _MemoryRedis()
    await FastAPILimiter.init(redis_client)


async def _token_cleanup_loop(interval: float) -> None:
    """Periodically remove expired entries from ``TOKENS``."""
    try:
        while True:
            await asyncio.sleep(interval)
            api_deps.remove_expired_tokens()
    except asyncio.CancelledError:  # pragma: no cover - task cancelled
        pass


@app.on_event("startup")
async def _start_token_cleanup() -> None:
    """Launch background task for expired token cleanup."""
    from .event_ledger import event_ledger

    global _token_cleanup_task, _ledger_compaction_stop
    interval = min(TOKEN_CLEANUP_INTERVAL, settings.UME_OAUTH_TTL)
    _token_cleanup_task = asyncio.create_task(_token_cleanup_loop(interval))

    _, stop = start_ledger_compaction_scheduler(
        event_ledger,
        interval_seconds=getattr(settings, "UME_LEDGER_COMPACTION_INTERVAL", 24 * 3600),
        offset_window=getattr(settings, "UME_LEDGER_OFFSET_WINDOW", 1000),
    )
    _ledger_compaction_stop = stop


@app.on_event("startup")
def _register_vector_listener() -> None:
    """Register VectorStoreListener for automatic indexing."""
    global _vector_listener
    store = getattr(app.state, "vector_store", None)
    if store is None:
        return
    listener = VectorStoreListener(store)
    register_listener(listener)
    _vector_listener = listener


@app.on_event("shutdown")
def _unregister_vector_listener() -> None:
    """Remove the VectorStoreListener if it was registered."""
    global _vector_listener
    if _vector_listener is not None:
        unregister_listener(_vector_listener)
        _vector_listener = None


@app.on_event("shutdown")
def _close_vector_store() -> None:
    """Ensure the configured vector store is properly closed."""
    store = getattr(app.state, "vector_store", None)
    if store is not None and hasattr(store, "close"):
        store.close()


@app.on_event("shutdown")
async def _stop_token_cleanup() -> None:
    """Cancel the background token cleanup task if running."""
    global _token_cleanup_task, _ledger_compaction_stop
    if _token_cleanup_task is not None:
        _token_cleanup_task.cancel()
        try:
            await _token_cleanup_task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        _token_cleanup_task = None
    if _ledger_compaction_stop is not None:
        _ledger_compaction_stop()
    else:
        stop_ledger_compaction_scheduler()
    _ledger_compaction_stop = None


@app.middleware("http")
async def metrics_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    method = request.method
    path = request.url.path
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception("Unhandled exception while processing request", exc_info=exc)
        REQUEST_LATENCY.labels(method=method, path=path).observe(
            time.perf_counter() - start
        )
        REQUEST_COUNT.labels(method=method, path=path, status="500").inc()
        raise
    REQUEST_LATENCY.labels(method=method, path=path).observe(
        time.perf_counter() - start
    )
    REQUEST_COUNT.labels(
        method=method, path=path, status=str(response.status_code)
    ).inc()
    return response


# These can be configured by the embedding application or tests

class _DefaultQueryEngine:
    def execute_cypher(self, cypher: str) -> list[dict[str, Any]]:
        return [{"q": cypher}]

app.state.query_engine = cast(Any, _DefaultQueryEngine())
app.state.graph = cast(Any, None)
try:
    app.state.vector_store = cast(Any, create_vector_store())
except ImportError:  # pragma: no cover - optional dependency
    logger.warning("Vector store dependencies missing; continuing without one")
    app.state.vector_store = None



@app.exception_handler(AccessDeniedError)
async def access_denied_handler(
    request: Request, exc: AccessDeniedError
) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return 400 for request validation errors."""
    return JSONResponse(status_code=400, content={"detail": exc.errors()})


