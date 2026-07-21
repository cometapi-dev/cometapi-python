"""Environment-backed configuration for the public CometAPI clients."""

from __future__ import annotations

import os
from typing import TypeVar

from openai import OpenAIError

DEFAULT_BASE_URL = "https://api.cometapi.com/v1"

_T = TypeVar("_T")


def resolve_api_key(api_key: _T | None) -> _T | str:
    """Resolve an explicit API key before consulting ``COMETAPI_KEY``."""
    resolved = api_key if api_key is not None else os.environ.get("COMETAPI_KEY")
    if resolved is None or (isinstance(resolved, str) and not resolved):
        raise OpenAIError(
            "The CometAPI API key must be provided with the api_key client option "
            "or the COMETAPI_KEY environment variable."
        )
    return resolved


def resolve_base_url(base_url: _T | None) -> _T | str:
    """Resolve an explicit base URL before environment and default values."""
    if base_url is not None:
        return base_url
    return os.environ.get("COMETAPI_BASE_URL") or DEFAULT_BASE_URL
