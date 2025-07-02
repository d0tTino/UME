"""HTTP API exposing graph queries and analytics."""

from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, cast
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
from uuid import uuid4
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.security import OAuth2PasswordRequestForm

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .metrics import REQUEST_COUNT, REQUEST_LATENCY
from pydantic import BaseModel

from .audit import get_audit_entries
from .rbac_adapter import AccessDeniedError
from .graph_adapter import IGraphAdapter
from . import VectorStore, create_vector_store
from .api_deps import (
    POLICY_DIR,  # noqa: F401 re-exported for tests
    TOKENS,
    configure_graph,  # noqa: F401 re-exported for tests
    configure_vector_store,  # noqa: F401 re-exported for tests
    get_current_role,
    get_graph,
    get_vector_store,
)
from .graph_routes import router as graph_router
from .vector_routes import router as vector_router
from .policy_routes import router as policy_router

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


@app.on_event("shutdown")
def _close_vector_store() -> None:
    """Ensure the configured vector store is properly closed."""
    store = getattr(app.state, "vector_store", None)
    if store is not None and hasattr(store, "close"):
        store.close()


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
app.state.query_engine = cast(Any, None)
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


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@app.post("/token")
def issue_token(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    if (
        form_data.username == settings.UME_OAUTH_USERNAME
        and form_data.password == settings.UME_OAUTH_PASSWORD
    ):
        token = str(uuid4())
        expires_at = time.time() + settings.UME_OAUTH_TTL
        TOKENS[token] = (settings.UME_OAUTH_ROLE, expires_at)
        return TokenResponse(access_token=token)
    raise HTTPException(status_code=400, detail="Invalid credentials")
    

@app.get("/metrics")
def metrics_endpoint(_: str = Depends(get_current_role)) -> Response:
    """Expose Prometheus metrics."""
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


@app.get("/metrics/summary")
def metrics_summary(
    _: str = Depends(get_current_role),
    store: VectorStore = Depends(get_vector_store),
) -> Dict[str, Any]:
    """Return a summary of core Prometheus metrics."""
    total_requests = 0.0
    by_status: Dict[str, float] = {}
    for metric in REQUEST_COUNT.collect():
        for s in metric.samples:
            if s.name.endswith("_total"):
                status = s.labels.get("status", "unknown")
                total_requests += s.value
                by_status[status] = by_status.get(status, 0) + s.value

    latency_sum = 0.0
    latency_count = 0.0
    for metric in REQUEST_LATENCY.collect():
        for s in metric.samples:
            if s.name.endswith("_sum"):
                latency_sum += s.value
            elif s.name.endswith("_count"):
                latency_count += s.value
    avg_latency = latency_sum / latency_count if latency_count else 0.0

    index_size = len(getattr(store, "idx_to_id", []))
    return {
        "total_requests": int(total_requests),
        "request_count_by_status": {k: int(v) for k, v in by_status.items()},
        "average_request_latency": avg_latency,
        "vector_index_size": index_size,
    }


@app.get("/dashboard/stats")
def dashboard_stats(
    _: str = Depends(get_current_role),
    graph: IGraphAdapter = Depends(get_graph),
    store: VectorStore = Depends(get_vector_store),
) -> Dict[str, Any]:
    """Return basic graph and vector index statistics for the dashboard."""
    node_count = len(graph.get_all_node_ids())
    edge_count = len(graph.get_all_edges())
    index_size = len(getattr(store, "idx_to_id", []))
    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "vector_index_size": index_size,
    }


@app.get("/dashboard/recent_events")
def dashboard_recent_events(
    limit: int = 10,
    _: str = Depends(get_current_role),
) -> List[Dict[str, Any]]:
    """Return recent audit log entries for the dashboard, newest first."""
    entries = get_audit_entries()
    return list(reversed(entries[-limit:]))


def _redaction_count() -> int:
    """Return the number of payload redactions recorded in the audit log."""
    entries = get_audit_entries()
    return sum(
        1 for e in entries if "payload_redacted" in str(e.get("reason", ""))
    )


@app.get("/pii/redactions")
def pii_redactions(_: str = Depends(get_current_role)) -> Dict[str, int]:
    """Return the total count of redacted payloads."""
    return {"redacted": _redaction_count()}


class Recommendation(BaseModel):
    id: str
    action: str


RECOMMENDATIONS: list[Recommendation] = [
    Recommendation(id="rec1", action="Upgrade vector index"),
    Recommendation(id="rec2", action="Review new node attributes"),
]

FEEDBACK: dict[str, list[str]] = defaultdict(list)


@app.get("/recommendations")
def get_recommendations(
    _: str = Depends(get_current_role),
) -> list[Recommendation]:
    """Return overseer recommended actions."""
    return RECOMMENDATIONS


class RecommendationFeedback(BaseModel):
    id: str
    feedback: str


@app.post("/recommendations/feedback")
def submit_feedback(
    req: RecommendationFeedback, _: str = Depends(get_current_role)
) -> Dict[str, str]:
    """Record user feedback for a recommendation."""
    FEEDBACK[req.id].append(req.feedback)
    return {"status": "ok"}

