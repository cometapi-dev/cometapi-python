from __future__ import annotations

import httpx
import pytest
from openai import AsyncStream, Stream
from openai.types import Model
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai.types.responses import Response, ResponseCompletedEvent

from cometapi import AsyncCometAPI, CometAPI

from .conftest import (
    API_KEY,
    BASE_URL,
    ContractRouter,
    async_http_client,
    request_json,
    sync_http_client,
)


def assert_common_request(
    request: httpx.Request,
    *,
    method: str,
    url: str,
) -> None:
    assert request.method == method
    assert str(request.url) == url
    assert request.headers["authorization"] == f"Bearer {API_KEY}"


def test_sync_chat_completion_contract() -> None:
    router = ContractRouter()
    http_client = sync_http_client(router)

    with CometAPI(api_key=API_KEY, base_url=BASE_URL, http_client=http_client) as client:
        result = client.chat.completions.create(
            model="gpt-5.4",
            messages=[{"role": "user", "content": "ping"}],
        )

    assert isinstance(result, ChatCompletion)
    assert result.choices[0].message.content == "pong"
    assert len(router.requests) == 1
    request = router.requests[0]
    assert_common_request(
        request,
        method="POST",
        url=f"{BASE_URL}/chat/completions",
    )
    assert request_json(request) == {
        "messages": [{"role": "user", "content": "ping"}],
        "model": "gpt-5.4",
    }


def test_sync_chat_completion_stream_contract() -> None:
    router = ContractRouter()
    http_client = sync_http_client(router)

    with CometAPI(api_key=API_KEY, base_url=BASE_URL, http_client=http_client) as client:
        stream = client.chat.completions.create(
            model="gpt-5.4",
            messages=[{"role": "user", "content": "ping"}],
            stream=True,
        )
        assert isinstance(stream, Stream)
        chunks = list(stream)

    assert len(chunks) == 1
    assert isinstance(chunks[0], ChatCompletionChunk)
    assert chunks[0].choices[0].delta.content == "pong"
    assert len(router.requests) == 1
    request = router.requests[0]
    assert_common_request(
        request,
        method="POST",
        url=f"{BASE_URL}/chat/completions",
    )
    assert request_json(request) == {
        "messages": [{"role": "user", "content": "ping"}],
        "model": "gpt-5.4",
        "stream": True,
    }


def test_sync_response_contract() -> None:
    router = ContractRouter()
    http_client = sync_http_client(router)

    with CometAPI(api_key=API_KEY, base_url=BASE_URL, http_client=http_client) as client:
        result = client.responses.create(model="gpt-5.4", input="ping")

    assert isinstance(result, Response)
    assert result.id == "resp-contract"
    assert len(router.requests) == 1
    request = router.requests[0]
    assert_common_request(request, method="POST", url=f"{BASE_URL}/responses")
    assert request_json(request) == {"input": "ping", "model": "gpt-5.4"}


def test_sync_response_stream_contract() -> None:
    router = ContractRouter()
    http_client = sync_http_client(router)

    with CometAPI(api_key=API_KEY, base_url=BASE_URL, http_client=http_client) as client:
        stream = client.responses.create(model="gpt-5.4", input="ping", stream=True)
        assert isinstance(stream, Stream)
        events = list(stream)

    assert len(events) == 1
    assert isinstance(events[0], ResponseCompletedEvent)
    assert events[0].response.id == "resp-contract"
    assert len(router.requests) == 1
    request = router.requests[0]
    assert_common_request(request, method="POST", url=f"{BASE_URL}/responses")
    assert request_json(request) == {
        "input": "ping",
        "model": "gpt-5.4",
        "stream": True,
    }


def test_sync_models_contract() -> None:
    router = ContractRouter()
    http_client = sync_http_client(router)

    with CometAPI(api_key=API_KEY, base_url=BASE_URL, http_client=http_client) as client:
        result = client.models.list()

    assert len(result.data) == 1
    assert isinstance(result.data[0], Model)
    assert result.data[0].id == "gpt-5.4"
    assert len(router.requests) == 1
    request = router.requests[0]
    assert_common_request(request, method="GET", url=f"{BASE_URL}/models")
    assert request.content == b""


@pytest.mark.asyncio
async def test_async_chat_completion_contract() -> None:
    router = ContractRouter()
    http_client = async_http_client(router)

    async with AsyncCometAPI(
        api_key=API_KEY,
        base_url=BASE_URL,
        http_client=http_client,
    ) as client:
        result = await client.chat.completions.create(
            model="gpt-5.4",
            messages=[{"role": "user", "content": "ping"}],
        )

    assert isinstance(result, ChatCompletion)
    assert result.choices[0].message.content == "pong"
    assert len(router.requests) == 1
    request = router.requests[0]
    assert_common_request(
        request,
        method="POST",
        url=f"{BASE_URL}/chat/completions",
    )
    assert request_json(request) == {
        "messages": [{"role": "user", "content": "ping"}],
        "model": "gpt-5.4",
    }


@pytest.mark.asyncio
async def test_async_chat_completion_stream_contract() -> None:
    router = ContractRouter()
    http_client = async_http_client(router)

    async with AsyncCometAPI(
        api_key=API_KEY,
        base_url=BASE_URL,
        http_client=http_client,
    ) as client:
        stream = await client.chat.completions.create(
            model="gpt-5.4",
            messages=[{"role": "user", "content": "ping"}],
            stream=True,
        )
        assert isinstance(stream, AsyncStream)
        chunks = [chunk async for chunk in stream]

    assert len(chunks) == 1
    assert isinstance(chunks[0], ChatCompletionChunk)
    assert chunks[0].choices[0].delta.content == "pong"
    assert len(router.requests) == 1
    request = router.requests[0]
    assert_common_request(
        request,
        method="POST",
        url=f"{BASE_URL}/chat/completions",
    )
    assert request_json(request) == {
        "messages": [{"role": "user", "content": "ping"}],
        "model": "gpt-5.4",
        "stream": True,
    }


@pytest.mark.asyncio
async def test_async_response_contract() -> None:
    router = ContractRouter()
    http_client = async_http_client(router)

    async with AsyncCometAPI(
        api_key=API_KEY,
        base_url=BASE_URL,
        http_client=http_client,
    ) as client:
        result = await client.responses.create(model="gpt-5.4", input="ping")

    assert isinstance(result, Response)
    assert result.id == "resp-contract"
    assert len(router.requests) == 1
    request = router.requests[0]
    assert_common_request(request, method="POST", url=f"{BASE_URL}/responses")
    assert request_json(request) == {"input": "ping", "model": "gpt-5.4"}


@pytest.mark.asyncio
async def test_async_response_stream_contract() -> None:
    router = ContractRouter()
    http_client = async_http_client(router)

    async with AsyncCometAPI(
        api_key=API_KEY,
        base_url=BASE_URL,
        http_client=http_client,
    ) as client:
        stream = await client.responses.create(model="gpt-5.4", input="ping", stream=True)
        assert isinstance(stream, AsyncStream)
        events = [event async for event in stream]

    assert len(events) == 1
    assert isinstance(events[0], ResponseCompletedEvent)
    assert events[0].response.id == "resp-contract"
    assert len(router.requests) == 1
    request = router.requests[0]
    assert_common_request(request, method="POST", url=f"{BASE_URL}/responses")
    assert request_json(request) == {
        "input": "ping",
        "model": "gpt-5.4",
        "stream": True,
    }


@pytest.mark.asyncio
async def test_async_models_contract() -> None:
    router = ContractRouter()
    http_client = async_http_client(router)

    async with AsyncCometAPI(
        api_key=API_KEY,
        base_url=BASE_URL,
        http_client=http_client,
    ) as client:
        result = await client.models.list()

    assert len(result.data) == 1
    assert isinstance(result.data[0], Model)
    assert result.data[0].id == "gpt-5.4"
    assert len(router.requests) == 1
    request = router.requests[0]
    assert_common_request(request, method="GET", url=f"{BASE_URL}/models")
    assert request.content == b""
