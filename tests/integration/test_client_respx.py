import httpx
import pytest
from ume.integrations import (
    LangGraph,
    Letta,
    MemGPT,
    SuperMemory,
    CrewAI,
    AutoGen,
    AsyncLangGraph,
    AsyncLetta,
    AsyncMemGPT,
    AsyncSuperMemory,
    AsyncCrewAI,
    AsyncAutoGen,
    BaseClient,
    AsyncBaseClient,
)

pytestmark = pytest.mark.integration

respx = pytest.importorskip("respx")


@pytest.mark.parametrize(
    "cls",
    [LangGraph, Letta, MemGPT, SuperMemory, CrewAI, AutoGen],
)
def test_sync_client_roundtrip(cls) -> None:
    client = cls(base_url="http://ume")
    assert isinstance(client, BaseClient)
    with respx.mock(assert_all_called=True) as mock:
        evt = mock.post("http://ume/events").mock(return_value=httpx.Response(200))
        recall_route = mock.get("http://ume/recall").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client.send_events([{"foo": "bar"}])
        result = client.recall({"node_id": "n1"})
        assert evt.called
        assert recall_route.called
        assert result == {"ok": True}
        assert dict(recall_route.calls.last.request.url.params) == {"node_id": "n1"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cls",
    [
        AsyncLangGraph,
        AsyncLetta,
        AsyncMemGPT,
        AsyncSuperMemory,
        AsyncCrewAI,
        AsyncAutoGen,
    ],
)
async def test_async_client_roundtrip(cls) -> None:
    async with cls(base_url="http://ume") as client:
        assert isinstance(client, AsyncBaseClient)
        with respx.mock(assert_all_called=True) as mock:
            evt = mock.post("http://ume/events").mock(return_value=httpx.Response(200))
            recall_route = mock.get("http://ume/recall").mock(
                return_value=httpx.Response(200, json={"ok": True})
            )
            await client.send_events([{"foo": "bar"}])
            result = await client.recall({"node_id": "n1"})
            assert evt.called
            assert recall_route.called
            assert result == {"ok": True}
            assert dict(recall_route.calls.last.request.url.params) == {"node_id": "n1"}


