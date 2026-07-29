# Compatibility

## Status

This matrix defines the contract-tested 0.1 compatibility surface. Release and
live-compatibility claims require their corresponding CI, registry, and release
evidence.

## Supported operations

| Operation | Sync non-streaming | Sync streaming | Async non-streaming | Async streaming |
| --- | --- | --- | --- | --- |
| `chat.completions.create` | Supported | Supported | Supported | Supported |
| `responses.create` | Supported | Supported | Supported | Supported |
| `models.list` | Supported | Not applicable | Supported | Not applicable |

“Supported” means the operation is part of the 0.1 public contract and must
have offline mocked coverage for URL resolution, authentication, serialization,
deserialization, lifecycle, relevant streaming behavior, option forwarding,
official error identity, and credential non-disclosure.

## Inherited versus supported

`CometAPI` and `AsyncCometAPI` subclass the official OpenAI clients. Other
OpenAI resources may therefore be visible at runtime, but they are inherited
and unverified, not supported CometAPI 0.1 operations. No compatibility or live
behavior claim is made for embeddings, images, audio, video, batches,
fine-tuning, realtime, files, uploads, or other inherited resources.

The SDK preserves official OpenAI request, response, stream, and exception
types for supported operations. It also forwards documented options such as
API/admin keys, organization, project, webhook secret, timeouts, retries,
headers, query parameters, WebSocket and HTTP base URLs, and proxies through a
custom sync/async HTTP client. Provider routing, workload identity, private
upstream controls, and arbitrary keywords are outside the CometAPI constructor
contract because they bypass CometAPI routing/authentication or depend on
private upstream types.

## OpenAI dependency

The installable range is:

```text
openai>=2.45.0,<3.0.0
```

| Lane | Purpose | Required evidence |
| --- | --- | --- |
| Minimum `2.45.0` | Prove the declared lower bound | Oldest supported Python runtime |
| Locked development version | Reproducible contributor and blocking CI environment | Every blocking Python runtime |
| Latest available below `3.0.0` | Detect upstream drift | Scheduled and dependency-update canary |

The lock file is development evidence only. It does not narrow the dependency
range installed for library users.

## Python runtimes

Python 3.10 through 3.14 is the initial blocking CI target while Python 3.10
remains upstream-supported.

## Configuration compatibility

| Behavior | Contract |
| --- | --- |
| API key | Trim explicit/environment strings; explicit blank is invalid, blank `COMETAPI_KEY` is missing; required |
| Base URL | Trim explicit/environment strings; explicit blank is invalid, blank `COMETAPI_BASE_URL` uses `https://api.cometapi.com/v1` |
| Callable key and `httpx.URL` | Preserve official deferred-key and URL-object behavior unchanged |
| OpenAI options | Documented constructor options forwarded unchanged |
| Inherited copy helpers | Unsupported and fail-closed for provider, workload-identity, and private-option injection |
| Complete-key disclosure | Forbidden in CometAPI-generated errors and logs |

Applications can configure `openai.OpenAI` or `openai.AsyncOpenAI` directly
with the CometAPI base URL. That is an interoperability option, not a claim that
the `cometapi` package supports every upstream resource.

## Deferred compatibility

Anthropic Messages, Gemini text generation, CometAPI-specific resources, media
and task APIs, and provider-neutral translation are deferred. They require
their own official SDK dependencies or authoritative schemas, mocked contracts,
and authorized live evidence before entering this matrix.

## Evidence policy

Mocked contracts, runtime CI, trusted live checks, and registry artifacts are
separate evidence layers. Default-branch monitoring cannot satisfy the
exact-release live gate, and a successful upload cannot replace public
installation, import, mocked-call, digest, and provenance verification.
