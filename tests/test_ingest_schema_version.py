from __future__ import annotations

from types import SimpleNamespace
from typing import Dict

import pytest

from ume.graph import MockGraph
from ume.graph_schema import EdgeLabel, GraphSchema
from ume.schema_manager import DEFAULT_SCHEMA_MANAGER
from ume.services.ingest import (
    dict_to_envelope,
    envelope_to_event_dict,
    ingest_event,
)


class SpyGraph(MockGraph):
    """Graph adapter that captures schema metadata for edges."""

    def __init__(self, perm_defaults: Dict[str, str]) -> None:
        super().__init__()
        self._perm_defaults = perm_defaults
        self.recorded_versions: list[str | None] = []

    def add_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        label: str,
        attrs: Dict[str, object] | None = None,
        schema_version: str | None = None,
    ) -> None:
        self.recorded_versions.append(schema_version)
        attr_dict = dict(attrs or {})
        if schema_version is not None:
            attr_dict.setdefault("schema_version", schema_version)
            default = self._perm_defaults.get(schema_version)
            if default is not None:
                attr_dict.setdefault("permission_level", default)
        super().add_edge(
            source_node_id,
            target_node_id,
            label,
            attr_dict,
            schema_version=schema_version,
        )


@pytest.fixture(autouse=True)
def _silence_classification(monkeypatch: pytest.MonkeyPatch) -> None:
    import ume.services.ingest as ingest_module

    monkeypatch.setattr(ingest_module, "classify_event", lambda event: [])
    monkeypatch.setattr(
        ingest_module,
        "_anomaly_detector",
        SimpleNamespace(process_event=lambda event: None),
    )


@pytest.fixture
def modern_schema_version() -> str:
    version = "3.0.0"
    schema = GraphSchema(
        version=version,
        node_types={},
        edge_labels={
            "SHARED_WITH": EdgeLabel(
                label="SHARED_WITH",
                version=version,
                permission_level="viewer",
                permission_level_values=("viewer", "editor"),
            )
        },
    )
    previous = DEFAULT_SCHEMA_MANAGER._schemas.get(version)
    DEFAULT_SCHEMA_MANAGER._schemas[version] = schema
    try:
        yield version
    finally:
        if previous is None:
            DEFAULT_SCHEMA_MANAGER._schemas.pop(version, None)
        else:
            DEFAULT_SCHEMA_MANAGER._schemas[version] = previous


@pytest.fixture
def legacy_schema_version() -> str:
    version = "2.9.9"
    schema = GraphSchema(
        version=version,
        node_types={},
        edge_labels={
            "SHARED_WITH": EdgeLabel(
                label="SHARED_WITH",
                version=version,
                permission_level="legacy_viewer",
                permission_level_values=("legacy_viewer", "legacy_editor"),
            )
        },
    )
    previous = DEFAULT_SCHEMA_MANAGER._schemas.get(version)
    DEFAULT_SCHEMA_MANAGER._schemas[version] = schema
    try:
        yield version
    finally:
        if previous is None:
            DEFAULT_SCHEMA_MANAGER._schemas.pop(version, None)
        else:
            DEFAULT_SCHEMA_MANAGER._schemas[version] = previous


def _permission_event(target: str, schema_version: str) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "eventType": "CREATE_EDGE",
        "timestamp": 1,
        "node_id": "doc",
        "target_node_id": target,
        "label": "SHARED_WITH",
        "payload": {},
    }


def test_ingest_respects_envelope_schema_versions(
    modern_schema_version: str,
    legacy_schema_version: str,
) -> None:
    events = [
        _permission_event("current_user", modern_schema_version),
        _permission_event("legacy_user", legacy_schema_version),
    ]

    envelopes = [dict_to_envelope(evt) for evt in events]
    assert [env.schema_version for env in envelopes] == [
        modern_schema_version,
        legacy_schema_version,
    ]

    round_tripped = [envelope_to_event_dict(env) for env in envelopes]
    assert [evt["schema_version"] for evt in round_tripped] == [
        modern_schema_version,
        legacy_schema_version,
    ]

    graph = SpyGraph(
        {modern_schema_version: "viewer", legacy_schema_version: "legacy_viewer"}
    )
    graph.add_node("doc", {"type": "Document"})
    graph.add_node("current_user", {"type": "User"})
    graph.add_node("legacy_user", {"type": "User"})

    for payload in round_tripped:
        ingest_event(payload, graph)

    assert graph.recorded_versions == [modern_schema_version, legacy_schema_version]

    attrs_by_target = {target: attrs for _src, target, _label, attrs in graph.get_all_edges()}

    modern_attrs = attrs_by_target["current_user"]
    legacy_attrs = attrs_by_target["legacy_user"]

    assert modern_attrs["schema_version"] == modern_schema_version
    assert modern_attrs["permission_level"] == "viewer"

    assert legacy_attrs["schema_version"] == legacy_schema_version
    assert legacy_attrs["permission_level"] == "legacy_viewer"


def test_ingest_event_prefers_explicit_schema_version_argument(
    modern_schema_version: str,
    legacy_schema_version: str,
) -> None:
    graph = SpyGraph(
        {modern_schema_version: "viewer", legacy_schema_version: "legacy_viewer"}
    )
    graph.add_node("doc", {"type": "Document"})
    graph.add_node("target", {"type": "User"})

    ingest_event(
        _permission_event("target", legacy_schema_version),
        graph,
        schema_version=f"  {modern_schema_version}  ",
    )

    assert graph.recorded_versions == [modern_schema_version]


def test_ingest_event_uses_payload_schema_version_when_argument_missing(
    modern_schema_version: str,
) -> None:
    graph = SpyGraph({modern_schema_version: "viewer"})
    graph.add_node("doc", {"type": "Document"})
    graph.add_node("target", {"type": "User"})

    ingest_event({"event": _permission_event("target", modern_schema_version)}, graph)

    assert graph.recorded_versions == [modern_schema_version]


def test_ingest_event_uses_payload_schema_version_when_envelope_version_blank(
    modern_schema_version: str,
) -> None:
    graph = SpyGraph({modern_schema_version: "viewer"})
    graph.add_node("doc", {"type": "Document"})
    graph.add_node("target", {"type": "User"})

    ingest_event(
        {
            "schema_version": "   ",
            "event": _permission_event("target", f" {modern_schema_version} "),
        },
        graph,
    )

    assert graph.recorded_versions == [modern_schema_version]


def test_ingest_event_prefers_envelope_schema_version_over_payload(
    modern_schema_version: str,
    legacy_schema_version: str,
) -> None:
    graph = SpyGraph(
        {modern_schema_version: "viewer", legacy_schema_version: "legacy_viewer"}
    )
    graph.add_node("doc", {"type": "Document"})
    graph.add_node("target", {"type": "User"})

    ingest_event(
        {
            "schema_version": f" {modern_schema_version} ",
            "event": _permission_event("target", legacy_schema_version),
        },
        graph,
    )

    assert graph.recorded_versions == [modern_schema_version]


def test_ingest_event_falls_back_when_schema_versions_missing(
    monkeypatch: pytest.MonkeyPatch,
    modern_schema_version: str,
) -> None:
    graph = SpyGraph({modern_schema_version: "viewer"})
    graph.add_node("doc", {"type": "Document"})
    graph.add_node("target", {"type": "User"})

    monkeypatch.setattr(
        "ume.services.ingest._fallback_schema_version",
        lambda: f" {modern_schema_version} ",
    )

    payload = _permission_event("target", "unused")
    payload.pop("schema_version")
    ingest_event(payload, graph, schema_version="   ")

    assert graph.recorded_versions == [modern_schema_version]
