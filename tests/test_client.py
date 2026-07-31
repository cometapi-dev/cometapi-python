from __future__ import annotations

import inspect
import logging
from typing import Literal

import httpx
import pytest
from openai import AuthenticationError, OpenAIError

import cometapi
from cometapi import AsyncCometAPI, CometAPI
from cometapi._config import DEFAULT_BASE_URL
from scripts._checks import read_project_version

from .conftest import (
    API_KEY,
    BASE_URL,
    ContractRouter,
    async_http_client,
    sync_http_client,
)


def test_public_api_exports_only_accepted_client_names() -> None:
    assert cometapi.__version__ == read_project_version()
    assert cometapi.__all__ == ["AsyncCometAPI", "CometAPI", "__version__"]
    assert cometapi.CometAPI is CometAPI
    assert cometapi.AsyncCometAPI is AsyncCometAPI
    assert not hasattr(cometapi, "CometClient")
    assert not hasattr(cometapi, "AsyncCometClient")


@pytest.mark.parametrize("client_type", [CometAPI, AsyncCometAPI])
def test_missing_key_raises_official_error_without_secret(
    client_type: type[CometAPI] | type[AsyncCometAPI],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("COMETAPI_KEY", raising=False)
    with pytest.raises(OpenAIError) as caught:
        client_type()

    message = str(caught.value)
    assert "COMETAPI_KEY" in message
    assert "Bearer" not in message


@pytest.mark.parametrize("client_type", [CometAPI, AsyncCometAPI])
@pytest.mark.parametrize("api_key", ["", "   ", "\ufeff", " \ufeff\t"])
def test_explicit_blank_key_does_not_fall_back_to_environment(
    client_type: type[CometAPI] | type[AsyncCometAPI],
    api_key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMETAPI_KEY", "environment-key")
    with pytest.raises(OpenAIError) as caught:
        client_type(api_key=api_key)

    assert "environment-key" not in str(caught.value)
    assert "environment-key" not in repr(caught.value)


@pytest.mark.parametrize("client_type", [CometAPI, AsyncCometAPI])
@pytest.mark.parametrize("environment_key", [" \t ", "\ufeff", " \ufeff\t"])
def test_whitespace_environment_key_is_treated_as_missing(
    client_type: type[CometAPI] | type[AsyncCometAPI],
    environment_key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMETAPI_KEY", environment_key)
    monkeypatch.setenv("OPENAI_API_KEY", "upstream-environment-key")

    with pytest.raises(OpenAIError) as caught:
        client_type()

    message = str(caught.value)
    assert "COMETAPI_KEY" in message
    assert "upstream-environment-key" not in message


def test_explicit_sync_key_takes_precedence_over_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMETAPI_KEY", "environment-key")
    router = ContractRouter()
    http_client = sync_http_client(router)

    with CometAPI(api_key=API_KEY, base_url=BASE_URL, http_client=http_client) as client:
        client.models.list()

    assert router.requests[0].headers["authorization"] == f"Bearer {API_KEY}"


def test_explicit_sync_key_is_trimmed() -> None:
    router = ContractRouter()
    http_client = sync_http_client(router)

    with CometAPI(
        api_key=f" \ufeff{API_KEY}\ufeff\t",
        base_url=BASE_URL,
        http_client=http_client,
    ) as client:
        client.models.list()

    assert router.requests[0].headers["authorization"] == f"Bearer {API_KEY}"


@pytest.mark.asyncio
async def test_explicit_async_key_takes_precedence_over_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMETAPI_KEY", "environment-key")
    router = ContractRouter()
    http_client = async_http_client(router)

    async with AsyncCometAPI(
        api_key=API_KEY,
        base_url=BASE_URL,
        http_client=http_client,
    ) as client:
        await client.models.list()

    assert router.requests[0].headers["authorization"] == f"Bearer {API_KEY}"


@pytest.mark.asyncio
async def test_explicit_async_key_is_trimmed() -> None:
    router = ContractRouter()
    http_client = async_http_client(router)

    async with AsyncCometAPI(
        api_key=f" \ufeff{API_KEY}\ufeff\t",
        base_url=BASE_URL,
        http_client=http_client,
    ) as client:
        await client.models.list()

    assert router.requests[0].headers["authorization"] == f"Bearer {API_KEY}"


def test_sync_environment_key_is_used_when_key_is_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMETAPI_KEY", f"  {API_KEY}\t")
    router = ContractRouter()
    http_client = sync_http_client(router)

    with CometAPI(base_url=BASE_URL, http_client=http_client) as client:
        client.models.list()

    assert router.requests[0].headers["authorization"] == f"Bearer {API_KEY}"


@pytest.mark.asyncio
async def test_async_environment_key_is_used_when_key_is_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMETAPI_KEY", f"  {API_KEY}\t")
    router = ContractRouter()
    http_client = async_http_client(router)

    async with AsyncCometAPI(base_url=BASE_URL, http_client=http_client) as client:
        await client.models.list()

    assert router.requests[0].headers["authorization"] == f"Bearer {API_KEY}"


def test_explicit_base_url_takes_precedence_over_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMETAPI_BASE_URL", "https://environment.example.test/v1")
    client = CometAPI(api_key=API_KEY, base_url=httpx.URL(BASE_URL))
    try:
        assert str(client.base_url) == f"{BASE_URL}/"
    finally:
        client.close()


@pytest.mark.parametrize("client_type", [CometAPI, AsyncCometAPI])
@pytest.mark.parametrize("base_url", ["", "   ", "\ufeff", " \ufeff\t"])
def test_explicit_blank_base_url_does_not_fall_back_to_environment(
    client_type: type[CometAPI] | type[AsyncCometAPI],
    base_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMETAPI_BASE_URL", "https://environment.example.test/v1")

    with pytest.raises(OpenAIError, match="base_url"):
        client_type(api_key=API_KEY, base_url=base_url)


def test_explicit_sync_string_base_url_is_trimmed() -> None:
    client = CometAPI(api_key=API_KEY, base_url=f" \ufeff{BASE_URL}\ufeff\t")
    try:
        assert str(client.base_url) == f"{BASE_URL}/"
    finally:
        client.close()


def test_environment_base_url_is_used_when_explicit_url_is_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment_url = "https://environment.example.test/v1"
    monkeypatch.setenv("COMETAPI_BASE_URL", f"  {environment_url}\t")
    client = CometAPI(api_key=API_KEY)
    try:
        assert str(client.base_url) == f"{environment_url}/"
    finally:
        client.close()


@pytest.mark.asyncio
async def test_async_explicit_base_url_takes_precedence_over_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMETAPI_BASE_URL", "https://environment.example.test/v1")
    client = AsyncCometAPI(api_key=API_KEY, base_url=httpx.URL(BASE_URL))
    try:
        assert str(client.base_url) == f"{BASE_URL}/"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_explicit_async_string_base_url_is_trimmed() -> None:
    client = AsyncCometAPI(api_key=API_KEY, base_url=f"  {BASE_URL}\t")
    try:
        assert str(client.base_url) == f"{BASE_URL}/"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_async_environment_base_url_is_used_when_explicit_url_is_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment_url = "https://environment.example.test/v1"
    monkeypatch.setenv("COMETAPI_BASE_URL", f"  {environment_url}\t")
    client = AsyncCometAPI(api_key=API_KEY)
    try:
        assert str(client.base_url) == f"{environment_url}/"
    finally:
        await client.close()


def test_default_base_url_is_used_when_no_override_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("COMETAPI_BASE_URL", raising=False)
    client = CometAPI(api_key=API_KEY)
    try:
        assert str(client.base_url) == f"{DEFAULT_BASE_URL}/"
    finally:
        client.close()


@pytest.mark.parametrize("environment_url", [" \t ", "\ufeff", " \ufeff\t"])
def test_whitespace_environment_base_url_uses_cometapi_default(
    environment_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMETAPI_BASE_URL", environment_url)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://upstream.example.test/v1")

    client = CometAPI(api_key=API_KEY)
    try:
        assert str(client.base_url) == f"{DEFAULT_BASE_URL}/"
    finally:
        client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("environment_url", [" \t ", "\ufeff", " \ufeff\t"])
async def test_async_whitespace_environment_base_url_uses_cometapi_default(
    environment_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMETAPI_BASE_URL", environment_url)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://upstream.example.test/v1")

    client = AsyncCometAPI(api_key=API_KEY)
    try:
        assert str(client.base_url) == f"{DEFAULT_BASE_URL}/"
    finally:
        await client.close()


def test_sync_callable_key_is_preserved() -> None:
    router = ContractRouter()
    http_client = sync_http_client(router)
    calls = 0

    def key_provider() -> str:
        nonlocal calls
        calls += 1
        return API_KEY

    with CometAPI(
        api_key=key_provider,
        base_url=BASE_URL,
        http_client=http_client,
    ) as client:
        assert calls == 0
        client.models.list()

    assert calls == 1
    assert router.requests[0].headers["authorization"] == f"Bearer {API_KEY}"


@pytest.mark.asyncio
async def test_async_callable_key_is_preserved() -> None:
    router = ContractRouter()
    http_client = async_http_client(router)
    calls = 0

    async def key_provider() -> str:
        nonlocal calls
        calls += 1
        return API_KEY

    async with AsyncCometAPI(
        api_key=key_provider,
        base_url=BASE_URL,
        http_client=http_client,
    ) as client:
        assert calls == 0
        await client.models.list()

    assert calls == 1
    assert router.requests[0].headers["authorization"] == f"Bearer {API_KEY}"


def test_sync_context_manager_closes_custom_http_client() -> None:
    router = ContractRouter()
    http_client = sync_http_client(router)

    with CometAPI(api_key=API_KEY, base_url=BASE_URL, http_client=http_client) as client:
        assert not client.is_closed()
        assert not http_client.is_closed

    assert client.is_closed()
    assert http_client.is_closed


@pytest.mark.asyncio
async def test_async_context_manager_closes_custom_http_client() -> None:
    router = ContractRouter()
    http_client = async_http_client(router)

    async with AsyncCometAPI(
        api_key=API_KEY,
        base_url=BASE_URL,
        http_client=http_client,
    ) as client:
        assert not client.is_closed()
        assert not http_client.is_closed

    assert client.is_closed()
    assert http_client.is_closed


@pytest.mark.parametrize("operation", ["chat", "responses", "models"])
def test_sync_timeout_headers_query_and_http_client_are_forwarded(
    operation: Literal["chat", "responses", "models"],
) -> None:
    router = ContractRouter()
    http_client = sync_http_client(router)

    with CometAPI(
        api_key=API_KEY,
        base_url=BASE_URL,
        organization="org-contract",
        project="project-contract",
        timeout=3.25,
        max_retries=0,
        websocket_base_url="wss://gateway.example.test/v1/realtime",
        default_headers={"x-contract": "forwarded"},
        default_query={"tenant": "contract"},
        http_client=http_client,
    ) as client:
        if operation == "chat":
            client.chat.completions.create(
                model="gpt-5.6-sol",
                messages=[{"role": "user", "content": "ping"}],
            )
        elif operation == "responses":
            client.responses.create(model="gpt-5.6-sol", input="ping")
        else:
            client.models.list()
        assert client.timeout == 3.25
        assert client.max_retries == 0
        assert str(client.websocket_base_url) == "wss://gateway.example.test/v1/realtime"

    request = router.requests[0]
    assert request.headers["openai-organization"] == "org-contract"
    assert request.headers["openai-project"] == "project-contract"
    assert request.headers["x-contract"] == "forwarded"
    assert request.url.params["tenant"] == "contract"
    assert request.extensions["timeout"] == {
        "connect": 3.25,
        "read": 3.25,
        "write": 3.25,
        "pool": 3.25,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["chat", "responses", "models"])
async def test_async_timeout_headers_query_and_http_client_are_forwarded(
    operation: Literal["chat", "responses", "models"],
) -> None:
    router = ContractRouter()
    http_client = async_http_client(router)

    async with AsyncCometAPI(
        api_key=API_KEY,
        base_url=BASE_URL,
        organization="org-contract",
        project="project-contract",
        timeout=4.5,
        max_retries=0,
        websocket_base_url="wss://gateway.example.test/v1/realtime",
        default_headers={"x-contract": "forwarded"},
        default_query={"tenant": "contract"},
        http_client=http_client,
    ) as client:
        if operation == "chat":
            await client.chat.completions.create(
                model="gpt-5.6-sol",
                messages=[{"role": "user", "content": "ping"}],
            )
        elif operation == "responses":
            await client.responses.create(model="gpt-5.6-sol", input="ping")
        else:
            await client.models.list()
        assert client.timeout == 4.5
        assert client.max_retries == 0
        assert str(client.websocket_base_url) == "wss://gateway.example.test/v1/realtime"

    request = router.requests[0]
    assert request.headers["openai-organization"] == "org-contract"
    assert request.headers["openai-project"] == "project-contract"
    assert request.headers["x-contract"] == "forwarded"
    assert request.url.params["tenant"] == "contract"
    assert request.extensions["timeout"] == {
        "connect": 4.5,
        "read": 4.5,
        "write": 4.5,
        "pool": 4.5,
    }


class RetryRouter(ContractRouter):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        if self.calls == 1:
            return httpx.Response(
                500,
                headers={"retry-after-ms": "0"},
                json={"error": {"message": "retry", "type": "server_error"}},
            )
        return super().__call__(request)


@pytest.mark.parametrize("operation", ["chat", "responses", "models"])
def test_sync_retry_option_is_preserved(
    operation: Literal["chat", "responses", "models"],
) -> None:
    router = RetryRouter()
    http_client = sync_http_client(router)

    with CometAPI(
        api_key=API_KEY,
        base_url=BASE_URL,
        max_retries=1,
        http_client=http_client,
    ) as client:
        if operation == "chat":
            result = client.chat.completions.create(
                model="gpt-5.6-sol",
                messages=[{"role": "user", "content": "ping"}],
            )
            assert result.id == "chatcmpl-contract"
        elif operation == "responses":
            result = client.responses.create(model="gpt-5.6-sol", input="ping")
            assert result.id == "resp-contract"
        else:
            result = client.models.list()
            assert result.data[0].id == "gpt-5.6-sol"

    assert router.calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["chat", "responses", "models"])
async def test_async_retry_option_is_preserved(
    operation: Literal["chat", "responses", "models"],
) -> None:
    router = RetryRouter()
    http_client = async_http_client(router)

    async with AsyncCometAPI(
        api_key=API_KEY,
        base_url=BASE_URL,
        max_retries=1,
        http_client=http_client,
    ) as client:
        if operation == "chat":
            result = await client.chat.completions.create(
                model="gpt-5.6-sol",
                messages=[{"role": "user", "content": "ping"}],
            )
            assert result.id == "chatcmpl-contract"
        elif operation == "responses":
            result = await client.responses.create(model="gpt-5.6-sol", input="ping")
            assert result.id == "resp-contract"
        else:
            result = await client.models.list()
            assert result.data[0].id == "gpt-5.6-sol"

    assert router.calls == 2


def unauthorized_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        401,
        json={
            "error": {
                "message": "invalid credential",
                "type": "authentication_error",
                "code": "invalid_api_key",
            }
        },
    )


@pytest.mark.parametrize("operation", ["chat", "responses", "models"])
def test_sync_official_error_identity_and_key_non_leakage(
    operation: Literal["chat", "responses", "models"],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    http_client = sync_http_client(unauthorized_handler)
    padded_key = f"  {API_KEY}\t"

    with CometAPI(
        api_key=padded_key,
        base_url=BASE_URL,
        max_retries=0,
        http_client=http_client,
    ) as client:
        assert API_KEY not in repr(client)
        assert padded_key not in repr(client)
        with pytest.raises(AuthenticationError) as caught:
            if operation == "chat":
                client.chat.completions.create(
                    model="gpt-5.6-sol",
                    messages=[{"role": "user", "content": "ping"}],
                )
            elif operation == "responses":
                client.responses.create(model="gpt-5.6-sol", input="ping")
            else:
                client.models.list()

    assert caught.value.status_code == 401
    assert API_KEY not in str(caught.value)
    assert API_KEY not in repr(caught.value)
    assert API_KEY not in caplog.text
    assert padded_key not in str(caught.value)
    assert padded_key not in repr(caught.value)
    assert padded_key not in caplog.text


@pytest.mark.parametrize("operation", ["chat", "responses", "models"])
@pytest.mark.asyncio
async def test_async_official_error_identity_and_key_non_leakage(
    operation: Literal["chat", "responses", "models"],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    http_client = async_http_client(unauthorized_handler)
    padded_key = f"  {API_KEY}\t"

    async with AsyncCometAPI(
        api_key=padded_key,
        base_url=BASE_URL,
        max_retries=0,
        http_client=http_client,
    ) as client:
        assert API_KEY not in repr(client)
        assert padded_key not in repr(client)
        with pytest.raises(AuthenticationError) as caught:
            if operation == "chat":
                await client.chat.completions.create(
                    model="gpt-5.6-sol",
                    messages=[{"role": "user", "content": "ping"}],
                )
            elif operation == "responses":
                await client.responses.create(model="gpt-5.6-sol", input="ping")
            else:
                await client.models.list()

    assert caught.value.status_code == 401
    assert API_KEY not in str(caught.value)
    assert API_KEY not in repr(caught.value)
    assert API_KEY not in caplog.text
    assert padded_key not in str(caught.value)
    assert padded_key not in repr(caught.value)
    assert padded_key not in caplog.text


def test_constructor_forwards_additional_public_openai_options() -> None:
    def key_provider() -> str:
        return API_KEY

    client = CometAPI(
        api_key=key_provider,
        base_url=BASE_URL,
        admin_api_key="admin-contract",
        organization="org-contract",
        project="project-contract",
        webhook_secret="webhook-contract",
    )
    try:
        assert client.organization == "org-contract"
        assert client.project == "project-contract"
        assert client.admin_api_key == "admin-contract"
        assert client.webhook_secret == "webhook-contract"
    finally:
        client.close()


@pytest.mark.asyncio
async def test_async_constructor_forwards_additional_public_openai_options() -> None:
    async def key_provider() -> str:
        return API_KEY

    client = AsyncCometAPI(
        api_key=key_provider,
        base_url=BASE_URL,
        admin_api_key="admin-contract",
        organization="org-contract",
        project="project-contract",
        webhook_secret="webhook-contract",
    )
    try:
        assert client.organization == "org-contract"
        assert client.project == "project-contract"
        assert client.admin_api_key == "admin-contract"
        assert client.webhook_secret == "webhook-contract"
    finally:
        await client.close()


@pytest.mark.parametrize("client_type", [CometAPI, AsyncCometAPI])
def test_public_constructor_signature_is_explicit_and_keyword_only(
    client_type: type[CometAPI] | type[AsyncCometAPI],
) -> None:
    parameters = list(inspect.signature(client_type.__init__).parameters.values())
    assert [parameter.name for parameter in parameters] == [
        "self",
        "api_key",
        "admin_api_key",
        "organization",
        "project",
        "webhook_secret",
        "base_url",
        "websocket_base_url",
        "timeout",
        "max_retries",
        "default_headers",
        "default_query",
        "http_client",
    ]
    assert parameters[0].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert all(parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in parameters[1:])
    assert all(parameter.kind is not inspect.Parameter.VAR_KEYWORD for parameter in parameters)
    assert "Any" not in repr(client_type.__init__.__annotations__)


@pytest.mark.parametrize("client_type", [CometAPI, AsyncCometAPI])
@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("_strict_response_validation", True),
        ("_enforce_credentials", False),
        ("provider", object()),
        (
            "workload_identity",
            {
                "identity_provider_id": "provider",
                "service_account_id": "service-account",
                "provider": {"token_type": "jwt", "get_token": lambda: "token"},
            },
        ),
        ("base_urll", BASE_URL),
    ],
)
def test_public_constructor_rejects_private_or_route_bypassing_options(
    client_type: type[CometAPI] | type[AsyncCometAPI],
    option: str,
    value: object,
) -> None:
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        client_type(api_key=API_KEY, **{option: value})  # pyright: ignore[reportArgumentType]


COPY_BYPASS_OPTIONS = [
    ("provider", object()),
    (
        "workload_identity",
        {
            "identity_provider_id": "provider",
            "service_account_id": "service-account",
            "provider": {"token_type": "jwt", "get_token": lambda: "token"},
        },
    ),
    ("_enforce_credentials", False),
    ("_extra_kwargs", {"provider": object()}),
]


@pytest.mark.parametrize("method_name", ["copy", "with_options"])
@pytest.mark.parametrize(("option", "value"), COPY_BYPASS_OPTIONS)
def test_sync_inherited_copy_options_cannot_bypass_cometapi_boundaries(
    method_name: str,
    option: str,
    value: object,
) -> None:
    client = CometAPI(api_key=API_KEY, base_url=BASE_URL)
    try:
        method = client.copy if method_name == "copy" else client.with_options
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            method(**{option: value})  # pyright: ignore[reportArgumentType]
        assert client.api_key == API_KEY
        assert str(client.base_url) == f"{BASE_URL}/"
    finally:
        client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("method_name", ["copy", "with_options"])
@pytest.mark.parametrize(("option", "value"), COPY_BYPASS_OPTIONS)
async def test_async_inherited_copy_options_cannot_bypass_cometapi_boundaries(
    method_name: str,
    option: str,
    value: object,
) -> None:
    client = AsyncCometAPI(api_key=API_KEY, base_url=BASE_URL)
    try:
        method = client.copy if method_name == "copy" else client.with_options
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            method(**{option: value})  # pyright: ignore[reportArgumentType]
        assert client.api_key == API_KEY
        assert str(client.base_url) == f"{BASE_URL}/"
    finally:
        await client.close()
