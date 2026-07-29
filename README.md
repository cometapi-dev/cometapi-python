# CometAPI Python SDK

> **Stable release:** `0.1.1` is approved for PyPI publication.

`cometapi` is a thin Python adapter over the official OpenAI SDK for the
OpenAI-compatible CometAPI endpoint. It changes the default API key and base
URL configuration while preserving official OpenAI request, response, stream,
error, retry, timeout, proxy, and transport behavior.

## Supported 0.1 surface

| Operation | Synchronous | Asynchronous | Streaming |
| --- | --- | --- | --- |
| `chat.completions.create` | Yes | Yes | Yes |
| `responses.create` | Yes | Yes | Yes |
| `models.list` | Yes | Yes | Not applicable |

Only these operations are supported and contract-tested for 0.1. Other
resources inherited from the OpenAI client are not CometAPI support claims.
See [COMPATIBILITY.md](COMPATIBILITY.md) for the precise compatibility policy.

The package requires Python 3.10 or later and declares
`openai>=2.45.0,<3.0.0`.

Project links: [CometAPI](https://www.cometapi.com),
[API documentation](https://apidoc.cometapi.com/),
[source repository](https://github.com/cometapi-dev/cometapi-python), and
[issue tracker](https://github.com/cometapi-dev/cometapi-python/issues).

## Installation

After the protected publication workflow and public-registry verification
succeed, install the stable release from PyPI with:

```bash
python -m pip install 'cometapi==0.1.1'
```

After those gates succeed, the immutable
[GitHub release](https://github.com/cometapi-dev/cometapi-python/releases/tag/v0.1.1)
and exact [PyPI release](https://pypi.org/project/cometapi/0.1.1/) record the
published artifact.

## Authentication and configuration

Create an API key at <https://www.cometapi.com/console/token> and provide it
through the environment:

```bash
export COMETAPI_KEY="your-api-key"
```

You are responsible for all usage and charges incurred with your key. Never
commit a key, place one in an example, or include one in a bug report.

Configuration precedence is explicit constructor value, then environment
variable, then the default:

| Constructor option | Environment variable | Default |
| --- | --- | --- |
| `api_key` | `COMETAPI_KEY` | Required |
| `base_url` | `COMETAPI_BASE_URL` | `https://api.cometapi.com/v1` |

Leading and trailing whitespace is removed from string API keys and base URLs.
An explicitly blank string is invalid and never falls back to the environment
or default. A blank `COMETAPI_KEY` is treated as missing, while a blank
`COMETAPI_BASE_URL` uses the default CometAPI URL. Callable API keys and
`httpx.URL` values retain their official OpenAI behavior.

## Usage

### Chat Completions

<!-- cometapi-readme-example: sync-chat -->
```python
from cometapi import CometAPI

with CometAPI() as client:
    response = client.chat.completions.create(
        model="gpt-5.4",
        messages=[{"role": "user", "content": "Hello!"}],
    )
    print(response.choices[0].message.content)
```

Streaming uses the official OpenAI stream type:

<!-- cometapi-readme-example: sync-chat-stream -->
```python
from cometapi import CometAPI

with CometAPI() as client:
    stream = client.chat.completions.create(
        model="gpt-5.4",
        messages=[{"role": "user", "content": "Write one sentence."}],
        stream=True,
    )
    for chunk in stream:
        print(chunk.choices[0].delta.content or "", end="")
```

### Responses and Models

<!-- cometapi-readme-example: sync-responses-models -->
```python
from cometapi import CometAPI

with CometAPI() as client:
    response = client.responses.create(
        model="gpt-5.4",
        input="Explain API compatibility in one sentence.",
    )
    models = client.models.list()

print(response.output_text)
print(models.data[0].id if models.data else "No models returned")
```

### Async client

<!-- cometapi-readme-example: async-response -->
```python
import asyncio

from cometapi import AsyncCometAPI


async def main() -> None:
    async with AsyncCometAPI() as client:
        response = await client.responses.create(
            model="gpt-5.4",
            input="Say hello.",
        )
        print(response.output_text)


asyncio.run(main())
```

The constructor exposes a named, typed option set: `api_key`, `admin_api_key`,
`organization`, `project`, `webhook_secret`, `base_url`,
`websocket_base_url`, `timeout`, `max_retries`, `default_headers`,
`default_query`, and the sync or async `http_client`. Configure proxies through
that documented custom HTTP client path. OpenAI provider routing and workload
identity are deliberately excluded because they replace CometAPI routing or
authentication; private underscore-prefixed OpenAI controls and arbitrary
keywords are rejected. Inherited `copy` and `with_options` helpers are not part
of the supported 0.1 surface and cannot be used to introduce those excluded
routing or authentication options.

## Direct OpenAI interoperability

Applications may configure the official client directly when they do not need
the CometAPI-specific defaults:

```python
import os

from openai import OpenAI

client = OpenAI(
    api_key=os.environ["COMETAPI_KEY"],
    base_url="https://api.cometapi.com/v1",
)
```

This is an interoperability option, not the primary `cometapi` experience.

## Explicit non-goals for 0.1

The 0.1 release does not add Anthropic or Gemini adapters, CometAPI account or
platform resources, media APIs, provider-neutral message translation, CLI
behavior, or custom HTTP/SSE/retry implementations. There are no compatibility
aliases named `CometClient` or `AsyncCometClient`.

## Development

All commands run from this repository root:

```bash
uv sync --locked
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run pyright
uv run pytest -m "not live"
uv run python scripts/check_version.py --require-changelog
uv run python scripts/check_secrets.py
uv run python scripts/check_workflows.py
rm -rf dist
uv build
uv run twine check dist/*
uv run python scripts/check_artifacts.py dist/*
uv run python scripts/check_clean_install.py dist/*
uv run python scripts/check_repository_independence.py
uv run python scripts/run_actionlint.py
```

`actionlint` is static validation, not evidence that a workflow ran
successfully on GitHub. See [CONTRIBUTING.md](CONTRIBUTING.md) and
[RELEASING.md](RELEASING.md) for the contributor and release gates.

The scheduled/manual trusted smoke checks only the current default branch for
ongoing compatibility. It cannot validate or authorize a release. Publication
requires a separate protected live job that checks out the exact immutable
release commit after default-branch ancestry verification and must succeed
before the protected PyPI job becomes eligible.

## Support and security

Use the [issue tracker](https://github.com/cometapi-dev/cometapi-python/issues)
for reproducible SDK problems and `support@cometapi.com` for private support or
conduct reports. Use the
[private security advisory form](https://github.com/cometapi-dev/cometapi-python/security/advisories/new)
for vulnerabilities. [SUPPORT.md](SUPPORT.md) and [SECURITY.md](SECURITY.md)
define the corresponding scope and handling guidance.

## License

MIT. See [LICENSE](LICENSE).
