import httpx
import respx

from ume.classification.tino_storm import TinoStormClassifier
from ume.services import ingest_event
from ume.graph import MockGraph
from ume.classification.plugins import register_classifier


def _make_event(text: str) -> dict[str, object]:
    return {
        "event_type": "CREATE_NODE",
        "timestamp": 0,
        "node_id": "node1",
        "payload": {"node_id": "node1", "attributes": {"content": text}},
    }


def test_tino_storm_local_classification(monkeypatch) -> None:
    graph = MockGraph()
    classifier = TinoStormClassifier(base_url=None)
    register_classifier("tino_storm", classifier)
    ingest_event(_make_event("This contains a password."), graph)
    stored = graph.get_node("node1")
    assert stored["domain"] == "credentials"
    assert stored["subdomain"] == "password"
    assert stored["sensitivity"] == "high"


@respx.mock
def test_tino_storm_remote_classification(monkeypatch) -> None:
    url = "http://tino/api"
    respx.post(f"{url}/classify").mock(
        return_value=httpx.Response(
            200,
            json={
                "domain": "finance",
                "subdomain": "bank",
                "sensitivity": "high",
                "confidence": 0.9,
            },
        )
    )
    classifier = TinoStormClassifier(base_url=url)
    register_classifier("tino_storm", classifier)
    graph = MockGraph()
    ingest_event(_make_event("some text"), graph)
    stored = graph.get_node("node1")
    assert stored["domain"] == "finance"
    assert stored["subdomain"] == "bank"
    assert stored["sensitivity"] == "high"
