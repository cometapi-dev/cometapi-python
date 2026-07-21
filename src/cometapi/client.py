"""Public CometAPI clients built on the official OpenAI SDK."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING

from openai import DEFAULT_MAX_RETRIES, NOT_GIVEN, AsyncOpenAI, NotGiven, OpenAI, Timeout

from ._config import resolve_api_key, resolve_base_url

if TYPE_CHECKING:
    import httpx


class CometAPI(OpenAI):
    """Synchronous client for CometAPI's OpenAI-compatible API."""

    def __init__(
        self,
        *,
        api_key: str | Callable[[], str] | None = None,
        admin_api_key: str | None = None,
        organization: str | None = None,
        project: str | None = None,
        webhook_secret: str | None = None,
        base_url: str | httpx.URL | None = None,
        websocket_base_url: str | httpx.URL | None = None,
        timeout: float | Timeout | None | NotGiven = NOT_GIVEN,
        max_retries: int = DEFAULT_MAX_RETRIES,
        default_headers: Mapping[str, str] | None = None,
        default_query: Mapping[str, object] | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        super().__init__(
            api_key=resolve_api_key(api_key),
            admin_api_key=admin_api_key,
            organization=organization,
            project=project,
            webhook_secret=webhook_secret,
            base_url=resolve_base_url(base_url),
            websocket_base_url=websocket_base_url,
            timeout=timeout,
            max_retries=max_retries,
            default_headers=default_headers,
            default_query=default_query,
            http_client=http_client,
        )


class AsyncCometAPI(AsyncOpenAI):
    """Asynchronous client for CometAPI's OpenAI-compatible API."""

    def __init__(
        self,
        *,
        api_key: str | Callable[[], Awaitable[str]] | None = None,
        admin_api_key: str | None = None,
        organization: str | None = None,
        project: str | None = None,
        webhook_secret: str | None = None,
        base_url: str | httpx.URL | None = None,
        websocket_base_url: str | httpx.URL | None = None,
        timeout: float | Timeout | None | NotGiven = NOT_GIVEN,
        max_retries: int = DEFAULT_MAX_RETRIES,
        default_headers: Mapping[str, str] | None = None,
        default_query: Mapping[str, object] | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            api_key=resolve_api_key(api_key),
            admin_api_key=admin_api_key,
            organization=organization,
            project=project,
            webhook_secret=webhook_secret,
            base_url=resolve_base_url(base_url),
            websocket_base_url=websocket_base_url,
            timeout=timeout,
            max_retries=max_retries,
            default_headers=default_headers,
            default_query=default_query,
            http_client=http_client,
        )
