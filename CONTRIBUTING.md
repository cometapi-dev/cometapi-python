# Contributing to the CometAPI Python SDK

Thank you for helping improve the SDK. The repository targets the stable 0.1
contract. Contributions must stay within the supported 0.1 scope described in
`README.md`, `ROADMAP.md`, and `COMPATIBILITY.md`. The canonical repository is
<https://github.com/cometapi-dev/cometapi-python>.

## Development setup

Install `uv`, clone the repository, and run from its root:

```bash
uv sync --locked
```

The checkout must not depend on files outside the repository root, a sibling
SDK, private backend source, or uncommitted generated artifact.

## Required local checks

Before submitting a change, run:

```bash
uv lock --check
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run pyright
uv run pytest -m "not live"
uv run python scripts/check_version.py --require-changelog --require-public-preview-docs
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

`scripts/run_actionlint.py` downloads and checksum-verifies `actionlint`
1.7.12 when it is not cached. A passing static workflow check does not mean the
workflow has run successfully on GitHub.

If a check is unavailable, say so in the pull request rather than describing
it as passing.

## Tests

Every supported operation needs mocked contract coverage for:

- HTTP method and resolved URL;
- authentication and secret non-disclosure;
- request serialization and response deserialization;
- synchronous and asynchronous lifecycle and closing;
- streaming where supported;
- timeout and retry option forwarding; and
- official OpenAI response, stream, and exception identity.

Pull-request tests must not require `COMETAPI_KEY` or contact the live service.
Keep live tests in the separately gated trusted workflow.

## Scope and design

Keep the client a thin adapter over the official OpenAI Python SDK. Do not
reimplement HTTP, SSE, retries, timeouts, protocol models, or error types. Do
not add Anthropic, Gemini, account resources, media APIs, CLI behavior, or
legacy client aliases to a 0.1 change.

Prefer the smallest complete change. Preserve precise type hints, update
documentation and the compatibility matrix when public behavior changes, and
add a changelog entry for user-visible changes.

## Commit and pull-request guidance

Use Conventional Commit subjects where practical, for example:

```text
feat: add a supported client option
fix: preserve an upstream error type
docs: clarify installation
test: cover async response streaming
```

Pull requests should explain:

- the user-visible problem and chosen solution;
- the supported operation or repository gate affected;
- exact checks run and their results;
- checks skipped or unavailable; and
- any compatibility, security, or release impact.

Never include credentials, production responses, customer data, or private
service details in a commit, fixture, log, screenshot, or issue.

## Documentation

Repository documentation is written in English. Examples use supported model
IDs and must describe shipped behavior rather than planned behavior. Keep the
canonical repository URLs, CometAPI authorship, copyright, and support and
security contacts aligned with `AGENTS.md`.

## Conduct and license

Participation is governed by `CODE_OF_CONDUCT.md`. Contributions are licensed
under the MIT license in `LICENSE`.
