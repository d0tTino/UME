import asyncio
import httpx
import pytest

from ume.integrations.base import AsyncBaseClient
from ume.integrations.langgraph import AsyncLangGraph
from ume.integrations.letta import AsyncLetta
from ume.integrations.memgpt import AsyncMemGPT
from ume.integrations.supermemory import AsyncSuperMemory

respx = pytest.importorskip("respx")


def test_async_base_client_forwards() -> None:
    async def runner():
        async with AsyncBaseClient(base_url="http://ume", api_key="token") as client:
            with respx.mock(assert_all_called=True) as mock:
                evt = mock.post("http://ume/events").mock(return_value=httpx.Response(200))
                recall = mock.get("http://ume/recall").mock(return_value=httpx.Response(200, json={"ok": True}))
                await client.send_events([{"foo": "bar"}])
                result = await client.recall({"node_id": "n1"})
                assert evt.called
                assert recall.called
                assert result == {"ok": True}
                assert dict(recall.calls.last.request.url.params) == {"node_id": "n1"}

    asyncio.run(runner())


def test_async_langgraph_wrapper_forwards() -> None:
    async def runner():
        async with AsyncLangGraph(base_url="http://ume", api_key="token") as client:
            assert isinstance(client, AsyncBaseClient)
            with respx.mock(assert_all_called=True) as mock:
                evt = mock.post("http://ume/events").mock(return_value=httpx.Response(200))
                recall = mock.get("http://ume/recall").mock(return_value=httpx.Response(200, json={"ok": True}))
                await client.send_events([{"foo": "bar"}])
                result = await client.recall({"node_id": "n1"})
                assert evt.called
                assert recall.called
                assert result == {"ok": True}
                assert dict(recall.calls.last.request.url.params) == {"node_id": "n1"}

    asyncio.run(runner())


def test_async_letta_wrapper_forwards() -> None:
    async def runner():
        async with AsyncLetta(base_url="http://ume") as client:
            assert isinstance(client, AsyncBaseClient)
            with respx.mock(assert_all_called=True) as mock:
                evt = mock.post("http://ume/events").mock(return_value=httpx.Response(200))
                recall = mock.get("http://ume/recall").mock(return_value=httpx.Response(200, json={"id": 1}))
                await client.send_events([{"foo": 1}])
                result = await client.recall({"id": 1})
                assert evt.called
                assert recall.called
                assert result == {"id": 1}
                assert dict(recall.calls.last.request.url.params) == {"id": "1"}

    asyncio.run(runner())


def test_async_memgpt_wrapper_forwards() -> None:
    async def runner():
        async with AsyncMemGPT(base_url="http://ume") as client:
            assert isinstance(client, AsyncBaseClient)
            with respx.mock(assert_all_called=True) as mock:
                evt = mock.post("http://ume/events").mock(return_value=httpx.Response(200))
                recall = mock.get("http://ume/recall").mock(return_value=httpx.Response(200, json={"id": 2}))
                await client.send_events([{"foo": 2}])
                result = await client.recall({"id": 2})
                assert evt.called
                assert recall.called
                assert result == {"id": 2}
                assert dict(recall.calls.last.request.url.params) == {"id": "2"}

    asyncio.run(runner())


def test_async_supermemory_wrapper_forwards() -> None:
    async def runner():
        async with AsyncSuperMemory(base_url="http://ume") as client:
            assert isinstance(client, AsyncBaseClient)
            with respx.mock(assert_all_called=True) as mock:
                evt = mock.post("http://ume/events").mock(return_value=httpx.Response(200))
                recall = mock.get("http://ume/recall").mock(return_value=httpx.Response(200, json={"result": 3}))
                await client.send_events([{"foo": 3}])
                result = await client.recall({"result": 3})
                assert evt.called
                assert recall.called
                assert result == {"result": 3}
                assert dict(recall.calls.last.request.url.params) == {"result": "3"}

    asyncio.run(runner())


def test_async_wrapper_batch_endpoint() -> None:
    async def runner():
        async with AsyncLangGraph(base_url="http://ume") as client:
            assert isinstance(client, AsyncBaseClient)
            with respx.mock(assert_all_called=True) as mock:
                batch = mock.post("http://ume/events/batch").mock(return_value=httpx.Response(200))
                await client.send_events([{"foo": "a"}, {"foo": "b"}])
                assert batch.called

    asyncio.run(runner())
