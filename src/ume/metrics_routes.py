from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Response

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .metrics import REQUEST_COUNT, REQUEST_LATENCY, RECALL_SCORE
from .api_deps import get_current_role, get_vector_store
from .vector_store import VectorStore

router = APIRouter(prefix="/metrics")


@router.get("")
def metrics_endpoint(_: str = Depends(get_current_role)) -> Response:
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


@router.get("/summary")
def metrics_summary(
    _: str = Depends(get_current_role),
    store: VectorStore = Depends(get_vector_store),
) -> Dict[str, Any]:
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

    recall_sum = 0.0
    recall_count = 0.0
    for metric in RECALL_SCORE.collect():
        for s in metric.samples:
            if s.name.endswith("_sum"):
                recall_sum += s.value
            elif s.name.endswith("_count"):
                recall_count += s.value
    avg_recall = recall_sum / recall_count if recall_count else 0.0

    index_size = len(getattr(store, "idx_to_id", []))
    return {
        "total_requests": int(total_requests),
        "request_count_by_status": {k: int(v) for k, v in by_status.items()},
        "average_request_latency": avg_latency,
        "vector_index_size": index_size,
        "average_recall_score": avg_recall,
    }
