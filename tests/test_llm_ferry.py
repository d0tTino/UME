from ume import Event, EventType, MockGraph, apply_event_to_graph
from ume.llm_ferry import LLMFerry
from ume._internal.listeners import register_listener, unregister_listener
import pytest
import json

httpx = pytest.importorskip("httpx")

respx = pytest.importorskip("respx")


def test_llm_ferry_on_create() -> None:
    url = "https://example.com/api"
    with respx.mock(assert_all_called=True) as respx_mock:
        route = respx_mock.post(url).mock(return_value=httpx.Response(200))
        ferry = LLMFerry(api_url=url, api_key="token")
        register_listener(ferry)
        graph = MockGraph()
        event = Event(
            event_type=EventType.CREATE_NODE,
            timestamp=0,
            payload={"node_id": "n1", "attributes": {}},
        )
        apply_event_to_graph(event, graph)
        unregister_listener(ferry)

        assert route.called
        req = route.calls.last.request
        assert req.headers.get("Authorization") == "Bearer token"
        assert json.loads(req.content.decode()) == {"text": "Node created: n1 {}"}

