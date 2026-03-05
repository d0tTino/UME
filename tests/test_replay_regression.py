from __future__ import annotations

import json
from pathlib import Path

from ume.event_ledger import EventLedger
from ume.persistent_graph import PersistentGraph
from ume.replay import ReplayMode, replay_from_ledger


def _load_fixture(name: str) -> dict[str, object]:
    fixture = Path("tests/data/replay_golden") / f"{name}.json"
    return json.loads(fixture.read_text(encoding="utf-8"))


def _run_fixture(fixture: dict[str, object], replay_mode: ReplayMode) -> dict[str, object]:
    ledger = EventLedger(":memory:")
    for entry in fixture["events"]:
        ledger.append(entry["offset"], entry["event"])

    graph = PersistentGraph(":memory:")
    replay_from_ledger(graph, ledger, 0, replay_mode=replay_mode)

    edges = sorted(
        [
            {
                "source": source,
                "target": target,
                "label": label,
                "schema_version": attrs.get("schema_version"),
            }
            for source, target, label, attrs in graph.get_all_edges()
        ],
        key=lambda edge: (edge["source"], edge["target"], edge["label"]),
    )

    return {
        "nodes": sorted(graph.get_all_node_ids()),
        "edges": edges,
    }


def test_replay_golden_fixture_matches_expected_end_state() -> None:
    fixture = _load_fixture("mixed_schema_policy")
    expected = fixture["expected"]

    strict_state = _run_fixture(fixture, ReplayMode.STRICT_HISTORICAL)
    current_state = _run_fixture(fixture, ReplayMode.CURRENT_POLICY)

    assert strict_state == expected["strict_historical"]
    assert current_state == expected["current_policy"]


def test_replay_golden_fixture_is_deterministic() -> None:
    fixture = _load_fixture("mixed_schema_policy")

    first = _run_fixture(fixture, ReplayMode.STRICT_HISTORICAL)
    second = _run_fixture(fixture, ReplayMode.STRICT_HISTORICAL)
    assert first == second
