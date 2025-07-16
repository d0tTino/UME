import httpx
import pytest

from ume.integrations import BaseClient, LangGraph, Letta, MemGPT, SuperMemory, IntegrationError

respx = pytest.importorskip("respx")


def test_base_client_forwards() -> None:
    client = BaseClient(base_url="http://ume", api_key="dummy-token")  # pragma: allowlist secret
    with respx.mock(assert_all_called=True) as mock:
        evt = mock.post("http://ume/events").mock(return_value=httpx.Response(200))
        recall = mock.get("http://ume/recall").mock(return_value=httpx.Response(200, json={"ok": True}))
        client.send_events([{"foo": "bar"}])
        result = client.recall({"node_id": "n1"})
        assert evt.called
        assert recall.called
        assert result == {"ok": True}
        assert dict(recall.calls.last.request.url.params) == {"node_id": "n1"}


def test_langgraph_wrapper_forwards() -> None:
    client = LangGraph(base_url="http://ume", api_key="dummy-token")  # pragma: allowlist secret
    assert isinstance(client, BaseClient)
    with respx.mock(assert_all_called=True) as mock:
        evt = mock.post("http://ume/events").mock(return_value=httpx.Response(200))
        recall = mock.get("http://ume/recall").mock(return_value=httpx.Response(200, json={"ok": True}))
        client.send_events([{"foo": "bar"}])
        result = client.recall({"node_id": "n1"})
        assert evt.called
        assert recall.called
        assert result == {"ok": True}
        assert dict(recall.calls.last.request.url.params) == {"node_id": "n1"}


def test_letta_wrapper_forwards() -> None:
    client = Letta(base_url="http://ume")
    assert isinstance(client, BaseClient)
    with respx.mock(assert_all_called=True) as mock:
        evt = mock.post("http://ume/events").mock(return_value=httpx.Response(200))
        recall = mock.get("http://ume/recall").mock(return_value=httpx.Response(200, json={"id": 1}))
        client.send_events([{"foo": 1}])
        result = client.recall({"id": 1})
        assert evt.called
        assert recall.called
        assert result == {"id": 1}
        assert dict(recall.calls.last.request.url.params) == {"id": "1"}


def test_memgpt_wrapper_forwards() -> None:
    client = MemGPT(base_url="http://ume")
    assert isinstance(client, BaseClient)
    with respx.mock(assert_all_called=True) as mock:
        evt = mock.post("http://ume/events").mock(return_value=httpx.Response(200))
        recall = mock.get("http://ume/recall").mock(return_value=httpx.Response(200, json={"id": 2}))
        client.send_events([{"foo": 2}])
        result = client.recall({"id": 2})
        assert evt.called
        assert recall.called
        assert result == {"id": 2}
        assert dict(recall.calls.last.request.url.params) == {"id": "2"}


def test_supermemory_wrapper_forwards() -> None:
    client = SuperMemory(base_url="http://ume")
    assert isinstance(client, BaseClient)
    with respx.mock(assert_all_called=True) as mock:
        evt = mock.post("http://ume/events").mock(return_value=httpx.Response(200))
        recall = mock.get("http://ume/recall").mock(return_value=httpx.Response(200, json={"result": 3}))
        client.send_events([{"foo": 3}])
        result = client.recall({"result": 3})
        assert evt.called
        assert recall.called
        assert result == {"result": 3}
        assert dict(recall.calls.last.request.url.params) == {"result": "3"}


def test_wrapper_batch_endpoint() -> None:
    client = LangGraph(base_url="http://ume")
    assert isinstance(client, BaseClient)
    with respx.mock(assert_all_called=True) as mock:
        batch = mock.post("http://ume/events/batch").mock(return_value=httpx.Response(200))
        client.send_events([{"foo": "a"}, {"foo": "b"}])
        assert batch.called


def test_store_events_alias() -> None:
    client = BaseClient(base_url="http://ume")
    with respx.mock(assert_all_called=True) as mock:
        evt = mock.post("http://ume/store").mock(return_value=httpx.Response(200))
        client.store_events([{"foo": "bar"}])
        assert evt.called


def test_env_token(monkeypatch) -> None:
    monkeypatch.setenv("UME_API_TOKEN", "token")
    client = BaseClient(base_url="http://ume")
    with respx.mock(assert_all_called=True) as mock:
        evt = mock.post("http://ume/events").mock(return_value=httpx.Response(200))
        client.send_events([{"foo": "bar"}])
        assert evt.calls.last.request.headers["Authorization"] == "Bearer token"


def test_error_handling() -> None:
    client = LangGraph(base_url="http://ume")
    with respx.mock(assert_all_called=True) as mock:
        mock.post("http://ume/events").mock(return_value=httpx.Response(500))
        with pytest.raises(IntegrationError):
            client.send_events([{"foo": "bar"}])
