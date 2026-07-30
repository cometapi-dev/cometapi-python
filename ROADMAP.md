# CometAPI Python SDK Roadmap

Status: `0.1.1` stable maintenance released
Last updated: 2026-07-29
Repository contract: this roadmap is self-contained.
Current gate: maintain the verified stable 0.1 surface. Begin 0.2 only after a
separate maintainer request authorizes its provider schemas and live contracts.

## Product target

The SDK provides the shortest reliable path from an OpenAI Python integration
to CometAPI while preserving official request, response, error, retry, timeout,
sync, async, and streaming behavior.

Private Remote Validation, Public Preview, the functional `0.1.0a1` Registry
Alpha, stable `0.1.0`, and maintenance release `0.1.1` are complete for the
sanitized public repository. Protected repository configuration, public
default-branch CI, exact-release live smoke, PyPI OIDC publication, provenance,
digest comparison, and public-registry smoke provide separate evidence layers.
Support and release claims remain limited to the evidence defined in this
roadmap and `COMPATIBILITY.md`.

## Milestones

| Milestone | Status | Exit outcome |
| --- | --- | --- |
| Repository foundation | Complete | Public files, offline gates, packaging checks, and self-containment are complete. |
| Private Remote Validation | Complete | The sanitized private repository passes real credential-free default-branch CI; public-only controls and live tests remain disabled. |
| Public Preview | Complete | The public repository has blocking CI, repository rules, security reporting, protected environments, immutable releases, and authorized live-smoke evidence. |
| `0.1.0a1` Registry Alpha | Complete | Early adopters can install the functional prerelease from PyPI; every release and registry gate passed. |
| `0.1.0` stable | Complete | Complete runtime, release-PR, example, provenance, and registry gates passed. |
| `0.1.1` maintenance | Complete | Configuration validation and every stable release, live, provenance, and registry gate passed. |
| `0.2.0` provider-native text | Planned | Optional official Anthropic and Gemini adapters. |
| `0.3.0` CometAPI resources | Planned | First schema-backed typed CometAPI-specific resource. |
| Media and task APIs | Planned | Coherent task lifecycle precedes individual media helpers. |

## `0.1.x` maintenance

Stable maintenance preserves the 0.1 public operation and constructor surface.
String API keys and base URLs are trimmed at their direct or environment
boundary. Explicit blank values fail without fallback; a blank environment key
is missing, while a blank environment base URL selects the default CometAPI
URL. Callable keys and `httpx.URL` values keep their official OpenAI semantics.
Inherited `copy` and `with_options` helpers remain unsupported and fail-closed
for provider routing, workload identity, and private-option injection.

No maintenance release activates 0.2 provider adapters or adds a new resource,
CLI, translation, or Go surface without a separate maintainer request.

## Repository foundation

Deliverables:

- Package `cometapi`, version `0.1.0a1`, with `CometAPI` and `AsyncCometAPI` and
  no legacy aliases.
- Standalone documentation, MIT licensing, contribution and conduct guidance,
  security and support policies, architecture, release guide, changelog,
  compatibility matrix, and issue and pull-request templates.
- Normalized package metadata with HTTPS-only project URLs and a public support
  document link, a reproducible development lock, Ruff, Pyright, pytest,
  metadata, artifact, clean-install, secret, and version checks.
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

Private Remote Validation was the one-time initialization stage for the
canonical repository. Maintainers created an empty private repository from a
sanitized first commit and verified real GitHub behavior. The complete history
was required to be suitable for future public visibility and contain only
durable product, contribution, maintenance, compatibility, and release
material. This stage is complete and must not be repeated for the current
canonical repository.

Recorded exit criteria:

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

The private repository was created empty, without generated starter files, so
the sanitized local content became its first history. The stage ended after
real credential-free default-branch CI was recorded. It did not change
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

Public Preview ready as of 2026-07-27.

Private initialization, pre-visibility work, the visibility change, public
configuration, and preview evidence are completed historical steps and must not
be repeated. The recorded dependency dispositions below remain authoritative
for the listed pull requests. Newly opened dependency pull requests remain
pending until a current maintainer request explicitly authorizes their normal
maintenance; they must not cause closed or superseded dispositions to be
described as unfinished.

The milestone was established only after repository rules, Private
Vulnerability Reporting, immutable releases, protected environments,
public default-branch CI, the public-content gate, and an authorized protected
live smoke passed. Registry Alpha remained a separate authorization and
evidence gate and was completed later the same day.

Recorded pre-visibility dependency dispositions:

| Item | Disposition | Evidence and required action |
| --- | --- | --- |
| Dependabot [PR #1](https://github.com/cometapi-dev/cometapi-python/pull/1): `actions/download-artifact` 4.3.0 to 8.0.1 | Closed unmerged; superseded by merged private [PR #9](https://github.com/cometapi-dev/cometapi-python/pull/9) | PR #9 applies the reviewed SHA pin throughout the release workflow and adds a credential-free CI artifact download plus SHA256 round trip. Its final [CI run 29916685839](https://github.com/cometapi-dev/cometapi-python/actions/runs/29916685839) passed, PR #9 squash-merged as `72b212dd72e66bbde9c6714329f72071cc1ca129`, and PR #1 was closed without merging. |
| Dependabot [PR #2](https://github.com/cometapi-dev/cometapi-python/pull/2): `actions/checkout` 4.2.2 to 7.0.1 | Closed unmerged; superseded by merged private [PR #9](https://github.com/cometapi-dev/cometapi-python/pull/9) | PR #2's [CI run 29796719306](https://github.com/cometapi-dev/cometapi-python/actions/runs/29796719306) failed because its regression test hard-coded the previous checkout SHA. PR #9 instead validates parsed action references independently of version, passed final CI run 29916685839, and squash-merged as `72b212dd72e66bbde9c6714329f72071cc1ca129`; PR #2 was closed without merging, and its failed run remains negative evidence only. |
| Dependabot [PR #3](https://github.com/cometapi-dev/cometapi-python/pull/3): `pypa/gh-action-pypi-publish` 1.14.0 to 1.14.1 | Deferred; keep out of `main` | Pull-request CI does not execute the release-triggered OIDC publish action or prove PyPI publication, provenance, or registry installation. Revisit with an authorized release-path review and the separately required protected release evidence; credential-free CI success alone is insufficient. |
| Dependabot [PR #4](https://github.com/cometapi-dev/cometapi-python/pull/4): `actions/upload-artifact` 4.6.2 to 7.0.1 | Closed unmerged; superseded by merged private [PR #9](https://github.com/cometapi-dev/cometapi-python/pull/9) | PR #9 applies the reviewed SHA pin in CI and release builds, requires missing artifacts to fail, retains digest evidence, passed final CI run 29916685839, and squash-merged as `72b212dd72e66bbde9c6714329f72071cc1ca129`; PR #4 was closed without merging. |
| Dependabot [PR #5](https://github.com/cometapi-dev/cometapi-python/pull/5): `googleapis/release-please-action` 4.4.1 to 5.0.0 | Deferred; keep out of `main` | `RELEASE_PLEASE_ENABLED` remains disabled, and pull-request CI does not execute the gated write-capable Release Please action. Revisit only after its real config, manifest, permissions, and release behavior can be reviewed without treating a skipped action as execution evidence. |
| Dependabot [PR #6](https://github.com/cometapi-dev/cometapi-python/pull/6): `actions/setup-python` 5.6.0 to 7.0.0 | Closed unmerged; superseded by merged private [PR #9](https://github.com/cometapi-dev/cometapi-python/pull/9) | PR #9 applies the reviewed SHA pin across CI, monitoring, and release workflows, passed final CI run 29916685839 on every blocking lane, and squash-merged as `72b212dd72e66bbde9c6714329f72071cc1ca129`; PR #6 was closed without merging. |

Recorded pre-visibility replacement evidence on 2026-07-22:

Local and package evidence at commit
`97a14ac6087db3c9205e66bcfbcc890dc23a7ca7`:

- `git diff --check`, `uv lock --check`, and `uv sync --locked` passed.
- `uv run ruff check src tests scripts`,
  `uv run ruff format --check src tests scripts`, and `uv run pyright` passed.
- `uv run pytest -m "not live"` passed with 173 tests passed and one separately
  marked live test deselected.
- `uv run python scripts/check_version.py --expected 0.1.0a1 --require-changelog`
  and
  `uv run python scripts/check_version.py --require-public-preview-docs` passed.
- `uv run python scripts/check_secrets.py` and
  `uv run python scripts/check_workflows.py` passed.
- `rm -rf dist` completed, and `uv build` produced the `0.1.0a1` wheel and source
  distribution in the clean output directory.
- `uv run twine check dist/*`,
  `uv run python scripts/check_artifacts.py dist/*`, and
  `uv run python scripts/check_clean_install.py dist/*` passed for both exact
  artifacts, including SHA256 digest generation.
- `uv run python scripts/check_repository_independence.py` passed after copying
  the candidate into an empty temporary parent and rerunning its complete
  offline, workflow, build, artifact, and two-artifact clean-install gates.
- `uv run python scripts/run_actionlint.py` and
  `uv run python scripts/run_actionlint.py --offline` passed with
  checksum-pinned actionlint 1.7.12.

Follow-up verifier-hardening evidence at commit
`88560a889017e2bddc47c52bcaf51e97fa42bcd4`:

- `git diff --check`, `uv lock --check`, and `uv sync --locked` passed.
- `uv run ruff check src tests scripts`,
  `uv run ruff format --check src tests scripts`, and `uv run pyright` passed.
- `uv run pytest -m "not live"` passed with 197 tests passed and one separately
  marked live test deselected.
- `uv run python scripts/check_version.py --expected 0.1.0a1 --require-changelog`,
  `uv run python scripts/check_version.py --require-public-preview-docs`,
  `uv run python scripts/check_secrets.py`, and
  `uv run python scripts/check_workflows.py` passed.
- `uv run python scripts/run_actionlint.py` and
  `uv run python scripts/run_actionlint.py --offline` passed with
  checksum-pinned actionlint 1.7.12.
- `uv build`, `uv run twine check dist/*`,
  `uv run python scripts/check_artifacts.py dist/*`, and
  `uv run python scripts/check_clean_install.py dist/*` passed for the rebuilt
  wheel and source distribution.
- `uv run python scripts/check_repository_independence.py` passed the complete
  copied-checkout gate, including its offline suite, build, artifact checks, and
  independent clean installs of both artifacts.
- Independent adversarial workflow review and targeted follow-up regression
  coverage found no remaining accepted hostile case after checking trigger
  filters, secret-context access, runner, container, matrix, working-directory,
  checkout, job, step, and environment overrides, arbitrary privileged actions,
  mutable refs, no-op and failure-swallowing commands, artifact ordering, and
  release-ref decoys.

Final workflow-inventory hardening evidence at commit
`668b78f89e8962cc8ab1d1aca8fe3d24c38723ac`:

- `git diff --check`, `uv lock --check`, and `uv sync --locked` passed.
- `uv run ruff check src tests scripts`,
  `uv run ruff format --check src tests scripts`, and `uv run pyright` passed.
- `uv run pytest -m "not live"` passed with 200 tests passed and one separately
  marked live test deselected.
- `uv run python scripts/check_version.py --expected 0.1.0a1 --require-changelog`,
  `uv run python scripts/check_version.py --require-public-preview-docs`,
  `uv run python scripts/check_secrets.py`, and
  `uv run python scripts/check_workflows.py` passed.
- `uv run python scripts/run_actionlint.py` and
  `uv run python scripts/run_actionlint.py --offline` passed with
  checksum-pinned actionlint 1.7.12.
- `uv run python scripts/check_repository_independence.py` passed the complete
  copied-checkout gate, including 200 offline tests, the package build, artifact
  inspection, and independent clean installs of the wheel and source
  distribution.

Final pre-visibility refresh evidence on 2026-07-23:

- `git diff --check`, `uv lock --check`, and `uv sync --locked` passed.
- `uv run ruff check src tests scripts`,
  `uv run ruff format --check src tests scripts`, and `uv run pyright` passed.
- `uv run pytest -m "not live"` passed with 200 tests passed and one separately
  marked live test deselected.
- `uv run python scripts/check_version.py --expected 0.1.0a1 --require-changelog`,
  `uv run python scripts/check_version.py --require-public-preview-docs`,
  `uv run python scripts/check_secrets.py`, and
  `uv run python scripts/check_workflows.py` passed.
- `uv build --out-dir dist/previsibility-20260723` built exactly the
  `0.1.0a1` wheel and source distribution in a newly created empty directory.
  `uv run twine check dist/previsibility-20260723/*`,
  `uv run python scripts/check_artifacts.py dist/previsibility-20260723/*`, and
  `uv run python scripts/check_clean_install.py dist/previsibility-20260723/*`
  passed for both exact artifacts.
- `uv run python scripts/check_repository_independence.py` passed the complete
  copied-checkout gate, including its 200 offline tests, workflow validation,
  package build, artifact inspection, and independent clean installs of both
  artifacts.
- `uv run python scripts/run_actionlint.py` and
  `uv run python scripts/run_actionlint.py --offline` passed with
  checksum-pinned actionlint 1.7.12.

Failed or unavailable checks:

- None of the executed final-candidate validation checks failed or were
  unavailable.
  Dependabot PR #2's failed run remains separate negative evidence for that PR,
  not replacement evidence for PR #9. An earlier intentional offline actionlint
  probe in a fresh detached worktree failed closed before the verified cache was
  populated; it is not final-candidate validation evidence.

Recorded pre-visibility remote evidence:

- Private PR #9's final-head
  [CI run 29916685839](https://github.com/cometapi-dev/cometapi-python/actions/runs/29916685839)
  passed quality, Python 3.10 through 3.14, minimum OpenAI, package,
  exact-artifact clean install, retained artifact digest, and copied-checkout
  jobs for `5db7f012a1470564f4f60fe343b9a0799b58987d`; the PR-only
  latest-within-major canary skipped as designed. PR #9 then squash-merged as
  `72b212dd72e66bbde9c6714329f72071cc1ca129`, and its credential-free
  [default-branch CI run 29916919999](https://github.com/cometapi-dev/cometapi-python/actions/runs/29916919999)
  passed. Superseded PRs #1, #2, #4, and #6 were closed without merging.
- Private PR #10's
  [CI run 29978262916](https://github.com/cometapi-dev/cometapi-python/actions/runs/29978262916)
  passed the same blocking lanes for
  `debd7c1d12c72219ee37de0baa58be119d135ae0`; its PR-only canary skipped as
  designed. PR #10 squash-merged as
  `7d9a3d70714b38b4815d8a8f82a7177d1bcea857`, and its
  [default-branch CI run 29978384862](https://github.com/cometapi-dev/cometapi-python/actions/runs/29978384862)
  passed. The corresponding
  [Release Please run 29978384858](https://github.com/cometapi-dev/cometapi-python/actions/runs/29978384858)
  skipped as required while `RELEASE_PLEASE_ENABLED` remains disabled.
- The final merged workflow's latest-within-major canary remains unverified
  under its scheduled and Dependabot paths.
- The canonical repository was confirmed private after these runs.
  Repository-level variables and Actions secrets, environments, tags, releases,
  and publish runs were absent when checked; `main` reported
  `protected: false`. Organization-level variables and secrets were unavailable
  to the current credential; detailed protection and ruleset APIs were
  unavailable under the current private-repository plan. They do not provide
  additional evidence. No visibility, secret, environment, protection, live,
  tag, release, registry, or publication change was made.

Recorded pre-visibility live evidence:

- The live-smoke path was not executed, and no live API request was made.
  Transport success and provider behavior therefore remain unverified.

Recorded pre-visibility registry and release evidence:

- Release Please, immutable-release publishing, PyPI OIDC, provenance, and
  public-registry installation were not executed. No tag, release, or
  publication was created.

Public Preview readiness evidence on 2026-07-27:

- The complete local readiness gate passed on 2026-07-27 with all three
  readiness-document changes present: lock reproduction, Ruff, formatting,
  Pyright, 200 non-live tests, public-content, secret, workflow, actionlint,
  exact wheel and source-distribution, clean-install, and copied
  standalone-repository checks all succeeded.
- The canonical repository became public. Active rulesets require pull
  requests and the nine blocking CI contexts on `main`, block force pushes and
  deletion with organization-administrator emergency bypass, permit only squash
  merges, and protect `refs/tags/v*` from updates and deletion.
- Immutable releases and Private Vulnerability Reporting were enabled. The
  `live-smoke` environment has no required reviewer; the `pypi` environment
  requires the current release approver and permits self-review. The live key
  exists only as an environment secret.
- Public scheduled
  [CI run 30248141487](https://github.com/cometapi-dev/cometapi-python/actions/runs/30248141487)
  passed quality, Python 3.10 through 3.14, minimum and latest-within-major
  OpenAI compatibility, package, exact-artifact, retained-digest, and copied
  standalone-repository jobs for `fa32e962f7a35dd9e183f7b201bd9117590654a9`.
  A manually requested rerun was superseded by this scheduled run through the
  reviewed concurrency group and was not used as final evidence.
- Explicitly authorized protected
  [live-smoke run 30248383703](https://github.com/cometapi-dev/cometapi-python/actions/runs/30248383703)
  passed all four sequential Chat Completions and Responses modes against
  `gpt-5.4` within the four-request, 16-output-token, 30-second-per-request,
  concurrency-one, zero-retry, stop-on-first-failure budget. The
  `LIVE_SMOKE_ENABLED` opt-in was reset to `false` after the run.
- At this Public Preview checkpoint, no tag, GitHub release, Trusted Publisher,
  PyPI OIDC publication, provenance, or public-registry installation existed.
  Those later Registry Alpha actions are recorded below. Release Please remained
  disabled until a separately reviewed and tested `last-release-sha` bridge
  established the recovery alpha as its previous-release boundary.

Public Preview remains ready only while:

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
  repository self-containment and package gates pass, and the README uses
  publication-neutral stable installation guidance suitable for immutable
  distribution metadata.
- An explicitly authorized protected live smoke passes within the four-request,
  16-output-token, 30-second-per-request, concurrency-one, stop-on-first-failure
  budget.

## `0.1.0a1`: Registry Alpha

Registry Alpha completed on 2026-07-27.

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

### Completed release gates

The alpha was not called released until maintainers confirmed package ownership
and PyPI Trusted Publisher configuration, authorized the budgeted live smoke,
and reviewed the release documentation. The release workflow proved that the
immutable tag target was the checked-out commit and belonged to the protected
default branch, ran the protected live suite against that exact commit, and
only then made protected PyPI approval eligible. Public artifact identity,
digest, provenance, import, clean install, and mocked calls were verified as
separate post-publication evidence.

A mock never satisfies a live gate, static workflow validation never proves a
remote run, and a successful upload never proves registry installation.
PyPI publication is OIDC-only; Python has no token-bootstrap exception.

The first immutable release reached PyPI OIDC publication but Warehouse
rejected its non-HTTPS Support project URL before accepting any distribution.
GitHub permanently reserved the deleted `v0.1.0-alpha.1` release identity. The
approved recovery release therefore uses
`v0.1.0-alpha.1+recovery.1`, whose SemVer build suffix leaves the PyPI package
version at the required first public artifact `0.1.0a1`.

Accepted release evidence:

- Metadata fix [PR #16](https://github.com/cometapi-dev/cometapi-python/pull/16)
  merged as `6344c2d0e2e975360b42c887275c1950b82918ee`; recovery contract
  [PR #17](https://github.com/cometapi-dev/cometapi-python/pull/17) merged as
  release commit `31b68904141489ca04932edbf305ccf88af09372`. Final
  [default-branch CI run 30261497883](https://github.com/cometapi-dev/cometapi-python/actions/runs/30261497883)
  passed.
- Annotated tag `v0.1.0-alpha.1+recovery.1` has tag object
  `fdc4a6cce31f4534f83903f3f95e7757a4d4049f` and peels to the release
  commit. The corresponding
  [immutable GitHub prerelease](https://github.com/cometapi-dev/cometapi-python/releases/tag/v0.1.0-alpha.1%2Brecovery.1)
  is release `360377046`.
- [Release workflow run 30261746138](https://github.com/cometapi-dev/cometapi-python/actions/runs/30261746138)
  passed exact artifact construction and validation, the authorized four-request
  protected live smoke, protected `pypi` approval, OIDC Trusted Publishing,
  provenance verification, public digest comparison, clean PyPI installation,
  imports, and the public-registry mocked-call smoke.
- The exact [PyPI release](https://pypi.org/project/cometapi/0.1.0a1/) is public.
  Its wheel SHA256 is
  `a6820347317943ca22f7632acbe354dd992f31a122a6172dfe45b57960e3a093` and
  its source-distribution SHA256 is
  `98d86829ef14771e8b7ec180d452c6638289f49c14a39b7207be5c47cb64cde7`.
- `LIVE_SMOKE_ENABLED=false`. Release Please remains disabled outside an
  explicitly authorized release sequence. The reviewed stable-readiness
  `last-release-sha` bridge generated the stable release PR and was removed
  during human finalization.

## `0.1.0`: OpenAI protocol foundation

Stable 0.1 retains the alpha surface. Its additional exit criteria are:

- Blocking Python runtime matrix for every supported runtime.
- Human-reviewed release PR with exact version and changelog agreement.
- Stable documentation, classifier, and installation guidance finalized in the
  release PR, with the one-time recovery bridge removed before merge.
- Executed README examples against the built artifact.
- Trusted live Chat Completions and Responses smoke evidence.
- Immutable tag, GitHub release, wheel, source distribution, and changelog
  versions agree.
- PyPI OIDC publication includes provenance and the public artifact passes an
  independent post-publication install/import/mocked-call check.
- No complete credential appears in source, fixtures, artifacts, or logs.

The first stable publication attempt created immutable release `v0.1.0` at
`6f42981edcc6c252f8db997606671c3da84d1dd8` and passed default-branch CI plus
exact artifact construction, but [stopped before any live request](https://github.com/cometapi-dev/cometapi-python/actions/runs/30348177128)
because the reusable workflow caller omitted `secrets: inherit` and GitHub
resolved the `live-smoke` environment secret as empty. PyPI publication and
registry verification were skipped. [PR #21](https://github.com/cometapi-dev/cometapi-python/pull/21)
added secret inheritance, a credential preflight, exact recovery identity
gates, and rerun rejection.

[Recovery run 30353657522](https://github.com/cometapi-dev/cometapi-python/actions/runs/30353657522)
then passed exact release verification, artifact construction, the credential
preflight, the bounded four-request live suite, and protected `pypi` approval.
PyPI rejected the upload with HTTP 400 before accepting either distribution:
the attestation certificate's Build Config URI named
`release-recovery.yml@refs/heads/main`, while the configured Trusted Publisher
expected `publish.yml`. This is a platform constraint: reusable workflows are
[unsupported by the PyPA publisher action](https://github.com/pypa/gh-action-pypi-publish/issues/166),
and [Warehouse requires the attestation identity to match the publisher](https://github.com/pypi/warehouse/issues/19814).
The first permanent correction consolidated release creation, recovery,
selection, build, protected live smoke, direct PyPI publication, and registry
verification in the single top-level `publish.yml` identity. It kept
attestations and the existing Trusted Publisher intact and reached `main` as
`ec420af2966ef683660b58acff8d125e916fc623` through
[PR #22](https://github.com/cometapi-dev/cometapi-python/pull/22).

[Recovery run 30357111315](https://github.com/cometapi-dev/cometapi-python/actions/runs/30357111315)
verified the exact immutable release and passed the shared selector from the
correct top-level workflow identity. GitHub nevertheless propagated the
intentionally skipped Release Please ancestry to the selector descendants, so
build, live smoke, publication, and registry verification were all skipped and
the overall run incorrectly reported success. No live request or registry side
effect occurred, and PyPI still returned 404 for `cometapi==0.1.0`. The
permanent control-flow fix makes every selector descendant explicitly evaluate
skipped ancestry while rejecting cancellation and reruns and requiring every
direct dependency to succeed.

[PR #23](https://github.com/cometapi-dev/cometapi-python/pull/23) pinned those
conditions in the semantic checker and mutation tests, passed
[pull-request CI run 30358662050](https://github.com/cometapi-dev/cometapi-python/actions/runs/30358662050),
squash-merged as `9cd60419130533d6920083e2f4bf295a3b5a4fd7`, and passed
[default-branch CI run 30358990834](https://github.com/cometapi-dev/cometapi-python/actions/runs/30358990834).
Fresh first-attempt
[recovery run 30359383715](https://github.com/cometapi-dev/cometapi-python/actions/runs/30359383715)
then passed the selector, exact artifact rebuild, bounded four-request live
suite, protected `pypi` approval, direct OIDC publication with attestations,
public digest and provenance checks, and the isolated PyPI install and mocked
smoke. The exact [PyPI release](https://pypi.org/project/cometapi/0.1.0/) is
public with wheel SHA256
`8eae758688bb6c98274e48d8d81f882eeae760f69cfd2f5e125004881d60e90f`
and source-distribution SHA256
`e9308b44f6091200b5121e24d1a0e1b9ea3e6bcccc109d6de87554b1ab2a8bca`.
Both files matched retained pre-publication evidence and independently verified
Trusted Publisher provenance. Recovery variables were removed immediately
after identity verification. At that closeout, `LIVE_SMOKE_ENABLED=false` was
the only remaining release-related repository variable.

## `0.1.1`: Configuration validation maintenance

Maintenance release `0.1.1` rejects explicitly blank API keys and base URLs,
treats a blank environment key as missing, and uses the default CometAPI URL
for a blank environment base URL. It trims surrounding string whitespace,
including the Node-compatible byte-order mark boundary, without changing
callable keys or `httpx.URL` values. Inherited copy helpers remain fail-closed
against provider routing, workload identity, and private-option injection.

[Fix PR #25](https://github.com/cometapi-dev/cometapi-python/pull/25) passed
[pull-request CI run 30419881169](https://github.com/cometapi-dev/cometapi-python/actions/runs/30419881169)
and squash-merged as `d02b1dba277ac72229b772d29ea1870b569edd88`.
The first authorized
[Release Please run 30420057230](https://github.com/cometapi-dev/cometapi-python/actions/runs/30420057230)
failed before creating a pull request because GitHub Actions lacked permission
to create pull requests; it created no tag, release, live request, or PyPI file.
The permission was restored while default workflow permissions remained
read-only, and
[PR #26](https://github.com/cometapi-dev/cometapi-python/pull/26) recorded the
preflight as `18de120c79b5a4fde5d125d56238f7f3b28e69bf`.

Fresh [Release Please run 30423490399](https://github.com/cometapi-dev/cometapi-python/actions/runs/30423490399)
created [release PR #27](https://github.com/cometapi-dev/cometapi-python/pull/27).
Its final head `7d24b4079b232c6c5e9b09b3d182ded230840ea8` passed all nine
required checks in
[run 30424732041](https://github.com/cometapi-dev/cometapi-python/actions/runs/30424732041)
and received an exact-head human owner approval. It squash-merged as release
commit `576e7503a0a8c1103faca5143e4b8d576f8e8b44`, which passed
[default-branch CI run 30429821579](https://github.com/cometapi-dev/cometapi-python/actions/runs/30429821579).

First-attempt
[release run 30429821548](https://github.com/cometapi-dev/cometapi-python/actions/runs/30429821548)
created and verified the immutable non-draft
[GitHub release](https://github.com/cometapi-dev/cometapi-python/releases/tag/v0.1.1)
and lightweight tag `v0.1.1` at that exact release commit. The run selected the
verified release identity, rebuilt and independently installed both artifacts,
and passed the exact-release live suite with four serial requests, at most 16
output tokens per request, a 30-second request timeout, and stop-on-first-failure.
After protected `pypi` approval, the same top-level `publish.yml` published by
OIDC with attestations and passed public registry verification.

The exact [PyPI release](https://pypi.org/project/cometapi/0.1.1/) has wheel
SHA256 `27e7904542f82fbbcd60e0de23a4a62c042420b6d004d00286d1f37d2ec4c5e5`
and source-distribution SHA256
`64c7cb87745032703b3374cc562ea00b979416c54908862dbcebd116b2dc44c8`.
Both files matched the retained pre-publication digest record. Their PyPI
Integrity API provenance names repository `cometapi-dev/cometapi-python`,
workflow `publish.yml`, environment `pypi`, release commit `576e7503`, and
[run attempt 1](https://github.com/cometapi-dev/cometapi-python/actions/runs/30429821548/attempts/1).
An independent post-workflow verification downloaded both public files,
verified their provenance with `pypi-attestations==0.0.29`, installed
`cometapi==0.1.1` from the public simple index, checked version and public
imports, and passed every supported mocked call and README example.

`RELEASE_PLEASE_ENABLED=false` and `LIVE_SMOKE_ENABLED=false`. Recovery
variables are absent. No recovery tag or recovery workflow was used.

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

The repository maintains three independently auditable workflows:

- `ci.yml`: offline lint, type, unit, contract, build, artifact, and clean
  install checks for pull requests and default-branch pushes.
- `live-smoke.yml`: scheduled and manual default-branch monitoring capped at
  four requests, 16 output tokens per generation, a 30-second request timeout,
  concurrency one, a ten-minute workflow timeout, and stop on first failure.
- `publish.yml`: the single top-level release and PyPI Trusted Publisher
  identity. Its gated push path maintains the human-reviewed Release Please PR
  and independently verifies a created release. Its explicitly enabled manual
  path recovers an independently verified existing immutable release only from
  the protected default branch. An exact selector feeds both paths into tag,
  commit, and default-branch ancestry verification, artifact rebuild, protected
  live smoke, direct PyPI OIDC publication, provenance, and registry
  verification.

All workflow files must pass local `actionlint` 1.7.12. This is static
validation only. Remote behavior remains unverified until each workflow runs
successfully in the canonical GitHub repository.

Scheduled and manually dispatched live smoke must require
`LIVE_SMOKE_ENABLED=true`; an unset or other value prevents live execution.
Release Please requires `RELEASE_PLEASE_ENABLED=true` and remains disabled
outside an explicitly authorized release sequence. Its reviewed one-time
`last-release-sha` bridge established the recovery alpha boundary, generated
the stable release PR, and was removed during human finalization. Release jobs
must resolve an unset or empty `COMETAPI_LIVE_MODEL` to `gpt-5.4` rather than
attempt a request with an empty model. Immutable-release recovery additionally
requires `RELEASE_RECOVERY_TAG` and `RELEASE_RECOVERY_SHA` to equal the exact
dispatch inputs; keep both variables absent except for one explicitly authorized
identity and delete them immediately after recovery identity verification or a
stopped run. Recovery and
publication jobs reject rerun attempts. Every job downstream of the mutually
exclusive selector must explicitly evaluate skipped ancestry, reject
cancellation, and require every direct dependency's result to equal `success`.
The PyPI action must execute directly in top-level `publish.yml`; workflow
inventory, semantic checks, and mutation tests must reject reusable publishing,
split publisher identities, additional OIDC consumers, downstream use of raw
dispatch inputs, or weakened selector-descendant conditions.

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
