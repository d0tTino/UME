from __future__ import annotations

from typing import TYPE_CHECKING

from .graph_adapter import IGraphAdapter
from .policy.pipeline import PolicyContext, PolicyDecision, build_default_policy_pipeline

if TYPE_CHECKING:  # pragma: no cover - for type hints only
    from .event_ledger import EventLedger


def replay_from_ledger(
    graph: IGraphAdapter,
    ledger: "EventLedger",
    start_offset: int = 0,
    end_offset: int | None = None,
    *,
    end_timestamp: int | None = None,
) -> int:
    """Replay ledger events into ``graph`` starting from ``start_offset``."""
    last = start_offset
    from .processing import apply_event_to_graph

    pipeline = build_default_policy_pipeline(redactor=lambda payload: (payload, False))

    for off, data in ledger.range(start=start_offset, end=end_offset):
        if end_timestamp is not None and data.get("timestamp", 0) > end_timestamp:
            break
        context = PolicyContext(source="cli_replay", transport_data=data)
        result = pipeline.evaluate(context)
        if result.decision in {PolicyDecision.DENY, PolicyDecision.QUARANTINE} or context.event is None:
            continue
        apply_event_to_graph(context.event, graph)
        pipeline.audit_post_apply(context)
        last = off
    return last


def build_graph_from_ledger(
    ledger: "EventLedger",
    graph: IGraphAdapter | None = None,
    *,
    end_offset: int | None = None,
    end_timestamp: int | None = None,
    db_path: str | None = ":memory:",
) -> IGraphAdapter:
    """Return ``graph`` populated from ``ledger``."""
    if graph is None:
        from .persistent_graph import PersistentGraph

        graph = PersistentGraph(db_path, check_same_thread=False)
    replay_from_ledger(
        graph,
        ledger,
        start_offset=0,
        end_offset=end_offset,
        end_timestamp=end_timestamp,
    )
    return graph


def graph_from_event_ledger(
    *,
    end_offset: int | None = None,
    end_timestamp: int | None = None,
    db_path: str | None = ":memory:",
    graph: IGraphAdapter | None = None,
) -> IGraphAdapter:
    """Rebuild a graph from the global :data:`event_ledger`."""

    from .event_ledger import event_ledger

    return build_graph_from_ledger(
        event_ledger,
        graph=graph,
        end_offset=end_offset,
        end_timestamp=end_timestamp,
        db_path=db_path,
    )


def snapshot_from_event_ledger(
    *, end_offset: int | None = None, end_timestamp: int | None = None
) -> dict[str, object]:
    """Return a snapshot built from :data:`event_ledger`."""

    graph = graph_from_event_ledger(
        end_offset=end_offset, end_timestamp=end_timestamp
    )
    return graph.dump()
