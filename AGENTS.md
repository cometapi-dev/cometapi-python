# CometAPI Python SDK Agent Instructions

This file is the self-contained engineering contract for the public CometAPI
Python SDK repository. Treat this directory as the repository root.

## Repository authority and remote permissions

Repository documents define permitted workflows and safety boundaries; they do
not grant standing permission to change local tracked content or remote state.
Any push, pull-request creation or update, merge, comment, or other remote
mutation requires explicit authorization in the current maintainer request.
Without new explicit authorization, limit work to local read-only inspection or
validation and do not create another pre-visibility closeout pull request.

Repository visibility, settings, branch or tag rules, Private Vulnerability
Reporting, secrets, variables, environments, live API requests, tags, releases,
PyPI operations, and other registry operations each require separate explicit
authorization. Authorization for one action does not authorize another.

A local build, mocked test, statically valid workflow, or private remote CI run
proves only its own evidence layer. Never invent or mock missing evidence.

## Git branch lifecycle

- Start every authorized task from a clean worktree. Fetch `origin`, switch to
  local `main`, require `main` to be an ancestor of `origin/main`, and run
  `git merge --ff-only origin/main`. Require the worktree to remain clean and
  `main` to equal `origin/main` after the fast-forward.
- If local `dev` does not exist, create it with `git switch -c dev` only while
  the synchronized, clean `main` is checked out. If local `dev` exists, require
  `dev` to be an ancestor of `main`, switch to `dev`, and run
  `git merge --ff-only main`. Require `dev` to equal `main` after either path.
- Only after those startup checks pass may an authorized task create its
  dedicated short-lived topic branch from synchronized `dev`. Do not commit
  task changes directly to `dev`.
- Treat a topic branch lifecycle as closed only after its required pull-request
  checks pass and its squash merge is present on `origin/main`. Any alternate
  disposition requires explicit user authorization and must not advance `dev`
  until the accepted commit is present on `origin/main`.
- After merge and required verification, start from a clean worktree, fetch
  `origin`, switch to `main`, require it to be an ancestor of `origin/main`, and
  fast-forward it with `git merge --ff-only origin/main`. Require `main` to
  equal `origin/main`, require `dev` to be an ancestor of `main`, switch to
  `dev`, and fast-forward it with `git merge --ff-only main`. Finish on a clean
  `dev` with `HEAD`, local `main`, local `dev`, and `origin/main` all equal.
- Any dirty worktree, fetch failure, ahead or divergent local branch, failed
  ancestry check, failed fast-forward, or final ref mismatch must fail closed.
  Never reset, rebase, discard work, force-update refs, delete or recreate an
  existing `dev`, or push `dev` to recover. Report the exact state instead.

## Current milestone: Public Preview

Public Preview pre-visibility complete; visibility change awaiting explicit authorization.

Private Remote Validation is complete. The sanitized first history, empty
private repository creation, initial push, and pre-visibility closeout are
completed historical steps and must not be repeated. The canonical repository
remains private at the visibility authorization gate. Public Preview is not
ready, and no pre-visibility implementation task remains.

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

At the visibility authorization gate:

1. Treat the dependency dispositions recorded in `ROADMAP.md` as authoritative
   for the listed pull requests. Process newly opened dependency pull requests
   through normal maintenance only when a current maintainer request explicitly
   authorizes that work, without reopening completed dispositions.
2. Keep `.github/CODEOWNERS` absent until a real multi-maintainer model exists.
3. Keep scheduled and manually dispatched live smoke fail-closed behind
   `LIVE_SMOKE_ENABLED=true`, and keep `RELEASE_PLEASE_ENABLED` disabled through
   the initial manual alpha.
4. Do not create another pre-visibility closeout pull request unless a current
   maintainer request explicitly authorizes a new, scoped change.
5. Stop before changing visibility. After an explicitly authorized visibility
   change, repository rules, Private Vulnerability Reporting, protected
   environments, default-branch CI, and authorized protected live smoke must
   pass before Public Preview can be marked ready.

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

Before marking Public Preview ready, run
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
