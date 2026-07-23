# CometAPI Python SDK Agent Instructions

This file is the self-contained engineering contract for the public CometAPI
Python SDK repository. Treat this directory as the repository root.

## Repository authority

Repository-local source, tests, documentation, metadata, fixtures, and workflow
definitions may be changed and verified locally. The current milestone may use
private pull requests and credential-free GitHub Actions to complete the
remaining pre-visibility work. Changing repository visibility, configuring
secrets or environments, making live API requests, creating tags or releases,
publishing to PyPI, and changing registry settings remain outside the current
authorized pre-visibility scope.

A local build, mocked test, statically valid workflow, or private remote CI run
proves only its own evidence layer. Never invent or mock missing evidence.

## Git branch lifecycle

- Use a dedicated short-lived topic branch for each task. `dev` is the clean
  local landing branch between tasks; do not commit task changes directly to
  `dev`.
- Treat a topic branch lifecycle as closed only after its required pull-request
  checks pass and its squash merge is present on `origin/main`. Any alternate
  disposition requires explicit user authorization and must not advance `dev`
  until the accepted commit is present on `origin/main`.
- With a clean worktree, fetch `origin`, switch to `main`, fast-forward it with
  `git merge --ff-only origin/main`, switch to `dev`, fast-forward it with
  `git merge --ff-only main`, and finish with `dev` checked out. Cleanup is
  complete only when the worktree is clean and local `main`, local `dev`, and
  `origin/main` resolve to the same commit.
- Never reset, discard work, force-update refs, delete branches, or push `dev`
  merely to complete this cleanup. If fetching fails, the worktree is dirty,
  either fast-forward is impossible, or the three final refs differ, stop and
  report the exact state instead of forcing synchronization.

## Current milestone: Public Preview

Private Remote Validation is complete. Prepare the private canonical repository
for a future explicitly authorized visibility change, and stop before changing
visibility. A session starting in this repository must be able to finish the
remaining pre-visibility work without instructions outside the repository.

The accepted identity is:

| Field | Value |
| --- | --- |
| Repository | `https://github.com/cometapi-dev/cometapi-python` |
| PyPI package | `cometapi` |
| Author | `CometAPI` |
| Copyright | `Copyright (c) 2026 CometAPI` |
| Homepage | `https://www.cometapi.com` |
| Documentation | `https://apidoc.cometapi.com/` |
| Issues | `https://github.com/cometapi-dev/cometapi-python/issues` |
| Support and conduct | `support@cometapi.com` |
| Security | `https://github.com/cometapi-dev/cometapi-python/security/advisories/new` |

Before changing repository visibility:

1. Resolve or explicitly defer every open dependency pull request that is not
   ready to merge. Dependabot PR #2 must not merge while its credential-free CI
   is failing; record its disposition in `ROADMAP.md`.
2. Keep `.github/CODEOWNERS` absent until a real multi-maintainer model exists.
3. Keep scheduled and manually dispatched live smoke fail-closed behind
   `LIVE_SMOKE_ENABLED=true`, and keep `RELEASE_PLEASE_ENABLED` disabled through
   the initial manual alpha.
4. Run every local offline, package, self-containment, public-content, secret,
   and workflow-static-validation gate, then deliver the pre-visibility changes
   through a private pull request with successful credential-free CI.
5. Confirm the canonical repository is still private and stop. Visibility,
   branch or tag rules, Private Vulnerability Reporting, secrets, protected
   environments, Trusted Publishing, live API calls, tags, releases, and
   publication require separate authorization after this stop point.

## Repository independence

- Never depend on files outside this repository root, sibling repositories,
  private backend checkouts, or external instructions.
- Keep commands, links, file paths, and source trees relative to this root.
- Use public upstream documentation or fixtures committed here for evidence.
- Record accepted repository decisions in `ROADMAP.md`, `ARCHITECTURE.md`,
  `RELEASING.md`, and this file.
- The repository-independence check must copy the candidate into an empty
  temporary parent, scan public documentation and configuration for external
  outside-root dependencies, and run its documented offline gates there.

## Product contract

The PyPI package name is `cometapi`. Version `0.1.0a1` exports only the public
clients `CometAPI` and `AsyncCometAPI`; `CometClient` and `AsyncCometClient`
must not exist as aliases.

The supported 0.1 operations are:

- `chat.completions.create`: synchronous and asynchronous, streaming and
  non-streaming.
- `responses.create`: synchronous and asynchronous, streaming and
  non-streaming.
- `models.list`: synchronous and asynchronous.

An inherited OpenAI resource is not supported unless it has mocked contract
coverage and appears in `COMPATIBILITY.md`.

Anthropic, Gemini, CometAPI-specific account and platform resources, image,
video, audio, batch, fine-tuning, realtime, provider-neutral translation, CLI,
and Go work are outside 0.1. Do not add placeholder provider modules or
compatibility aliases.

## Architecture rules

- Implement `CometAPI` as a thin subclass of `openai.OpenAI` and
  `AsyncCometAPI` as a thin subclass of `openai.AsyncOpenAI`.
- Reuse official OpenAI transport, request and response models, errors,
  retries, timeouts, pagination, and SSE streaming.
- Use documented public OpenAI constructor options only. Do not depend on
  private upstream attributes or hand-write equivalent protocol layers.
- Keep the constructor explicit and precisely typed. It may forward only named
  options compatible with CometAPI routing and authentication; reject arbitrary
  keywords, private underscore-prefixed controls, provider routing, and
  workload identity.
- Preserve official OpenAI request, response, stream, and exception types.
- Public APIs require precise type hints, and the package must ship `py.typed`.
- Add CometAPI-specific resources only in a later milestone with authoritative
  schemas, authentication and error contracts, fixtures, and tests.

The 0.1 source layout is:

```text
src/cometapi/
├── __init__.py
├── _config.py
├── client.py
└── py.typed
tests/
scripts/
```

## Configuration and dependencies

Explicit constructor values take precedence over environment variables, which
take precedence over defaults:

| Setting | Environment | Default |
| --- | --- | --- |
| `api_key` | `COMETAPI_KEY` | Required |
| `base_url` | `COMETAPI_BASE_URL` | `https://api.cometapi.com/v1` |

Never log or include a complete credential in CometAPI-generated errors.

The installable OpenAI range is `openai>=2.45.0,<3.0.0`. The lock file chooses
a reproducible development version but must not narrow end-user resolution to
that exact version. Runtime dependencies belong in the manifest only when
CometAPI source directly imports and owns their use.

Compatibility checks cover the minimum supported OpenAI version, the locked
development version, and a scheduled or dependency-PR latest-within-major
canary. Python 3.10 through 3.14 is the initial blocking runtime range while
Python 3.10 remains upstream-supported.

## Development and verification

Run from the repository root:

```bash
uv sync --locked
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run pyright
uv run pytest -m "not live"
uv run python scripts/check_version.py --expected 0.1.0a1 --require-changelog
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

The workflow wrapper downloads and checksum-verifies `actionlint` 1.7.12 on its
first run, then validates every workflow. Its success is static syntax and
semantic evidence only; it does not emulate GitHub Actions or prove remote
execution. Use `--offline` after the pinned binary is cached when network-free
validation is required.

Mocked contracts for every supported operation must verify the HTTP method and
resolved URL, authentication, serialization, deserialization, streaming,
async lifecycle and closing, timeout and retry option forwarding, official
error identity, and secret non-disclosure. Pull-request checks must not require
a production credential. Live checks run only through a trusted, budgeted
workflow after maintainer authorization.

Build wheel and source distribution into a clean output directory. Inspect
their metadata and file lists, install each exact artifact independently
outside the source tree, assert version and public imports, and run mocked-call
smokes. Generated artifacts, local environments, and credentials must never be
committed.

## Release and documentation rules

- The first public artifact must be functional `0.1.0a1`, never a placeholder.
- Publication uses a reviewed immutable tag, a protected `pypi` environment,
  and PyPI OIDC Trusted Publishing.
- The release commit must equal the tag target and belong to the protected
  default branch. A protected live-smoke job must check out that exact commit
  and succeed before the protected PyPI job can become eligible.
- Scheduled/default-branch live smoke is monitoring evidence only and cannot
  satisfy the exact-release live gate.
- Missing identity, credentials, environments, reviewers, protection,
  publisher configuration, or approval blocks publication; no conditional
  skip or mock may bypass it.
- Manual or arbitrary-branch publication is forbidden.
- A successful build or upload is not a release. Registry installation,
  import, mocked-call smoke, and provenance must be verified separately.
- Keep third-party Actions pinned to full commit SHAs and grant
  `id-token: write` only to the publishing job.
- Keep README, roadmap, compatibility matrix, examples, and changelog aligned
  with shipped behavior. Use currently supported model IDs.
- All repository documentation is written in English.

Before Public Preview, run
`uv run python scripts/check_version.py --require-public-preview-docs`. The
gate must report every detected violation and fail until canonical identity,
contacts, repository metadata, and durable public-facing content are complete.

The private repository becoming public begins a short configuration interval;
it does not by itself establish Public Preview readiness. After visibility
changes, require pull requests and blocking CI for `main`, with zero required
approvals, blocked force pushes and deletion, and administrator bypass reserved
for emergencies. Protect version tags from updates and deletion, enable
immutable releases and Private Vulnerability Reporting, configure `live-smoke`
without a required reviewer, and configure `pypi` with approval by the current
release approver and self-review allowed. Rerun CI and the authorized protected
live smoke before recording Public Preview readiness or preparing Registry
Alpha.

Verification reports must list exact commands and outcomes, failed or
unavailable checks, and unverified remote, live, and registry evidence as
separate categories.
