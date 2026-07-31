from __future__ import annotations

import httpx
import pytest
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
)
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai.types.responses import (
    Response,
    ResponseCompletedEvent,
    ResponseIncompleteEvent,
    ResponseStreamEvent,
    ResponseTextDeltaEvent,
)

from tests.live.test_live_smoke import (
    LiveSmokeFailure,
    OutputLimitExhausted,
    classify_transport_failure,
    validate_chat_completion,
    validate_chat_stream,
    validate_response,
    validate_response_stream,
)


def _chat(
    *,
    text: str | None = "OK",
    finish_reason: str | None = "stop",
    extra_choices: list[dict[str, object]] | None = None,
) -> ChatCompletion:
    choices: list[dict[str, object]] = [
        {
            "index": 0,
            "message": {"role": "assistant", "content": text},
            "finish_reason": finish_reason,
        }
    ]
    choices.extend(extra_choices or [])
    return ChatCompletion.model_validate(
        {
            "id": "chatcmpl-live-validation",
            "object": "chat.completion",
            "created": 1,
            "model": "gpt-5.6-sol",
            "choices": choices,
        }
    )


def _chat_chunk(
    *, text: str | None = None, finish_reason: str | None = None, index: int = 0
) -> ChatCompletionChunk:
    return ChatCompletionChunk.model_validate(
        {
            "id": "chatcmpl-live-validation",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "gpt-5.6-sol",
            "choices": [
                {
                    "index": index,
                    "delta": {"content": text},
                    "finish_reason": finish_reason,
                }
            ],
        }
    )


def _response(
    *,
    text: str = "OK",
    status: str = "completed",
    incomplete_reason: str | None = None,
) -> Response:
    incomplete_details = {"reason": incomplete_reason} if incomplete_reason is not None else None
    return Response.model_validate(
        {
            "id": "resp-live-validation",
            "object": "response",
            "created_at": 1,
            "status": status,
            "incomplete_details": incomplete_details,
            "model": "gpt-5.6-sol",
            "output": [
                {
                    "id": "msg-live-validation",
                    "type": "message",
                    "status": "completed",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": text,
                            "annotations": [],
                        }
                    ],
                }
            ],
            "parallel_tool_calls": True,
            "tool_choice": "auto",
            "tools": [],
        }
    )


def _response_delta(text: str) -> ResponseTextDeltaEvent:
    return ResponseTextDeltaEvent.model_validate(
        {
            "content_index": 0,
            "delta": text,
            "item_id": "msg-live-validation",
            "logprobs": [],
            "output_index": 0,
            "sequence_number": 0,
            "type": "response.output_text.delta",
        }
    )


def _completed_event(response: Response) -> ResponseCompletedEvent:
    return ResponseCompletedEvent.model_validate(
        {"response": response, "sequence_number": 1, "type": "response.completed"}
    )


def _incomplete_event(response: Response) -> ResponseIncompleteEvent:
    return ResponseIncompleteEvent.model_validate(
        {"response": response, "sequence_number": 1, "type": "response.incomplete"}
    )


def test_chat_completion_requires_meaningful_text_and_stop() -> None:
    validate_chat_completion(_chat())

    with pytest.raises(LiveSmokeFailure, match="no meaningful text"):
        validate_chat_completion(_chat(text="  "))
    with pytest.raises(LiveSmokeFailure, match=r"finish_reason=stop.*content_filter"):
        validate_chat_completion(_chat(finish_reason="content_filter"))


def test_chat_completion_classifies_only_length_as_output_exhaustion() -> None:
    with pytest.raises(OutputLimitExhausted, match=r"output-limit exhaustion.*length"):
        validate_chat_completion(_chat(text=None, finish_reason="length"))


def test_chat_completion_rejects_decoy_index_one_exhaustion() -> None:
    decoy: dict[str, object] = {
        "index": 1,
        "message": {"role": "assistant", "content": None},
        "finish_reason": "length",
    }
    with pytest.raises(LiveSmokeFailure, match=r"choice drift.*indexes=\[0, 1\]") as exc_info:
        validate_chat_completion(_chat(extra_choices=[decoy]))

    assert not isinstance(exc_info.value, OutputLimitExhausted)


def test_chat_stream_requires_text_and_one_normal_terminal_reason() -> None:
    validate_chat_stream([_chat_chunk(text="O"), _chat_chunk(text="K", finish_reason="stop")])

    with pytest.raises(LiveSmokeFailure, match="no meaningful text"):
        validate_chat_stream([_chat_chunk(text=" ", finish_reason="stop")])
    with pytest.raises(LiveSmokeFailure, match=r"terminal drift.*got \[\]"):
        validate_chat_stream([_chat_chunk(text="OK")])
    with pytest.raises(LiveSmokeFailure, match=r"terminal drift.*content_filter"):
        validate_chat_stream([_chat_chunk(text="OK", finish_reason="content_filter")])
    with pytest.raises(LiveSmokeFailure, match=r"terminal drift.*'stop', 'stop'"):
        validate_chat_stream(
            [
                _chat_chunk(text="O", finish_reason="stop"),
                _chat_chunk(text="K", finish_reason="stop"),
            ]
        )


def test_chat_stream_classifies_only_length_as_output_exhaustion() -> None:
    with pytest.raises(OutputLimitExhausted, match=r"stream output-limit exhaustion.*length"):
        validate_chat_stream([_chat_chunk(finish_reason="length")])


def test_chat_stream_rejects_decoy_index_one_exhaustion() -> None:
    with pytest.raises(LiveSmokeFailure, match=r"choice drift.*index=1") as exc_info:
        validate_chat_stream(
            [
                _chat_chunk(text="OK"),
                _chat_chunk(finish_reason="length", index=1),
            ]
        )

    assert not isinstance(exc_info.value, OutputLimitExhausted)


def test_response_requires_meaningful_text_and_completed_status() -> None:
    validate_response(_response())

    with pytest.raises(LiveSmokeFailure, match="no meaningful text"):
        validate_response(_response(text=" "))
    with pytest.raises(LiveSmokeFailure, match=r"terminal drift.*content_filter"):
        validate_response(_response(status="incomplete", incomplete_reason="content_filter"))
    with pytest.raises(LiveSmokeFailure, match=r"terminal drift.*status='failed'"):
        validate_response(_response(status="failed"))


def test_response_classifies_only_max_output_tokens_as_output_exhaustion() -> None:
    with pytest.raises(OutputLimitExhausted, match=r"output-limit exhaustion.*max_output_tokens"):
        validate_response(_response(status="incomplete", incomplete_reason="max_output_tokens"))


def test_response_stream_requires_text_and_one_completed_terminal_event() -> None:
    response = _response()
    validate_response_stream([_response_delta("OK"), _completed_event(response)])

    with pytest.raises(LiveSmokeFailure, match="no meaningful text"):
        validate_response_stream([_response_delta(" "), _completed_event(response)])
    with pytest.raises(LiveSmokeFailure, match=r"event drift.*got 0.*observed types"):
        validate_response_stream([_response_delta("OK")])
    with pytest.raises(LiveSmokeFailure, match=r"event drift.*got 2"):
        validate_response_stream(
            [_response_delta("OK"), _completed_event(response), _completed_event(response)]
        )


def test_response_stream_distinguishes_incomplete_reasons() -> None:
    output_limited = _response(status="incomplete", incomplete_reason="max_output_tokens")
    with pytest.raises(OutputLimitExhausted, match="stream output-limit exhaustion"):
        validate_response_stream([_incomplete_event(output_limited)])

    filtered = _response(status="incomplete", incomplete_reason="content_filter")
    with pytest.raises(LiveSmokeFailure, match=r"terminal drift.*content_filter"):
        validate_response_stream([_incomplete_event(filtered)])


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            AuthenticationError(
                "bad key",
                response=httpx.Response(401, request=httpx.Request("GET", "https://example.test")),
                body=None,
            ),
            "authentication failure: HTTP 401",
        ),
        (
            NotFoundError(
                "unknown model",
                response=httpx.Response(404, request=httpx.Request("GET", "https://example.test")),
                body=None,
            ),
            "routing/model failure: HTTP 404",
        ),
        (
            BadRequestError(
                "bad route",
                response=httpx.Response(400, request=httpx.Request("GET", "https://example.test")),
                body=None,
            ),
            "routing/model failure: HTTP 400",
        ),
        (
            APIConnectionError(request=httpx.Request("GET", "https://example.test")),
            "transport connection failure",
        ),
        (
            APITimeoutError(httpx.Request("GET", "https://example.test")),
            "transport timeout",
        ),
        (ValueError("unknown event"), "unexpected API event/transport drift"),
    ],
)
def test_non_output_failures_forbid_calibration(error: Exception, message: str) -> None:
    classified = classify_transport_failure(error)
    assert isinstance(classified, LiveSmokeFailure)
    assert not isinstance(classified, OutputLimitExhausted)
    assert message in str(classified)
    assert "output-token calibration is forbidden" in str(classified)


def test_response_stream_event_fixture_stays_within_public_union() -> None:
    events: list[ResponseStreamEvent] = [_response_delta("OK"), _completed_event(_response())]
    validate_response_stream(events)
