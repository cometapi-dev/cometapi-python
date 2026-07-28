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

## Current milestone: Stable 0.1

Stable 0.1 is complete: `cometapi==0.1.0` is publicly available and its release
and registry trust chain has been verified. Do not begin 0.2 provider adapters
without a separate maintainer request that authorizes that milestone.

Private Remote Validation, the sanitized first history, private initialization,
pre-visibility closeout, public visibility configuration, Public Preview,
Registry Alpha, and the first stable release are completed historical steps and
must not be repeated. The canonical repository is public with protected branch
and version-tag rules, Private Vulnerability Reporting, immutable releases,
protected environments, public default-branch CI, and protected release and
registry evidence.

The accepted stable release evidence is:

| Field | Value |
| --- | --- |
| Release commit and tag target | `6f42981edcc6c252f8db997606671c3da84d1dd8` |
| Release tag | `v0.1.0` |
| GitHub release | `https://github.com/cometapi-dev/cometapi-python/releases/tag/v0.1.0` |
| Release workflow | `https://github.com/cometapi-dev/cometapi-python/actions/runs/30359383715` |
| PyPI release | `https://pypi.org/project/cometapi/0.1.0/` |
| Wheel SHA256 | `8eae758688bb6c98274e48d8d81f882eeae760f69cfd2f5e125004881d60e90f` |
| Source SHA256 | `e9308b44f6091200b5121e24d1a0e1b9ea3e6bcccc109d6de87554b1ab2a8bca` |

The accepted Registry Alpha evidence is:

| Field | Value |
| --- | --- |
| Release commit | `31b68904141489ca04932edbf305ccf88af09372` |
| Recovery tag | `v0.1.0-alpha.1+recovery.1` |
| Tag object | `fdc4a6cce31f4534f83903f3f95e7757a4d4049f` |
| GitHub release | `https://github.com/cometapi-dev/cometapi-python/releases/tag/v0.1.0-alpha.1%2Brecovery.1` |
| Release workflow | `https://github.com/cometapi-dev/cometapi-python/actions/runs/30261746138` |
| PyPI release | `https://pypi.org/project/cometapi/0.1.0a1/` |
| Wheel SHA256 | `a6820347317943ca22f7632acbe354dd992f31a122a6172dfe45b57960e3a093` |
| Source SHA256 | `98d86829ef14771e8b7ec180d452c6638289f49c14a39b7207be5c47cb64cde7` |

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

Post-stable invariants:

1. Treat the dependency dispositions recorded in `ROADMAP.md` as authoritative
   for the listed pull requests. Process newly opened dependency pull requests
   through normal maintenance only when a current maintainer request explicitly
   authorizes that work, without reopening completed dispositions.
2. Keep `.github/CODEOWNERS` absent until a real multi-maintainer model exists.
3. Keep scheduled and manually dispatched live smoke fail-closed behind
   `LIVE_SMOKE_ENABLED=true`, and keep `RELEASE_PLEASE_ENABLED` disabled outside
   an explicitly authorized release sequence. The reviewed `last-release-sha`
   bridge was used once to generate the stable release PR and must remain absent
   after its human finalization. Keep `RELEASE_RECOVERY_TAG` and
   `RELEASE_RECOVERY_SHA` absent outside an explicitly authorized recovery of
   that exact existing immutable release identity, and delete them as soon as
   recovery identity verification succeeds or the run stops.
4. Treat the recorded public rules, security reporting, immutable releases, and
   protected environments as readiness invariants. Any drift invalidates the
   readiness claim until it is explicitly authorized, restored, and verified.
5. Keep the `pypi` environment approval assigned to the current release
   approver with self-review allowed; the reviewer is GitHub configuration and
   must not be hardcoded in repository files.
6. Treat every recorded release tag, GitHub release, and PyPI distribution as
   immutable.
   Any later live request, tag, release, Trusted Publisher change, publication,
   or other registry mutation requires separate explicit maintainer
   authorization.
7. Keep `pypa/gh-action-pypi-publish` in the top-level `publish.yml` workflow
   that PyPI records as the Trusted Publisher. Do not move publication into a
   reusable workflow or call it from another workflow: PyPI requires an
   attestation's Build Config URI to match the workflow identity used for the
   Trusted Publisher exchange. The workflow inventory and semantic tests must
   fail if this single-publisher boundary changes.
8. Every release job downstream of the mutually exclusive release selector
   must use `always() && !cancelled()` so GitHub evaluates it after the unused
   release path is skipped, must reject workflow reruns, and must require every
   direct dependency's `result` to equal `success`. A skipped, cancelled,
   failed, or missing dependency must never make build, live smoke,
   publication, or registry verification eligible.

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

The PyPI package name is `cometapi`. Version `0.1.0` exports only the public
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
  default branch. Release Please must independently confirm that the exact tag
  and commit are immutable before the top-level publication workflow selects
  them for downstream jobs; do not rely on workflow-token release events to
  trigger it. A
  protected live-smoke job must check out that exact commit and succeed before
  the protected PyPI job can become eligible.
- Scheduled/default-branch live smoke is monitoring evidence only and cannot
  satisfy the exact-release live gate.
- Missing identity, credentials, environments, reviewers, protection,
  publisher configuration, or approval blocks publication; no conditional
  skip or mock may bypass it.
- Arbitrary-branch publication is forbidden. Manual publication is permitted
  only through the reviewed `workflow_dispatch` path in `publish.yml` from the
  protected default branch, with `RELEASE_RECOVERY_TAG` and
  `RELEASE_RECOVERY_SHA` equal to its exact inputs, after separately verifying
  the existing immutable tag and commit. Recovery verification, release
  selection, and all downstream release jobs must reject every workflow rerun.
  Delete both variables immediately after the recovery succeeds or stops.
- A successful build or upload is not a release. Registry installation,
  import, mocked-call smoke, and provenance must be verified separately.
- Every distribution `Project-URL` must use HTTPS. The canonical Support URL
  is `https://github.com/cometapi-dev/cometapi-python/blob/main/SUPPORT.md`;
  `support@cometapi.com` remains the support and conduct contact.
- GitHub permanently reserved `v0.1.0-alpha.1` after its immutable release
  reached OIDC publication but failed before any PyPI distribution was
  accepted. The sole approved recovery tag is
  `v0.1.0-alpha.1+recovery.1`, which maps to package version `0.1.0a1`.
  Later releases must use their ordinary canonical tag spelling.
- Keep Release Please disabled outside an explicitly authorized release
  sequence. The stable-readiness configuration used a reviewed and tested
  `last-release-sha` bridge because the recovery tag's build metadata could not
  be inferred from the manifest. The human-finalized stable release PR removed
  that bridge and its prerelease-versioning controls; keep them absent.
- Keep third-party Actions pinned to full commit SHAs. Keep release creation,
  recovery, build, protected live smoke, OIDC publication, and registry
  verification in the single top-level `publish.yml` workflow. Grant
  `id-token: write` only to its protected publishing job, and keep
  `COMETAPI_KEY` scoped only to the protected live credential preflight and
  test. The semantic checker must reject reusable publication, split workflow
  identities, additional OIDC consumers, and raw dispatch inputs downstream of
  the verified release selector. Every selector descendant must explicitly
  evaluate skipped ancestry, reject cancellation and reruns, and require each
  direct dependency to succeed.
- Keep README, roadmap, compatibility matrix, examples, and changelog aligned
  with shipped behavior. Use currently supported model IDs.
- All repository documentation is written in English.

The Public Preview readiness record requires
`uv run python scripts/check_version.py --require-public-preview-docs` to keep
passing. The gate must report every detected violation and fail until canonical
identity, contacts, repository metadata, and durable public-facing content are
complete.

Before preparing any later release, re-audit that `main` still requires pull
requests and blocking CI with zero required approvals, force pushes and deletion
remain blocked, administrator bypass remains emergency-only, version tags remain
protected, immutable releases and Private Vulnerability Reporting remain
enabled, and the `live-smoke` and `pypi` environments retain their reviewed
protection boundaries. `LIVE_SMOKE_ENABLED` is `false`; enable it only for a
separately authorized monitoring request.

Verification reports must list exact commands and outcomes, failed or
unavailable checks, and unverified remote, live, and registry evidence as
separate categories.
