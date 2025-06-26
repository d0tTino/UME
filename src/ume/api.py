"""HTTP API exposing graph queries and analytics."""

from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, cast, AsyncGenerator
import asyncio
from collections import defaultdict
from pathlib import Path

try:  # pragma: no cover - optional dependency
    import redis
except Exception:  # pragma: no cover - allow tests without redis installed
    redis = None
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

from .config import settings
from .logging_utils import configure_logging
from .tracing import configure_tracing, is_tracing_enabled
from opentelemetry import trace
from uuid import uuid4
from fastapi import Depends, FastAPI, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import JSONResponse, Response
from sse_starlette.sse import EventSourceResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .metrics import REQUEST_COUNT, REQUEST_LATENCY
from pydantic import BaseModel

from .analytics import shortest_path
from .reliability import filter_low_confidence
from .audit import get_audit_entries
from .rbac_adapter import RoleBasedGraphAdapter, AccessDeniedError
from .graph_adapter import IGraphAdapter
from .query import Neo4jQueryEngine
from . import VectorStore, create_default_store

logger = logging.getLogger(__name__)

# Directory containing local Rego policy files
POLICY_DIR = Path(__file__).with_name("plugins") / "alignment" / "policies"


configure_logging()
configure_tracing()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
# map token -> (role, expiry)
TOKENS: Dict[str, tuple[str, float]] = {}

app = FastAPI(
    title="UME API",
    version="0.1.0",
    description="HTTP API for the Universal Memory Engine.",
)

if is_tracing_enabled():
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app, tracer_provider=trace.get_tracer_provider())


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
    app.state.vector_store = cast(Any, create_default_store())
except ImportError:  # pragma: no cover - optional dependency
    logger.warning("Vector store dependencies missing; continuing without one")
    app.state.vector_store = None


def configure_graph(graph: IGraphAdapter) -> None:
    """Set ``app.state.graph`` applying RBAC if ``settings.UME_API_ROLE`` is defined."""
    role = settings.UME_API_ROLE
    if role:
        graph = RoleBasedGraphAdapter(graph, role=role)
    app.state.graph = graph
    if settings.UME_API_TOKEN:
        expires_at = time.time() + settings.UME_OAUTH_TTL
        TOKENS[settings.UME_API_TOKEN] = (settings.UME_OAUTH_ROLE, expires_at)


def configure_vector_store(store: VectorStore) -> None:
    """Inject a :class:`VectorStore` instance into the application state.

    If an existing store is configured and it exposes a ``close`` method it will
    be closed prior to assigning the new store. This ensures background flush
    threads are properly shut down.
    """
    existing = getattr(app.state, "vector_store", None)
    if existing is not None and hasattr(existing, "close"):
        try:
            existing.close()
        except Exception as exc:  # pragma: no cover - unexpected failure
            logger.exception("Failed to close existing vector store", exc_info=exc)
    app.state.vector_store = store


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
    """Dependency that ensures a bearer token is provided."""
    return None


def get_query_engine() -> Neo4jQueryEngine:
    engine = app.state.query_engine
    if engine is None:
        raise HTTPException(status_code=500, detail="Query engine not configured")
    return engine


def get_graph(role: str = Depends(get_current_role)) -> IGraphAdapter:
    graph = app.state.graph
    if graph is None:
        raise HTTPException(status_code=500, detail="Graph not configured")
    if role:
        return RoleBasedGraphAdapter(graph, role=role)
    return graph


def get_vector_store() -> VectorStore:
    store = app.state.vector_store
    if store is None:
        raise HTTPException(status_code=500, detail="Vector store not configured")
    return store


@app.get("/query")
def run_cypher(
    cypher: str,
    _: str = Depends(get_current_role),
    engine: Neo4jQueryEngine = Depends(get_query_engine),
) -> List[Dict[str, Any]]:
    """Execute an arbitrary Cypher query and return the result set."""
    return engine.execute_cypher(cypher)


class ShortestPathRequest(BaseModel):
    source: str
    target: str


class PathRequest(BaseModel):
    source: str
    target: str
    max_depth: int | None = None
    edge_label: str | None = None
    since_timestamp: int | None = None


class SubgraphRequest(BaseModel):
    start: str
    depth: int
    edge_label: str | None = None
    since_timestamp: int | None = None


class NodeCreateRequest(BaseModel):
    id: str
    attributes: Dict[str, Any] | None = None


class NodeUpdateRequest(BaseModel):
    attributes: Dict[str, Any]


class EdgeCreateRequest(BaseModel):
    source: str
    target: str
    label: str


class TweetCreateRequest(BaseModel):
    text: str


class DocumentUploadRequest(BaseModel):
    content: str


@app.post("/analytics/shortest_path")
def api_shortest_path(
    req: ShortestPathRequest,
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Return the shortest path between two nodes."""
    path = shortest_path(graph, req.source, req.target)
    filtered = filter_low_confidence(path, settings.UME_RELIABILITY_THRESHOLD)
    return {"path": filtered}


@app.post("/analytics/path")
def api_constrained_path(
    req: PathRequest,
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Find a path subject to optional depth or label constraints."""
    raw_path = graph.constrained_path(
        req.source,
        req.target,
        req.max_depth,
        req.edge_label,
        req.since_timestamp,
    )
    threshold = settings.UME_RELIABILITY_THRESHOLD
    nodes = filter_low_confidence(raw_path, threshold)
    return {"path": nodes}


@app.get("/analytics/path/stream")
async def api_constrained_path_stream(
    source: str = Query(...),
    target: str = Query(...),
    max_depth: int | None = Query(None),
    edge_label: str | None = Query(None),
    since_timestamp: int | None = Query(None),
    _: str = Depends(get_current_role),
    graph: IGraphAdapter = Depends(get_graph),
    __: None = Depends(RateLimiter(times=2, seconds=1)),
) -> EventSourceResponse:
    """Stream path nodes one by one as an SSE feed."""

    async def _gen() -> AsyncGenerator[dict[str, str], None]:
        path = graph.constrained_path(
            source, target, max_depth, edge_label, since_timestamp
        )
        filtered = filter_low_confidence(path, settings.UME_RELIABILITY_THRESHOLD)
        for node in filtered:
            yield {"data": node}
            await asyncio.sleep(0)

    return EventSourceResponse(_gen())


@app.post("/analytics/subgraph")
def api_subgraph(
    req: SubgraphRequest,
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Extract a subgraph starting from ``start`` to the given ``depth``."""
    sg = graph.extract_subgraph(
        req.start,
        req.depth,
        req.edge_label,
        req.since_timestamp,
    )
    threshold = settings.UME_RELIABILITY_THRESHOLD
    nodes = filter_low_confidence(sg.get("nodes", {}).keys(), threshold)
    sg["nodes"] = {n: sg["nodes"][n] for n in nodes}
    sg["edges"] = [
        e
        for e in sg.get("edges", [])
        if len(filter_low_confidence(e, threshold)) == len(e)
        and e[0] in sg["nodes"]
        and e[1] in sg["nodes"]
    ]
    return sg


@app.post("/redact/node/{node_id}")
def api_redact_node(
    node_id: str,
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Redact (delete) a node by its ID."""
    graph.redact_node(node_id)
    return {"status": "ok"}


class RedactEdgeRequest(BaseModel):
    source: str
    target: str
    label: str


@app.post("/redact/edge")
def api_redact_edge(
    req: RedactEdgeRequest,
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Redact an edge between two nodes."""
    graph.redact_edge(req.source, req.target, req.label)
    return {"status": "ok"}


@app.post("/nodes")
def api_create_node(
    req: NodeCreateRequest,
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Create a node with optional attributes."""
    graph.add_node(req.id, req.attributes or {})
    return {"status": "ok"}


@app.patch("/nodes/{node_id}")
def api_update_node(
    node_id: str,
    req: NodeUpdateRequest,
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Update attributes of an existing node."""
    graph.update_node(node_id, req.attributes)
    return {"status": "ok"}


@app.delete("/nodes/{node_id}")
def api_delete_node(
    node_id: str,
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Remove a node from the graph."""
    graph.redact_node(node_id)
    return {"status": "ok"}


@app.post("/edges")
def api_create_edge(
    req: EdgeCreateRequest,
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Create an edge between two nodes."""
    graph.add_edge(req.source, req.target, req.label)
    return {"status": "ok"}


@app.delete("/edges/{source}/{target}/{label}")
def api_delete_edge(
    source: str,
    target: str,
    label: str,
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Delete an edge identified by source, target and label."""
    graph.delete_edge(source, target, label)
    return {"status": "ok"}


@app.post("/tweets")
def api_post_tweet(
    req: TweetCreateRequest,
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Create a tweet node used by the Tweet-bot."""
    node_id = f"tweet:{uuid4()}"
    graph.add_node(node_id, {"text": req.text, "timestamp": int(time.time())})
    return {"id": node_id}


@app.post("/documents")
def api_upload_document(
    req: DocumentUploadRequest,
    graph: IGraphAdapter = Depends(get_graph),
) -> Dict[str, Any]:
    """Upload a document for Document Guru."""
    node_id = f"doc:{uuid4()}"
    graph.add_node(node_id, {"content": req.content, "timestamp": int(time.time())})
    return {"id": node_id}


class VectorAddRequest(BaseModel):
    id: str
    vector: List[float]


@app.post("/vectors")
def api_add_vector(
    req: VectorAddRequest,
    _: str = Depends(get_current_role),
    store: VectorStore = Depends(get_vector_store),
) -> Dict[str, Any]:
    """Store an embedding vector for later similarity search."""
    if len(req.vector) != store.dim:
        raise HTTPException(status_code=400, detail="Invalid vector dimension")
    store.add(req.id, req.vector)
    return {"status": "ok"}


@app.get("/vectors/search")
def api_search_vectors(
    vector: List[float] = Query(...),
    k: int = 5,
    _: str = Depends(get_current_role),
    store: VectorStore = Depends(get_vector_store),
) -> Dict[str, Any]:
    """Find the IDs of the ``k`` nearest vectors to ``vector``."""
    if len(vector) != store.dim:
        raise HTTPException(status_code=400, detail="Invalid vector dimension")
    ids = store.query(vector, k=k)
    return {"ids": ids}


@app.get("/vectors/benchmark")
def api_benchmark_vectors(
    use_gpu: bool = Query(False),
    num_vectors: int = 1000,
    num_queries: int = 100,
    _: str = Depends(get_current_role),
    store: VectorStore = Depends(get_vector_store),
) -> Dict[str, Any]:
    """Run a synthetic benchmark against the vector store."""
    from .benchmarks import benchmark_vector_store

    return benchmark_vector_store(
        use_gpu,
        dim=store.dim,
        num_vectors=num_vectors,
        num_queries=num_queries,
    )


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


def _resolve_policy_path(name: str) -> Path:
    """Return absolute path for policy ``name`` within :data:`POLICY_DIR`."""
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise HTTPException(status_code=400, detail="Invalid policy path")
    return (POLICY_DIR / path).resolve()


@app.get("/policies")
def list_policies(_: str = Depends(get_current_role)) -> Dict[str, List[str]]:
    """List all available Rego policy files."""
    files = [p.relative_to(POLICY_DIR).as_posix() for p in POLICY_DIR.rglob("*.rego")]
    return {"policies": sorted(files)}


@app.post("/policies/{name:path}")
async def add_policy(
    name: str,
    file: UploadFile = File(...),
    _: str = Depends(get_current_role),
) -> Dict[str, str]:
    """Upload a Rego policy file under ``name``."""
    path = _resolve_policy_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    with path.open("wb") as f:
        f.write(content)
    return {"status": "ok"}


@app.delete("/policies/{name:path}")
def delete_policy(name: str, _: str = Depends(get_current_role)) -> Dict[str, str]:
    """Delete a policy file."""
    path = _resolve_policy_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Policy not found")
    path.unlink()
    return {"status": "ok"}
