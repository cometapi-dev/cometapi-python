# Architecture

## Purpose

The CometAPI Python SDK is a deliberately thin adapter over the official OpenAI
Python SDK. Its 0.1 responsibility is configuration, not a second protocol
implementation.

```text
application
    -> CometAPI / AsyncCometAPI
        -> openai.OpenAI / openai.AsyncOpenAI
            -> https://api.cometapi.com/v1
```

## Public clients

`CometAPI` subclasses `openai.OpenAI`, and `AsyncCometAPI` subclasses
`openai.AsyncOpenAI`. The adapter supplies CometAPI defaults while forwarding
an explicit typed set of CometAPI-compatible constructor options to the
upstream client.

This preserves official OpenAI request, response, stream, error, retry,
timeout, proxy, pagination, and custom transport behavior. The SDK does not
wrap those values in CometAPI-specific protocol types.

The approved constructor surface includes API and admin keys, organization,
project, webhook secret, HTTP and WebSocket base URLs, timeout, retries,
default headers and query parameters, and sync/async custom HTTP clients.
Proxy customization uses the custom HTTP client path. Arbitrary keywords and
private underscore-prefixed upstream controls are rejected. OpenAI provider
routing and workload identity are also excluded because they replace the
CometAPI route or authentication contract and expose private upstream types.

## Configuration

Configuration follows one precedence rule:

1. explicit constructor option;
2. corresponding environment variable; and
3. documented default.

`api_key` resolves from `COMETAPI_KEY` and has no default. `base_url` resolves
from `COMETAPI_BASE_URL` and defaults to
`https://api.cometapi.com/v1`. Complete credentials must never appear in
CometAPI-generated exceptions or logs.

## Supported resource boundary

The 0.1 compatibility contract covers only:

- `chat.completions.create` in all sync, async, streaming, and non-streaming
  modes;
- `responses.create` in all sync, async, streaming, and non-streaming modes;
  and
- `models.list` in sync and async modes.

Subclassing exposes other upstream attributes at runtime, but inheritance alone
is not a support claim. A resource becomes supported only after its URL,
authentication, serialization, deserialization, lifecycle, option forwarding,
error identity, and secret behavior have contract tests and are documented in
`COMPATIBILITY.md`.

## Package layout

```text
src/cometapi/
├── __init__.py     # public exports and package version
├── _config.py      # environment names and default endpoint
├── client.py       # thin sync and async subclasses
└── py.typed         # PEP 561 marker
```

CometAPI-specific resources and Pydantic models, if later approved, belong in
separate `resources/` and `types/` packages. Provider-native adapters belong to
a later milestone and use the official provider SDKs as optional dependencies.
Empty placeholders are not part of 0.1.

Distribution `Project-URL` metadata uses HTTPS for every entry so registries
can validate and render it consistently. The Support entry links to the public
`SUPPORT.md` document; `support@cometapi.com` remains the support and conduct
contact published inside that document.

## Dependency policy

The installable OpenAI range is `openai>=2.45.0,<3.0.0`. End users resolve
within that range; `uv.lock` selects the reproducible development environment
without constraining consumers to the locked version. Direct runtime
dependencies are added only when production CometAPI source imports and owns
their use.

Compatibility evidence has three lanes:

- minimum OpenAI on the oldest supported Python runtime;
- locked OpenAI across the blocking Python runtime matrix; and
- latest OpenAI below 3.0 as a scheduled and dependency-update canary.

## Verification boundaries

Mocked contracts prove SDK construction and protocol delegation without
production credentials. Clean-install checks prove the exact wheel or source
distribution can be installed, imported, and used for an offline mocked call.
Repository-independence checks prove the public checkout does not need its
files outside the repository root.

These layers do not prove live CometAPI compatibility, GitHub Actions behavior,
registry ownership, OIDC configuration, publication, provenance, or public
installation. Each requires separate evidence described in `RELEASING.md`.

## Release trust boundary

Release evidence is intentionally ordered:

```text
local mocked/package evidence
    -> immutable tag commit equals checkout and belongs to protected default branch
    -> release API and tag ref confirm the exact immutable identity
    -> protected live-smoke job checks that exact commit
    -> protected PyPI OIDC job publishes the previously verified artifact
    -> public registry digest, provenance, install, import, and mocked smoke
```

This complete trust chain executed successfully in
[release workflow run 30261746138](https://github.com/cometapi-dev/cometapi-python/actions/runs/30261746138)
for release commit `31b68904141489ca04932edbf305ccf88af09372`, recovery tag
`v0.1.0-alpha.1+recovery.1`, and PyPI version `0.1.0a1`. The public wheel and
source distribution matched the retained pre-publication digests, Trusted
Publisher provenance was verified, and the clean registry install/import/mocked
smoke passed.

The scheduled/manual default-branch smoke is an operational canary only; it
does not prove the release commit. `COMETAPI_KEY` is exposed only to the
protected exact-release live job. OIDC permission is exposed only to the
protected publish job. Missing credentials, environments, approvals, or
remote configuration block publication.

The complete release chain has one top-level workflow identity: `publish.yml`.
It owns the gated Release Please push path and the sole manual recovery
dispatch, independently verifies either release identity, selects exactly one
successful path, and then runs the shared build, live, OIDC, provenance, and
registry jobs. The PyPI action executes directly in that file. This is a trust
boundary, not a refactoring preference: PyPI requires every uploaded
attestation's Build Config URI to match the Trusted Publisher workflow used for
the upload. Reusable publishing is unsupported by the
[PyPA action](https://github.com/pypa/gh-action-pypi-publish/issues/166), and
[Warehouse enforces the identity match](https://github.com/pypi/warehouse/issues/19814).

The recovery dispatch runs only from the protected default branch behind a
temporary tag-and-commit identity opt-in. Release verification, selection, and
every downstream release job reject rerun attempts so an old authorization
cannot be replayed through GitHub's rerun controls. The protected live job
checks its credential before checkout or any request. `scripts/check_workflows.py`
rejects split or reusable publisher identities, unverified selector inputs,
additional OIDC consumers, and missing first-attempt guards.

The initial alpha has one release-identity exception. GitHub's immutable
release tombstone permanently reserves `v0.1.0-alpha.1`, so the reviewed
recovery release uses SemVer build metadata in
`v0.1.0-alpha.1+recovery.1`. The build suffix does not change the package
artifact identity: the PyPI version remains `0.1.0a1`.

Release Please remains disabled outside an explicitly authorized release
sequence. The stable-readiness configuration used a tested `last-release-sha`
bridge to establish the recovery commit as the previous-release boundary and
generate the stable release PR without replaying earlier history. Human
finalization then removed that one-time bridge.

## Rejected 0.1 approaches

- Hand-written HTTP, SSE, retry, timeout, or protocol model layers duplicate
  the official SDK and create type-identity problems.
- Claiming every inherited method is supported confuses runtime availability
  with verified compatibility.
- Untyped account or media helpers broaden the API without stable schemas and
  task lifecycle contracts.
- Additional client aliases would expand the compatibility obligation without
  user benefit.
