import pytest
from fastapi.testclient import TestClient

from ume.api import app, configure_graph
from ume import MockGraph
from ume.config import settings


@pytest.fixture
def client_and_graph():
    g = MockGraph()
    configure_graph(g)
    app.state.query_engine = type("QE", (), {"execute_cypher": lambda self, q: []})()
    return TestClient(app), g


def _token(client: TestClient) -> str:
    return client.post(
        "/token",
        data={"username": settings.UME_OAUTH_USERNAME, "password": settings.UME_OAUTH_PASSWORD},
    ).json()["access_token"]


def test_post_tweet(client_and_graph):
    client, g = client_and_graph
    token = _token(client)
    res = client.post(
        "/tweets",
        json={"text": "hello"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    tweet_id = res.json()["id"]
    assert g.get_node(tweet_id)["text"] == "hello"


def test_upload_document(client_and_graph):
    client, g = client_and_graph
    token = _token(client)
    res = client.post(
        "/documents",
        json={"content": "  line1  \n\n line2 "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    doc_id = res.json()["id"]
    assert g.get_node(doc_id)["content"] == "line1\nline2"

    res = client.get(
        f"/documents/{doc_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    assert res.json()["content"] == "line1\nline2"
