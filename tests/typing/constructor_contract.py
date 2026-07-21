"""Static positive and negative contracts for the public constructor surface."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import httpx
from openai import Timeout

from cometapi import AsyncCometAPI, CometAPI


def valid_sync_constructor(
    key: str | Callable[[], str],
    http_client: httpx.Client,
) -> CometAPI:
    return CometAPI(
        api_key=key,
        admin_api_key="admin-key",
        organization="org-id",
        project="project-id",
        webhook_secret="webhook-secret",
        base_url=httpx.URL("https://gateway.example.invalid/v1"),
        websocket_base_url=httpx.URL("wss://gateway.example.invalid/v1/realtime"),
        timeout=Timeout(30.0),
        max_retries=1,
        default_headers={"x-contract": "typed"},
        default_query={"tenant": "typed"},
        http_client=http_client,
    )


def valid_async_constructor(
    key: str | Callable[[], Awaitable[str]],
    http_client: httpx.AsyncClient,
) -> AsyncCometAPI:
    return AsyncCometAPI(
        api_key=key,
        admin_api_key="admin-key",
        organization="org-id",
        project="project-id",
        webhook_secret="webhook-secret",
        base_url=httpx.URL("https://gateway.example.invalid/v1"),
        websocket_base_url=httpx.URL("wss://gateway.example.invalid/v1/realtime"),
        timeout=Timeout(30.0),
        max_retries=1,
        default_headers={"x-contract": "typed"},
        default_query={"tenant": "typed"},
        http_client=http_client,
    )


def rejected_constructor_options() -> None:
    CometAPI(api_key="key", _strict_response_validation=True)  # pyright: ignore[reportCallIssue]
    CometAPI(api_key="key", _enforce_credentials=False)  # pyright: ignore[reportCallIssue]
    CometAPI(api_key="key", provider=object())  # pyright: ignore[reportCallIssue]
    CometAPI(api_key="key", workload_identity={})  # pyright: ignore[reportCallIssue]
    CometAPI(api_key="key", base_urll="https://typo.invalid/v1")  # pyright: ignore[reportCallIssue]
    AsyncCometAPI(api_key="key", _strict_response_validation=True)  # pyright: ignore[reportCallIssue]
    AsyncCometAPI(api_key="key", _enforce_credentials=False)  # pyright: ignore[reportCallIssue]
    AsyncCometAPI(api_key="key", provider=object())  # pyright: ignore[reportCallIssue]
    AsyncCometAPI(api_key="key", workload_identity={})  # pyright: ignore[reportCallIssue]
    AsyncCometAPI(api_key="key", base_urll="https://typo.invalid/v1")  # pyright: ignore[reportCallIssue]
