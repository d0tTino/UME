"""Graph route permission tests for editor vs viewer behavior."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume.api_deps import TOKENS, TOKENS_LOCK
from ume.config import settings
from ume.graph import MockGraph


@pytest.fixture()
def client_with_graph() -> tuple[TestClient, MockGraph, dict[str, str]]:
    graph = MockGraph()
    configure_graph(graph)
    client = TestClient(app)
    try:
        token_res = client.post(
            "/auth/token",
            data={
                "username": settings.UME_OAUTH_USERNAME,
                "password": settings.UME_OAUTH_PASSWORD,
            },
        )
        token_res.raise_for_status()
        token = token_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        yield client, graph, headers
    finally:
        client.close()
        with TOKENS_LOCK:
            TOKENS.clear()


def test_viewer_cannot_modify_graph(client_with_graph: tuple[TestClient, MockGraph, dict[str, str]]) -> None:
    client, graph, headers = client_with_graph

    graph.add_node("doc", {"type": "Document"})
    graph.add_node("viewer", {"type": "User"})
    graph.add_node("team", {"type": "UserGroup"})
    graph.add_node("target", {"type": "User"})
    graph.add_edge("doc", "viewer", "OWNED_BY", {"permission_level": "viewer"})
    graph.add_edge("target", "viewer", "OWNED_BY", {"permission_level": "viewer"})

    params = {"user_id": "viewer"}

    res = client.patch(
        "/nodes/doc",
        json={"attributes": {"title": "updated"}},
        headers=headers,
        params=params,
    )
    assert res.status_code == 403
    assert "Editor permission required" in res.json()["detail"]

    res = client.post(
        "/edges",
        json={
            "source": "doc",
            "target": "team",
            "label": "SHARED_WITH",
            "attrs": {"permission_level": "viewer"},
        },
        headers=headers,
        params=params,
    )
    assert res.status_code == 403

    res = client.delete("/nodes/doc", headers=headers, params=params)
    assert res.status_code == 403


def test_permission_edge_requires_permission_level(
    client_with_graph: tuple[TestClient, MockGraph, dict[str, str]]
) -> None:
    client, graph, headers = client_with_graph

    graph.add_node("doc", {"type": "Document"})
    graph.add_node("owner", {"type": "User"})
    graph.add_node("team_view", {"type": "UserGroup"})
    graph.add_node("team_missing", {"type": "UserGroup"})
    graph.add_edge("doc", "owner", "OWNED_BY", {"permission_level": "editor"})

    params = {"user_id": "owner"}

    success = client.post(
        "/edges",
        json={
            "source": "doc",
            "target": "team_view",
            "label": "SHARED_WITH",
            "attrs": {"permission_level": "viewer"},
        },
        headers=headers,
        params=params,
    )
    assert success.status_code == 200
    assert any(
        edge[0] == "doc"
        and edge[1] == "team_view"
        and edge[2] == "SHARED_WITH"
        and edge[3].get("permission_level") == "viewer"
        for edge in graph.get_all_edges()
    )

    failure = client.post(
        "/edges",
        json={
            "source": "doc",
            "target": "team_missing",
            "label": "SHARED_WITH",
        },
        headers=headers,
        params=params,
    )
    assert failure.status_code == 400
    detail = failure.json()["detail"]
    assert isinstance(detail, list)
    assert any(
        isinstance(entry, dict)
        and entry.get("msg", "").startswith(
            "permission_level is required for OWNED_BY/SHARED_WITH edges"
        )
        for entry in detail
    )


def test_invalid_permission_level_value(
    client_with_graph: tuple[TestClient, MockGraph, dict[str, str]]
) -> None:
    client, graph, headers = client_with_graph

    graph.add_node("doc", {"type": "Document"})
    graph.add_node("owner", {"type": "User"})
    graph.add_node("target", {"type": "User"})
    graph.add_edge("doc", "owner", "OWNED_BY", {"permission_level": "editor"})

    params = {"user_id": "owner"}
    response = client.post(
        "/edges",
        json={
            "source": "doc",
            "target": "target",
            "label": "SHARED_WITH",
            "attrs": {"permission_level": "admin"},
        },
        headers=headers,
        params=params,
    )

    assert response.status_code == 403
    assert "Invalid permission_level" in response.json()["detail"]


def test_subgraph_filters_view_only_subjects(
    client_with_graph: tuple[TestClient, MockGraph, dict[str, str]]
) -> None:
    client, graph, headers = client_with_graph

    graph.add_node("visible", {"type": "Document"})
    graph.add_node("hidden", {"type": "Document"})
    graph.add_node("viewer", {"type": "User"})
    graph.add_node("other", {"type": "User"})
    graph.add_edge("visible", "viewer", "OWNED_BY", {"permission_level": "viewer"})
    graph.add_edge("hidden", "other", "OWNED_BY", {"permission_level": "editor"})
    graph.add_edge("visible", "hidden", "RELATES_TO")

    params = {"user_id": "viewer"}
    response = client.post(
        "/analytics/subgraph",
        json={"start": "visible", "depth": 1},
        headers=headers,
        params=params,
    )
    assert response.status_code == 200
    payload = response.json()
    assert set(payload["nodes"].keys()) == {"visible"}
    assert payload["edges"] == []


def _issue_token(client: TestClient) -> dict[str, str]:
    token_res = client.post(
        "/auth/token",
        data={
            "username": settings.UME_OAUTH_USERNAME,
            "password": settings.UME_OAUTH_PASSWORD,
        },
    )
    token_res.raise_for_status()
    token = token_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_mutation_endpoints_match_events_graph_results() -> None:
    conv_graph = MockGraph()
    evt_graph = MockGraph()
    conv_client: TestClient | None = None
    evt_client: TestClient | None = None
    try:
        configure_graph(conv_graph)
        conv_client = TestClient(app)
        conv_headers = _issue_token(conv_client)

        conv_graph.add_node("doc", {"type": "Document"})
        conv_graph.add_node("owner", {"type": "User"})
        conv_graph.add_node("team", {"type": "UserGroup"})
        conv_graph.add_edge("doc", "owner", "OWNED_BY", {"permission_level": "editor"})
        params = {"user_id": "owner"}

        assert conv_client.post(
            "/nodes", json={"id": "draft", "attributes": {"title": "t1"}}, headers=conv_headers, params=params
        ).status_code == 200
        assert conv_client.patch(
            "/nodes/draft", json={"attributes": {"title": "t2"}}, headers=conv_headers, params=params
        ).status_code == 200
        assert conv_client.post(
            "/edges",
            json={
                "source": "doc",
                "target": "team",
                "label": "SHARED_WITH",
                "attrs": {"permission_level": "viewer"},
            },
            headers=conv_headers,
            params=params,
        ).status_code == 200
        assert conv_client.post(
            "/redact/edge",
            json={"source": "doc", "target": "team", "label": "SHARED_WITH"},
            headers=conv_headers,
            params=params,
        ).status_code == 200
        assert conv_client.post(
            "/redact/node/draft", headers=conv_headers, params=params
        ).status_code == 200

        conv_dump = conv_graph.dump()

        configure_graph(evt_graph)
        evt_client = TestClient(app)
        evt_headers = _issue_token(evt_client)

        evt_graph.add_node("doc", {"type": "Document"})
        evt_graph.add_node("owner", {"type": "User"})
        evt_graph.add_node("team", {"type": "UserGroup"})
        evt_graph.add_edge("doc", "owner", "OWNED_BY", {"permission_level": "editor"})

        events = [
            {
                "eventType": "CREATE_NODE",
                "timestamp": 1700000000,
                "node_id": "draft",
                "payload": {"node_id": "draft", "attributes": {"title": "t1"}},
            },
            {
                "eventType": "UPDATE_NODE_ATTRIBUTES",
                "timestamp": 1700000001,
                "node_id": "draft",
                "payload": {"node_id": "draft", "attributes": {"title": "t2"}},
            },
            {
                "eventType": "CREATE_EDGE",
                "timestamp": 1700000002,
                "node_id": "doc",
                "target_node_id": "team",
                "label": "SHARED_WITH",
                "payload": {
                    "source_node_id": "doc",
                    "target_node_id": "team",
                    "label": "SHARED_WITH",
                    "attributes": {"permission_level": "viewer"},
                },
            },
            {
                "eventType": "REDACT_EDGE",
                "timestamp": 1700000003,
                "node_id": "doc",
                "target_node_id": "team",
                "label": "SHARED_WITH",
                "payload": {
                    "source_node_id": "doc",
                    "target_node_id": "team",
                    "label": "SHARED_WITH",
                },
            },
            {
                "eventType": "REDACT_NODE",
                "timestamp": 1700000004,
                "node_id": "draft",
                "payload": {"node_id": "draft"},
            },
        ]
        for event in events:
            assert evt_client.post("/events", json=event, headers=evt_headers).status_code == 200

        evt_dump = evt_graph.dump()
        assert conv_dump == evt_dump
    finally:
        with TOKENS_LOCK:
            TOKENS.clear()
        if conv_client is not None:
            conv_client.close()
        if evt_client is not None:
            evt_client.close()


def test_mutation_endpoints_match_events_policy_behavior(
    client_with_graph: tuple[TestClient, MockGraph, dict[str, str]],
) -> None:
    client, _, headers = client_with_graph

    convenience = client.post(
        "/nodes",
        json={"id": "forbidden", "attributes": {"type": "Document"}},
        headers=headers,
        params={"user_id": "owner"},
    )
    assert convenience.status_code == 400

    event = client.post(
        "/events",
        json={
            "eventType": "CREATE_NODE",
            "timestamp": 1700000000,
            "node_id": "forbidden",
            "payload": {"node_id": "forbidden", "attributes": {"type": "Document"}},
        },
        headers=headers,
    )
    assert event.status_code == 400
    assert convenience.json()["detail"] == event.json()["detail"]
