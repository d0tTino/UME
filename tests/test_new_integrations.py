import httpx
import pytest

from ume.integrations.crewai import CrewAI
from ume.integrations.autogen import AutoGen

respx = pytest.importorskip("respx")


def test_crewai_wrapper_forwards() -> None:
    client = CrewAI(base_url="http://ume")
    with respx.mock(assert_all_called=True) as mock:
        evt = mock.post("http://ume/events").mock(return_value=httpx.Response(200))
        recall = mock.get("http://ume/recall").mock(return_value=httpx.Response(200, json={"v": 1}))
        client.send_events([{"foo": 1}])
        result = client.recall({"v": 1})
        assert evt.called
        assert recall.called
        assert result == {"v": 1}
        assert dict(recall.calls.last.request.url.params) == {"v": "1"}


def test_autogen_wrapper_forwards() -> None:
    client = AutoGen(base_url="http://ume")
    with respx.mock(assert_all_called=True) as mock:
        evt = mock.post("http://ume/events").mock(return_value=httpx.Response(200))
        recall = mock.get("http://ume/recall").mock(return_value=httpx.Response(200, json={"v": 2}))
        client.send_events([{"foo": 2}])
        result = client.recall({"v": 2})
        assert evt.called
        assert recall.called
        assert result == {"v": 2}
        assert dict(recall.calls.last.request.url.params) == {"v": "2"}
