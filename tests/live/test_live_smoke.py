"""Trusted, explicitly authorized low-cost CometAPI compatibility smoke."""

from __future__ import annotations

import os

import pytest

from cometapi import CometAPI

DEFAULT_LIVE_MODEL = "gpt-5.4"


def resolve_live_model(value: str | None) -> str:
    return value or DEFAULT_LIVE_MODEL


def _required_int(name: str) -> int:
    value = os.environ.get(name)
    if value is None:
        pytest.fail(f"trusted live configuration is missing {name}")
    try:
        return int(value)
    except ValueError:
        pytest.fail(f"trusted live configuration {name} must be an integer")


@pytest.mark.live
def test_bounded_chat_and_responses_modes() -> None:
    """Use four sequential requests and stop immediately on any failure."""
    if os.environ.get("COMETAPI_LIVE_RUN") != "1":
        pytest.skip("live smoke requires the trusted workflow opt-in")
    if not os.environ.get("COMETAPI_KEY"):
        pytest.fail("trusted live smoke requires an owner-authorized COMETAPI_KEY")

    request_limit = _required_int("COMETAPI_LIVE_MAX_REQUESTS")
    token_limit = _required_int("COMETAPI_LIVE_MAX_OUTPUT_TOKENS")
    timeout = _required_int("COMETAPI_LIVE_REQUEST_TIMEOUT_SECONDS")
    concurrency = _required_int("COMETAPI_LIVE_CONCURRENCY")
    stop_on_failure = _required_int("COMETAPI_LIVE_STOP_ON_FAILURE")
    model = resolve_live_model(os.environ.get("COMETAPI_LIVE_MODEL"))

    assert request_limit == 4, "the complete live matrix requires exactly four requests"
    assert 1 <= token_limit <= 16
    assert 1 <= timeout <= 30
    assert concurrency == 1
    assert stop_on_failure == 1
    assert model == DEFAULT_LIVE_MODEL

    requests_used = 0
    prompt = "Reply with only the word OK."
    with CometAPI(timeout=float(timeout), max_retries=0) as client:
        requests_used += 1
        chat = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=token_limit,
        )
        assert chat.choices and chat.choices[0].message.content

        requests_used += 1
        chat_stream = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=token_limit,
            stream=True,
        )
        assert any(chunk.choices for chunk in chat_stream)

        requests_used += 1
        response = client.responses.create(
            model=model,
            input=prompt,
            max_output_tokens=token_limit,
        )
        assert response.id

        requests_used += 1
        response_stream = client.responses.create(
            model=model,
            input=prompt,
            max_output_tokens=token_limit,
            stream=True,
        )
        assert any(event.type == "response.completed" for event in response_stream)

    assert requests_used == request_limit
