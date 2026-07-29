"""Environment-backed configuration for the public CometAPI clients."""

from __future__ import annotations

import os
from typing import TypeVar

from openai import OpenAIError

DEFAULT_BASE_URL = "https://api.cometapi.com/v1"

_T = TypeVar("_T")


def _strip_configuration_whitespace(value: str) -> str:
    start = 0
    end = len(value)
    while start < end and (value[start].isspace() or value[start] == "\ufeff"):
        start += 1
    while end > start and (value[end - 1].isspace() or value[end - 1] == "\ufeff"):
        end -= 1
    return value[start:end]


def resolve_api_key(api_key: _T | None) -> _T | str:
    """Resolve an explicit API key before consulting ``COMETAPI_KEY``."""
    if api_key is not None and not isinstance(api_key, str):
        return api_key

    resolved = api_key if api_key is not None else os.environ.get("COMETAPI_KEY")
    normalized = _strip_configuration_whitespace(resolved) if resolved is not None else ""
    if not normalized:
        raise OpenAIError(
            "The CometAPI API key must be provided with the api_key client option "
            "or the COMETAPI_KEY environment variable."
        )
    return normalized


def resolve_base_url(base_url: _T | None) -> _T | str:
    """Resolve an explicit base URL before environment and default values."""
    if base_url is not None:
        if isinstance(base_url, str):
            normalized = _strip_configuration_whitespace(base_url)
            if not normalized:
                raise OpenAIError("The CometAPI base_url client option must not be empty.")
            return normalized
        return base_url

    environment_url = os.environ.get("COMETAPI_BASE_URL")
    normalized = (
        _strip_configuration_whitespace(environment_url) if environment_url is not None else ""
    )
    return normalized or DEFAULT_BASE_URL
