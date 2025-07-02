import pytest
from fastapi.testclient import TestClient

import importlib.util
import sys
import types
from ume.graph import MockGraph
from ume.config import settings

spec = importlib.util.spec_from_file_location("ume.api", "src/ume/api.py")
api = importlib.util.module_from_spec(spec)
sys.modules["ume.api"] = api
if "neo4j" not in sys.modules:
    neo4j_stub = types.SimpleNamespace(GraphDatabase=object, Driver=object)
    sys.modules["neo4j"] = neo4j_stub
spec.loader.exec_module(api)

app = api.app
configure_graph = api.configure_graph


@pytest.fixture
def client_and_graph():
    g = MockGraph()
    configure_graph(g)
    app.state.query_engine = type("QE", (), {"execute_cypher": lambda self, q: []})()
    return TestClient(app), g


def _token(client: TestClient) -> str:
    return client.post(
        "/auth/token",
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
