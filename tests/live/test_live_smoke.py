"""Trusted, explicitly authorized low-cost CometAPI compatibility smoke."""

from __future__ import annotations

import os
from collections.abc import Iterable
from typing import Protocol, TypeGuard

import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai.types.responses import Response, ResponseStreamEvent

from cometapi import CometAPI
from scripts._checks import CANONICAL_ACTIVE_MODEL

DEFAULT_LIVE_MODEL = CANONICAL_ACTIVE_MODEL
ALLOWED_LIVE_OUTPUT_TOKEN_LIMITS = frozenset({64, 128, 256})


class LiveSmokeFailure(AssertionError):
    """A classified live-contract failure that is safe to expose in CI."""


class OutputLimitExhausted(LiveSmokeFailure):
    """The sole live failure class that permits output-token calibration."""


class _ResponseTextDelta(Protocol):
    delta: str
    type: str


class _ResponseTerminalEvent(Protocol):
    response: Response
    type: str


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


def _is_response_text_delta(event: ResponseStreamEvent) -> TypeGuard[_ResponseTextDelta]:
    return event.type == "response.output_text.delta"


def _is_response_terminal_event(event: ResponseStreamEvent) -> TypeGuard[_ResponseTerminalEvent]:
    return event.type in {"response.completed", "response.failed", "response.incomplete"}


def _response_incomplete_reason(response: Response) -> str:
    details = response.incomplete_details
    return details.reason if details is not None and details.reason is not None else "missing"


def validate_chat_completion(chat: ChatCompletion) -> None:
    choice_indexes = [choice.index for choice in chat.choices]
    if choice_indexes != [0]:
        raise LiveSmokeFailure(
            "chat API choice drift: expected exactly one choice at index 0, "
            f"got indexes={choice_indexes!r}"
        )
    choice = chat.choices[0]
    if choice.finish_reason == "length":
        raise OutputLimitExhausted("chat output-limit exhaustion: finish_reason=length")
    if choice.finish_reason != "stop":
        raise LiveSmokeFailure(
            f"chat API terminal drift: expected finish_reason=stop, got {choice.finish_reason!r}"
        )
    if not choice.message.content or not choice.message.content.strip():
        raise LiveSmokeFailure("chat API drift: completed response has no meaningful text")


def validate_chat_stream(chunks: Iterable[ChatCompletionChunk]) -> None:
    text: list[str] = []
    terminal_reasons: list[str] = []
    for chunk in chunks:
        for choice in chunk.choices:
            if choice.index != 0:
                raise LiveSmokeFailure(
                    "chat stream API choice drift: expected only choice index 0, "
                    f"got index={choice.index!r}"
                )
            if choice.delta.content:
                text.append(choice.delta.content)
            if choice.finish_reason is not None:
                terminal_reasons.append(choice.finish_reason)
    if terminal_reasons == ["length"]:
        raise OutputLimitExhausted("chat stream output-limit exhaustion: finish_reason=length")
    if terminal_reasons != ["stop"]:
        raise LiveSmokeFailure(
            "chat stream API terminal drift: expected one finish_reason=stop, "
            f"got {terminal_reasons!r}"
        )
    if not "".join(text).strip():
        raise LiveSmokeFailure("chat stream API drift: completed stream has no meaningful text")


def validate_response(response: Response) -> None:
    if (
        response.status == "incomplete"
        and _response_incomplete_reason(response) == "max_output_tokens"
    ):
        raise OutputLimitExhausted(
            "Responses output-limit exhaustion: status=incomplete, reason=max_output_tokens"
        )
    if response.status != "completed":
        raise LiveSmokeFailure(
            "Responses API terminal drift: expected status=completed, "
            f"got status={response.status!r}, incomplete_reason="
            f"{_response_incomplete_reason(response)!r}"
        )
    if not response.output_text.strip():
        raise LiveSmokeFailure("Responses API drift: completed response has no meaningful text")


def validate_response_stream(events: Iterable[ResponseStreamEvent]) -> None:
    text: list[str] = []
    terminal_events: list[tuple[str, Response]] = []
    observed_types: list[str] = []
    for event in events:
        observed_types.append(event.type)
        if _is_response_text_delta(event):
            text.append(event.delta)
        elif _is_response_terminal_event(event):
            terminal_events.append((event.type, event.response))
    if len(terminal_events) == 1:
        event_type, terminal = terminal_events[0]
        if event_type == "response.incomplete" and (
            _response_incomplete_reason(terminal) == "max_output_tokens"
        ):
            raise OutputLimitExhausted(
                "Responses stream output-limit exhaustion: event=response.incomplete, "
                "reason=max_output_tokens"
            )
        if event_type != "response.completed" or terminal.status != "completed":
            raise LiveSmokeFailure(
                "Responses stream API terminal drift: expected response.completed with "
                f"status=completed, got event={event_type!r}, status={terminal.status!r}, "
                f"incomplete_reason={_response_incomplete_reason(terminal)!r}"
            )
    else:
        raise LiveSmokeFailure(
            "Responses stream API event drift: expected exactly one terminal event, "
            f"got {len(terminal_events)}; observed types={observed_types!r}"
        )
    if not "".join(text).strip():
        raise LiveSmokeFailure(
            "Responses stream API drift: completed stream has no meaningful text"
        )


def classify_transport_failure(error: Exception) -> LiveSmokeFailure:
    if isinstance(error, APIStatusError):
        if error.status_code in {401, 403}:
            category = "authentication"
        elif error.status_code in {400, 404, 422}:
            category = "routing/model"
        else:
            category = "API status"
        return LiveSmokeFailure(
            f"{category} failure: HTTP {error.status_code}; output-token calibration is forbidden"
        )
    if isinstance(error, APITimeoutError):
        return LiveSmokeFailure("transport timeout; output-token calibration is forbidden")
    if isinstance(error, APIConnectionError):
        return LiveSmokeFailure(
            "transport connection failure; output-token calibration is forbidden"
        )
    return LiveSmokeFailure(
        f"unexpected API event/transport drift ({type(error).__name__}); "
        "output-token calibration is forbidden"
    )


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
    assert token_limit in ALLOWED_LIVE_OUTPUT_TOKEN_LIMITS
    assert 1 <= timeout <= 30
    assert concurrency == 1
    assert stop_on_failure == 1
    assert model == DEFAULT_LIVE_MODEL

    requests_used = 0
    prompt = "Reply with only the word OK."
    try:
        with CometAPI(timeout=float(timeout), max_retries=0) as client:
            requests_used += 1
            chat = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=token_limit,
            )
            validate_chat_completion(chat)

            requests_used += 1
            chat_stream = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=token_limit,
                stream=True,
            )
            validate_chat_stream(chat_stream)

            requests_used += 1
            response = client.responses.create(
                model=model,
                input=prompt,
                max_output_tokens=token_limit,
            )
            validate_response(response)

            requests_used += 1
            response_stream = client.responses.create(
                model=model,
                input=prompt,
                max_output_tokens=token_limit,
                stream=True,
            )
            validate_response_stream(response_stream)
    except LiveSmokeFailure:
        raise
    except Exception as error:
        raise classify_transport_failure(error) from error

    assert requests_used == request_limit
