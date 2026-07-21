# CometAPI Python SDK Roadmap

Status: `0.1.0a1` in progress
Last updated: 2026-07-21
Repository contract: this roadmap is self-contained.

## Product target

The SDK provides the shortest reliable path from an OpenAI Python integration
to CometAPI while preserving official request, response, error, retry, timeout,
sync, async, and streaming behavior.

Private Remote Validation is complete for the sanitized repository, which
remains private. Work stops before any visibility change. Public Preview and
the functional `0.1.0a1` prerelease remain separate evidence gates. Support
and release claims remain limited to the evidence defined in this roadmap and
`COMPATIBILITY.md`.

## Milestones

| Milestone | Status | Exit outcome |
| --- | --- | --- |
| Repository foundation | Complete | Public files, offline gates, packaging checks, and self-containment are complete. |
| Private Remote Validation | Complete | The sanitized private repository passes real credential-free default-branch CI; public-only controls and live tests remain disabled. |
| Public Preview | Planned | The public repository has blocking CI, repository rules, security reporting, protected environments, and authorized live-smoke evidence before it claims preview readiness. |
| `0.1.0a1` Registry Alpha | Planned | Early adopters can install a functional prerelease from PyPI. |
| `0.1.0` stable | Planned | Complete runtime, release-PR, example, provenance, and registry gates pass. |
| `0.2.0` provider-native text | Planned | Optional official Anthropic and Gemini adapters. |
| `0.3.0` CometAPI resources | Planned | First schema-backed typed CometAPI-specific resource. |
| Media and task APIs | Planned | Coherent task lifecycle precedes individual media helpers. |

## Repository foundation

Deliverables:

- Package `cometapi`, version `0.1.0a1`, with `CometAPI` and `AsyncCometAPI` and
  no legacy aliases.
- Standalone documentation, MIT licensing, contribution and conduct guidance,
  security and support policies, architecture, release guide, changelog,
  compatibility matrix, and issue and pull-request templates.
- Normalized package metadata, a reproducible development lock, Ruff, Pyright,
  pytest, metadata, artifact, clean-install, secret, and version checks.
- Offline CI, trusted live-smoke definition, release-PR automation, OIDC
  publishing definition, and dependency update automation.
- A repository-independence gate that copies the candidate into an empty
  temporary parent and runs repository-local checks.
- Local validation of every workflow with documented `actionlint` 1.7.12.

Exit criteria:

- A new contributor can run documented checks from the repository root.
- Pull-request checks require no production credential.
- The wheel and source distribution contain only intended files and each exact
  artifact passes an independent clean install and mocked-call smoke.
- Documentation and configuration contain no dependency outside the repository root.
- Public identity and remote administration use maintainer-confirmed values.

### Private Remote Validation

Before Public Preview, maintainers create a private repository from a
sanitized first commit and verify real GitHub behavior. The complete history
must already be suitable for future public visibility and contain only durable
product, contribution, maintenance, compatibility, and release material.

Exit criteria:

- Canonical repository metadata, `CometAPI` authorship,
  `Copyright (c) 2026 CometAPI`, `support@cometapi.com`, and the repository's
  Private Vulnerability Reporting URL are present in their intended public
  files. `CODEOWNERS` is absent until a real multi-maintainer model exists.
- Default-branch CI passes in GitHub Actions on every blocking runtime.
- The repository-independence and public-content gates pass against tracked
  files and history.
- `LIVE_SMOKE_ENABLED` and `RELEASE_PLEASE_ENABLED` keep live and release-PR
  workflows disabled.
- No branch or tag rules, Private Vulnerability Reporting, protected
  environments, registry publisher, live credential, tag, release, or package
  publication is configured or exercised during this private stage.

The private repository is created empty, without generated starter files, so
the sanitized local content becomes its first history. This stage ends after
real credential-free default-branch CI is recorded. It does not change
visibility or publish to a private or public registry.

Recorded evidence on 2026-07-21:

- The empty private canonical repository received sanitized root commit
  `7bbffde609e2a5767c3ac1a8b6387ca9744c9e44`.
- Credential-free default-branch
  [CI run 29796686485](https://github.com/cometapi-dev/cometapi-python/actions/runs/29796686485)
  completed successfully for that commit. Blocking Python 3.10 through 3.14,
  minimum-OpenAI, quality, workflow, package, clean-install, and copied-checkout
  jobs passed; the push-only latest-within-major canary skipped as designed.
- Release Please remained disabled and its push run skipped. The repository
  remained private, and no live request, public-only control, tag, release, or
  package publication was configured or exercised.

## Public Preview

Changing the repository to public begins a short configuration interval; it
does not establish Public Preview readiness by itself. The preview is ready
only when:

- `main` requires pull requests and blocking CI with zero required approvals;
  force pushes and deletion are blocked, and administrator bypass is reserved
  for emergencies.
- Version tags cannot be updated or deleted, immutable releases and Private
  Vulnerability Reporting are enabled, and the documented security URL works.
- The `live-smoke` environment has no required reviewer. The `pypi`
  environment requires approval by the current release approver and permits
  self-review.
- Default-branch CI is rerun successfully after the public configuration.
- The fail-closed content gate reports all violations together and then passes,
  repository self-containment and package gates pass, and the README accurately
  states prerelease and registry availability.
- An explicitly authorized protected live smoke passes within the four-request,
  16-output-token, 30-second-per-request, concurrency-one, stop-on-first-failure
  budget.

## `0.1.0a1`: Registry Alpha

### User-visible scope

- `CometAPI` and `AsyncCometAPI`.
- `chat.completions.create`: sync and async, streaming and non-streaming.
- `responses.create`: sync and async, streaming and non-streaming.
- `models.list`: sync and async.
- `COMETAPI_KEY`, `COMETAPI_BASE_URL`, and explicit constructor overrides.
- Official OpenAI request, response, stream, error, retry, timeout, proxy, and
  custom transport behavior.

### Implementation and compatibility

- Thin public subclasses of `openai.OpenAI` and `openai.AsyncOpenAI`.
- Installable range `openai>=2.45.0,<3.0.0`.
- Minimum, locked-development, and latest-within-major compatibility lanes.
- Mocked contracts for URLs, authentication, serialization, deserialization,
  sync/async modes, streaming, client closing, option forwarding, retries,
  timeouts, official error identity, and credential non-disclosure.
- Wheel and source-distribution metadata, file-list, version, clean-install,
  and mocked-call verification.

### Explicit non-goals

- Anthropic or Gemini adapters.
- CometAPI account, balance, usage, token, log, task, or platform resources.
- Image, video, audio, batch, fine-tuning, realtime, or provider-neutral APIs.
- Reimplemented HTTP, SSE, retry, timeout, protocol models, or error classes.
- Support claims for every resource inherited from OpenAI.
- CLI or Go SDK changes.
- `CometClient` or `AsyncCometClient` compatibility aliases.

### Release gates

Before the alpha may be called released, maintainers must confirm package
ownership and PyPI pending Trusted Publisher configuration, authorize a
budgeted live smoke run, and review the release documentation. The release
workflow must then prove that the immutable tag target is the checked-out
commit and belongs to the protected default branch, run the protected live
suite against that exact commit, and only then make protected PyPI approval
eligible. Public artifact identity, digest, provenance, import, clean install,
and mocked calls remain separate post-publication evidence.

A mock never satisfies a live gate, static workflow validation never proves a
remote run, and a successful upload never proves registry installation.
PyPI publication is OIDC-only; Python has no token-bootstrap exception.

## `0.1.0`: OpenAI protocol foundation

Stable 0.1 retains the alpha surface. Its additional exit criteria are:

- Blocking Python runtime matrix for every supported runtime.
- Human-reviewed release PR with exact version and changelog agreement.
- Executed README examples against the built artifact.
- Trusted live Chat Completions and Responses smoke evidence.
- Immutable tag, GitHub release, wheel, source distribution, and changelog
  versions agree.
- PyPI OIDC publication includes provenance and the public artifact passes an
  independent post-publication install/import/mocked-call check.
- No complete credential appears in source, fixtures, artifacts, or logs.

## `0.2.0`: Provider-native text adapters

Planned scope:

- Anthropic Messages and Gemini text generation through their official SDKs.
- Optional dependencies with root-import isolation.
- Provider-native request, response, stream, and error types.
- A separate provider API-root configuration that preserves explicit custom
  proxy paths.

No 0.2 adapter is added without mocked and authorized live contract coverage.

## `0.3.0`: CometAPI-specific resources

Candidate account or platform resources require an authoritative schema,
authentication contract, error contract, fixtures, precise public types, and a
live test endpoint. Resources and their Pydantic models remain physically
separated under `resources/` and `types/` when this milestone begins.

## CI/CD contract

The repository maintains four independently auditable workflows:

- `ci.yml`: offline lint, type, unit, contract, build, artifact, and clean
  install checks for pull requests and default-branch pushes.
- `live-smoke.yml`: scheduled and manual default-branch monitoring capped at
  four requests, 16 output tokens per generation, a 30-second request timeout,
  concurrency one, a ten-minute workflow timeout, and stop on first failure.
- `release-please.yml`: a human-reviewed version and changelog pull request.
- `publish.yml`: immutable-release and default-branch ancestry verification,
  exact-release protected live smoke, artifact rebuild and verification,
  protected PyPI OIDC publication, provenance, and registry verification.

All workflow files must pass local `actionlint` 1.7.12. This is static
validation only. Remote behavior remains unverified until each workflow runs
successfully in the canonical GitHub repository.

Scheduled and manually dispatched live smoke must require
`LIVE_SMOKE_ENABLED=true`; an unset or other value prevents live execution.
Release Please requires
`RELEASE_PLEASE_ENABLED=true` and remains disabled through the initial manual
alpha. Release jobs must resolve an unset or empty `COMETAPI_LIVE_MODEL` to
`gpt-5.4` rather than attempt a request with an empty model.

## Maintenance cadence

- Review upstream OpenAI updates weekly through automated dependency pull
  requests.
- Run trusted live compatibility checks nightly once maintainers authorize the
  schedule and budget.
- Review security and compatibility issues before every release.
- Review this roadmap for every minor release and at least monthly while a
  milestone remains active.
- Mark a milestone released only after its registry artifact is independently
  installed and verified.
