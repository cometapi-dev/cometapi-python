from __future__ import annotations

import json
from collections.abc import Callable
from typing import cast

import httpx

API_KEY = "cometapi-contract-test-key"
BASE_URL = "https://gateway.example.test/v1"

CHAT_COMPLETION: dict[str, object] = {
    "id": "chatcmpl-contract",
    "object": "chat.completion",
    "created": 1,
    "model": "gpt-5.4",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "pong"},
            "finish_reason": "stop",
        }
    ],
}

CHAT_CHUNK: dict[str, object] = {
    "id": "chatcmpl-contract",
    "object": "chat.completion.chunk",
    "created": 1,
    "model": "gpt-5.4",
    "choices": [
        {
            "index": 0,
            "delta": {"content": "pong"},
            "finish_reason": None,
        }
    ],
}

RESPONSE: dict[str, object] = {
    "id": "resp-contract",
    "object": "response",
    "created_at": 1,
    "status": "completed",
    "model": "gpt-5.4",
    "output": [],
    "parallel_tool_calls": True,
    "tool_choice": "auto",
    "tools": [],
}

MODEL_LIST: dict[str, object] = {
    "object": "list",
    "data": [
        {
            "id": "gpt-5.4",
            "object": "model",
            "created": 1,
            "owned_by": "cometapi",
        }
    ],
}


def request_json(request: httpx.Request) -> dict[str, object]:
    if not request.content:
        return {}
    value = cast(object, json.loads(request.content))
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def chat_stream_body() -> str:
    return f"data: {json.dumps(CHAT_CHUNK)}\n\ndata: [DONE]\n\n"


def response_stream_body() -> str:
    event: dict[str, object] = {
        "type": "response.completed",
        "sequence_number": 0,
        "response": RESPONSE,
    }
    return f"event: response.completed\ndata: {json.dumps(event)}\n\n"


class ContractRouter:
    """Record requests and return deterministic OpenAI-compatible fixtures."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        body = request_json(request)

        if request.url.path.endswith("/chat/completions"):
            if body.get("stream") is True:
                return httpx.Response(
                    200,
                    text=chat_stream_body(),
                    headers={"content-type": "text/event-stream"},
                )
            return httpx.Response(200, json=CHAT_COMPLETION)

        if request.url.path.endswith("/responses"):
            if body.get("stream") is True:
                return httpx.Response(
                    200,
                    text=response_stream_body(),
                    headers={"content-type": "text/event-stream"},
                )
            return httpx.Response(200, json=RESPONSE)

        if request.url.path.endswith("/models"):
            return httpx.Response(200, json=MODEL_LIST)

        return httpx.Response(
            404,
            json={"error": {"message": "unexpected test URL", "type": "test_error"}},
        )


def sync_http_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def async_http_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))
