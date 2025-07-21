import asyncio
import httpx
import pytest

from ume.integrations import (
    AsyncBaseClient,
    AsyncLangGraph,
    AsyncLetta,
    AsyncMemGPT,
    AsyncSuperMemory,
    IntegrationError,
)

respx = pytest.importorskip("respx")


def test_async_base_client_forwards() -> None:
    async def runner():
        async with AsyncBaseClient(base_url="http://ume", api_key="dummy-token") as client:  # pragma: allowlist secret
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
        async with AsyncLangGraph(base_url="http://ume", api_key="dummy-token") as client:  # pragma: allowlist secret
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


def test_async_store_events_alias() -> None:
    async def runner():
        async with AsyncBaseClient(base_url="http://ume") as client:
            with respx.mock(assert_all_called=True) as mock:
                evt = mock.post("http://ume/store").mock(return_value=httpx.Response(200))
                await client.store_events([{"foo": "bar"}])
                assert evt.called

    asyncio.run(runner())


def test_async_env_token(monkeypatch) -> None:
    async def runner():
        monkeypatch.setenv("UME_API_TOKEN", "async-token")
        async with AsyncBaseClient(base_url="http://ume") as client:
            with respx.mock(assert_all_called=True) as mock:
                evt = mock.post("http://ume/events").mock(return_value=httpx.Response(200))
                await client.send_events([{"foo": "bar"}])
                assert evt.calls.last.request.headers["Authorization"] == "Bearer async-token"

    asyncio.run(runner())


def test_async_error_handling() -> None:
    async def runner():
        async with AsyncLangGraph(base_url="http://ume") as client:
            with respx.mock(assert_all_called=True) as mock:
                mock.post("http://ume/events").mock(return_value=httpx.Response(500))
                with pytest.raises(IntegrationError):
                    await client.send_events([{"foo": "bar"}])

    asyncio.run(runner())


def test_async_stream_methods() -> None:
    async def runner():
        async with AsyncBaseClient(base_url="http://ume") as client:
            stream_body = b"data: {\"id\": 1}\n\ndata: {\"id\": 2}\n\n"
            path_body = b"data: a\n\ndata: b\n\n"
            with respx.mock(assert_all_called=True) as mock:
                mock.get("http://ume/recall/stream").mock(
                    return_value=httpx.Response(200, stream=httpx.ByteStream(stream_body))
                )
                mock.get("http://ume/analytics/path/stream").mock(
                    return_value=httpx.Response(200, stream=httpx.ByteStream(path_body))
                )
                items = [i async for i in client.recall_stream({"node_id": "n1"})]
                nodes = [n async for n in client.path_stream({"source": "a", "target": "b"})]
            assert items == [{"id": 1}, {"id": 2}]
            assert nodes == ["a", "b"]

    asyncio.run(runner())
