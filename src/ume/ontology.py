from __future__ import annotations

import logging
import math
import time
from typing import Dict, List

from .embedding import generate_embedding
from .event import Event, EventType
from .graph_adapter import IGraphAdapter
from .processing import apply_event_to_graph
from ._internal.listeners import GraphListener

logger = logging.getLogger(__name__)


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Return the cosine similarity of two vectors."""
    if len(a) != len(b):
        raise ValueError("Vector length mismatch")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_concept_graph(
    graph: IGraphAdapter, *, threshold: float = 0.8
) -> List[Event]:
    """Generate ontology edges between similar nodes.

    Nodes are compared using embeddings derived from their ``text`` or
    ``name`` attribute. Existing embeddings are reused if present.
    Returns the list of :class:`Event` objects applied to ``graph``.
    """
    node_ids = graph.get_all_node_ids()
    embeddings: Dict[str, List[float]] = {}
    for nid in node_ids:
        data = graph.get_node(nid) or {}
        emb = data.get("embedding")
        if not isinstance(emb, list):
            text = str(data.get("text") or data.get("name") or "")
            if not text:
                continue
            emb = generate_embedding(text)
        embeddings[nid] = emb

    ids = list(embeddings.keys())
    events: List[Event] = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            e1 = embeddings[ids[i]]
            e2 = embeddings[ids[j]]
            sim = _cosine_similarity(e1, e2)
            if sim >= threshold:
                event = Event(
                    event_type=EventType.CREATE_ONTOLOGY_RELATION,
                    timestamp=int(time.time()),
                    node_id=ids[i],
                    target_node_id=ids[j],
                    label="RELATES_TO",
                    payload={"similarity": sim},
                )
                apply_event_to_graph(event, graph)
                events.append(event)
    logger.info("Created %s ontology relations", len(events))
    return events


def update_concept_graph_for_node(
    graph: IGraphAdapter, node_id: str, *, threshold: float = 0.8
) -> List[Event]:
    """Update ontology relations for ``node_id`` against existing nodes."""
    node = graph.get_node(node_id)
    if not node:
        return []
    emb = node.get("embedding")
    if not isinstance(emb, list):
        text = str(node.get("text") or node.get("name") or "")
        if not text:
            return []
        emb = generate_embedding(text)
    events: List[Event] = []
    for other_id in graph.get_all_node_ids():
        if other_id == node_id:
            continue
        other = graph.get_node(other_id) or {}
        other_emb = other.get("embedding")
        if not isinstance(other_emb, list):
            text = str(other.get("text") or other.get("name") or "")
            if not text:
                continue
            other_emb = generate_embedding(text)
        sim = _cosine_similarity(emb, other_emb)
        if sim >= threshold:
            event = Event(
                event_type=EventType.CREATE_ONTOLOGY_RELATION,
                timestamp=int(time.time()),
                node_id=node_id,
                target_node_id=other_id,
                label="RELATES_TO",
                payload={"similarity": sim},
            )
            apply_event_to_graph(event, graph)
            events.append(event)
    logger.info(
        "Updated ontology for %s with %s relations", node_id, len(events)
    )
    return events


_ONTOLOGY_GRAPH: IGraphAdapter | None = None


def configure_ontology_graph(graph: IGraphAdapter) -> None:
    """Set the graph used by :class:`OntologyListener`."""
    global _ONTOLOGY_GRAPH
    _ONTOLOGY_GRAPH = graph


class OntologyListener(GraphListener):
    """Listener that updates ontology relations on new nodes."""

    def __init__(self, *, threshold: float = 0.8) -> None:
        self.threshold = threshold

    def on_node_created(self, node_id: str, attributes: Dict[str, object]) -> None:
        if _ONTOLOGY_GRAPH is not None:
            update_concept_graph_for_node(
                _ONTOLOGY_GRAPH, node_id, threshold=self.threshold
            )

    def on_node_updated(self, node_id: str, attributes: Dict[str, object]) -> None:
        pass  # No-op

    def on_edge_created(
        self, source_node_id: str, target_node_id: str, label: str
    ) -> None:
        pass  # No-op

    def on_edge_deleted(
        self, source_node_id: str, target_node_id: str, label: str
    ) -> None:
        pass  # No-op
