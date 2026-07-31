# Release Guide

## Evidence states

Use these states precisely:

| State | Required evidence |
| --- | --- |
| Local code-complete | Source, tests, documentation, metadata, scripts, and workflow definitions exist and applicable offline checks pass. |
| Private Remote Validation ready | Local gates pass, the sanitized history and maintainer-confirmed identity are complete, and real credential-free private default-branch CI passes. |
| Public Preview ready | After visibility changes, public-only repository rules, security reporting, environments, default-branch CI, the content gate, and authorized protected live smoke all pass. |
| Registry Alpha candidate | The exact candidate wheel and source distribution pass metadata, file-list, clean-install, import, and mocked-call checks. |
| Registry Alpha released | The public PyPI artifact has provenance, installs cleanly, imports, and passes the post-publication mocked-call smoke. |
| Stable released | Every stable runtime, release-PR, live, example, provenance, and registry gate has separate evidence. |

A mock, successful build, valid workflow file, HTTP response, or successful
upload is evidence only for its own layer.

## Private Remote Validation

The canonical repository has completed Private Remote Validation. This section
records its one-time initialization history; it is not an instruction to
recreate the repository, rewrite the sanitized first history, or repeat the
initial push. The repository was initialized empty from a sanitized first
commit, without a generated README, license, or ignore file, and the complete
history was required to be suitable for public visibility.

The one-time initialization used these canonical values before the first push:

| Field | Required value |
| --- | --- |
| Repository | `https://github.com/cometapi-dev/cometapi-python` |
| Package author | `CometAPI` |
| Copyright | `Copyright (c) 2026 CometAPI` |
| Homepage | `https://www.cometapi.com` |
| Documentation | `https://apidoc.cometapi.com/` |
| Issues | `https://github.com/cometapi-dev/cometapi-python/issues` |
| Support and conduct | `support@cometapi.com` |
| Security | `https://github.com/cometapi-dev/cometapi-python/security/advisories/new` |

The package manifest uses `authors = [{ name = "CometAPI" }]`.
`.github/CODEOWNERS` and its validation dependencies were absent from the
completed private initialization and remain unnecessary while the project has
one active maintainer.

Before the historical first push, scheduled and manually dispatched live
execution was required to fail closed unless `LIVE_SMOKE_ENABLED=true`.
`RELEASE_PLEASE_ENABLED` was kept disabled. The reviewed stable-readiness
configuration later used an explicit `last-release-sha` bridge to establish the
recovery alpha as the previous-release boundary. Maintainers enabled the
repository variable only to start the stable release sequence, and human
finalization removed the bridge. An unset or non-true variable prevents the
corresponding gated job from executing. `RELEASE_RECOVERY_TAG` and
`RELEASE_RECOVERY_SHA` are absent by default and may exist only during an
explicitly authorized recovery of that exact existing immutable release
identity.
The release live-model configuration is fixed to the canonical active model
enforced by the workflow checker; repository variables cannot override it.

The completed private stage validated sanitized history, the complete local
gate, and real credential-free default-branch CI only. It did not configure or
exercise branch or tag rules, Private Vulnerability Reporting, secrets,
protected environments, Trusted Publishing, live API calls, tags, releases, or
registry publication. Its recorded CI result is historical evidence, not a
reason to repeat initialization.

The fail-closed content and identity gate was required before the historical
first remote push and passed again before Public Preview readiness. Keep running
it before later releases and after public-document changes:

```bash
uv run python scripts/check_version.py --require-public-preview-docs
```

## Local release-candidate checks

Run from the repository root in a clean checkout:

```bash
uv lock --check
uv sync --locked
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

Build output must contain exactly the current project version's wheel and source
distribution. Do not use an older artifact already present in `dist/`. Each
exact artifact must be installed independently outside the source tree; the
check must assert installed metadata, public exports, absence of legacy aliases,
and an offline mocked call.

Every canonical `[project.urls]` value must use HTTPS. In particular, Support
must resolve to
`https://github.com/cometapi-dev/cometapi-python/blob/main/SUPPORT.md`; the
email address in that document remains the canonical support contact.

Record every command, outcome, skipped check, and unavailable tool in the
verification record.

## Final post-merge evidence

This procedure grants no standing permission for remote writes. Run it only
when the current maintainer request explicitly authorizes the pull-request
lifecycle and its final timeline comment.

After a pre-visibility pull request is squash-merged, complete its evidence
record against the resulting default-branch commit:

1. Fetch `origin`, obtain the pull request's squash-merge SHA, verify that it is
   an ancestor of `origin/main`, and capture the current `origin/main` commit as
   the final `main` SHA.
2. Wait for the credential-free default-branch `CI` run for that final `main`
   SHA and require every blocking job to pass. Record the run URL; pull-request
   CI is not a substitute for this post-merge run.
3. Perform a read-only authorization-boundary audit. Record the repository's
   observed current visibility and other relevant observable state separately
   from the lifecycle attestation that this workflow made no visibility,
   settings, rules, secrets, or environments mutation and performed no live API,
   tag, release, or PyPI operation. Do not treat state hidden by permissions as
   affirmative evidence.
4. Follow the `AGENTS.md` branch lifecycle using only fast-forward updates, then
   require a clean worktree on `dev` with `HEAD`, local `main`, local `dev`, and
   `origin/main` equal to the final `main` SHA. Never push `dev`.
5. Add a timeline comment to the merged pull request containing its squash-merge
   SHA, the verified ancestry from that commit to the final `main` SHA, the final
   `main` SHA, default-branch CI result and URL, observed boundary-audit state,
   lifecycle attestation, and local worktree and ref state. Use that comment as
   the durable final evidence record and retain its URL.

If any required evidence fails or is unavailable, stop and report the exact
state instead of claiming completion. A commit cannot truthfully record its own
future squash-merge SHA, post-merge CI, or final comment URL; do not create
another commit to chase that circular record.

## Workflow validation

The repository wrapper pins `actionlint` 1.7.12 and verifies the release
archive checksum before caching its binary. Run:

```bash
uv run python scripts/run_actionlint.py
uv run python scripts/run_actionlint.py --offline
```

The first command downloads the pinned binary if needed and prints its version;
the second proves the verified cache can be used without another download.
`actionlint` performs static syntax and semantic validation; it is not a GitHub
Actions emulator. Until every workflow runs successfully in the canonical
repository, remote behavior remains unverified.

`scripts/check_workflows.py` separately enforces critical publication
semantics that `actionlint` cannot prove: immutable-event input, exact tag
commit, default-branch ancestry, exact-release live dependency, permission and
secret separation, and checkout-before-bundle-download ordering. Its git-backed
tests exercise accepted and rejected release histories locally; they still do
not emulate GitHub Actions.

The Release Please v5.0.0 step is pinned to
`googleapis/release-please-action@45996ed1f6d02564a971a2fa1b5860e934307cf7`,
whose immutable action metadata selects `node24`. The semantic
checker rejects any other pin so the workflow cannot silently regress to the
deprecated Node 20 runtime.

The direct PyPI publisher v1.14.1 is pinned to the reviewed commit. Its only
action-definition change from the previously reviewed publisher is the
conditional `setup-python` fallback moving from Node 20 to Node 24; the
top-level `publish.yml`, `publish` job, `pypi` environment, and Trusted
Publisher identity remain unchanged. The semantic checker requires this exact
publisher SHA.

The job invokes the pinned action release-only first with
`skip-github-pull-request: true`. That step cannot continue on error and is
never retried. If it succeeds without creating a release, PR-only maintenance
uses `skip-github-release: true`; its first attempt is the single Release Please
step allowed to continue on error, and a second identical attempt runs only
after that first PR attempt fails. A second failure ends the job. This permits
one bounded retry for mutable, idempotent branch and pull-request maintenance
without ever automatically retrying immutable tag or GitHub Release creation.

[Run 30509764960](https://github.com/cometapi-dev/cometapi-python/actions/runs/30509764960)
failed in the PR workflow with Undici/global `fetch` reporting
`other side closed`. It had built the candidate and reached the write boundary,
but created or updated no branch, pull request, tag, GitHub Release, live
request, or registry artifact. Read-only inspection ruled out a stale release
branch and missing pull-request permission. Treat that run as isolated
transport-failure evidence; do not rerun it or reinterpret it as an
authorization failure.

`CHANGELOG.md` is release-only: do not maintain an `Unreleased` placeholder.
Conventional Commits carry pending changes, and Release Please owns the newest
canonical dated section immediately after the preamble. The version gate rejects
any unmanaged `Unreleased` level-two heading so the generated layout remains
valid on every patch release.

Each validated release-evidence block contains the immutable release identity
and workflow history bound by machine-readable markers. The canonical
publication run is part of the identity; every ancillary implementation CI,
Release Please, failed-publication, or recovery URL requires an exact workflow
reference marker. The document gate rejects non-canonical URLs and undeclared,
unused, malformed, duplicate, or contradictory run identities regardless of
prose or Markdown labeling.

Release mode (`check_version.py --require-releasable-docs`) also fails closed
until project authorship, the canonical GitHub repository URL, the copyright
holder, security and support contacts, a publication-neutral README, and a
canonical dated changelog release section are present. It accepts Release
Please's native linked heading and the legacy historical heading, so release PRs
do not require a formatting-only finalization commit. Public Preview validation
reports all discovered violations in one run and still returns non-zero when any
violation exists.

`pyproject.toml` embeds `README.md` as the immutable distribution long
description. The README therefore uses the unpinned
`python -m pip install cometapi` command and unversioned project links. Release
PRs and post-release evidence changes must not introduce approval, unpublished,
or exact-version availability statements. Artifact inspection applies the same
policy to wheel `METADATA` and sdist `PKG-INFO`, so source and registry-facing
descriptions cannot drift.

## Workflow responsibilities

- `ci.yml` runs credential-free lint, type, unit, contract, package, artifact,
  and clean-install checks for pull requests and default-branch pushes.
- `live-smoke.yml` checks out and runs only the canonical default branch on
  trusted scheduled or manual events with a maintainer-approved key and the
  checker-fixed canonical model. It is ongoing monitoring only and cannot
  satisfy a release gate. It is capped at four requests, a reviewed 64/128/256
  output-token calibration choice with a 64-token default, a 30-second request
  timeout, concurrency one, a ten-minute workflow timeout, and stop on the first
  failure. Every trigger requires `LIVE_SMOKE_ENABLED=true`.
- Calibrate monitoring strictly in the order 64, 128, then 256, stopping on the
  first pass. Run at most three workflows and twelve requests. Escalate only
  when the validator reports `finish_reason=length` or an incomplete reason of
  `max_output_tokens`; authentication, routing, model, transport, timeout, API
  event, or any other failure stops calibration and blocks release.
- Before enabling `RELEASE_PLEASE_ENABLED` or merging the change intended to
  open or update a release PR, verify the effective repository setting:

  ```bash
  gh api repos/cometapi-dev/cometapi-python/actions/permissions/workflow \
    | jq -e '.default_workflow_permissions == "read" and .can_approve_pull_request_reviews == true'
  ```

  The organization policy must permit this repository setting, and the
  repository setting must remain enabled as a release-automation invariant.
  It does not grant default write access: workflow permissions remain read-only
  unless a job explicitly requests a narrower write scope. Do not disable this
  setting during release cleanup. If the check fails or is unavailable, stop
  before the default-branch merge; do not rerun the failed release workflow or
  manually replace its Release Please PR.
- The `release-please` job in `publish.yml` maintains a human-reviewed version
  and changelog pull request from Conventional Commits after maintainers enable
  the `RELEASE_PLEASE_ENABLED` repository variable. A reviewed one-time
  `last-release-sha` bridge established the recovery release boundary and was
  removed during human finalization of the stable release PR. Keep the variable
  disabled except while executing an explicitly authorized release sequence.
  The job checks for and creates an approved release through its non-retryable
  release-only invocation before it performs retryable PR-only maintenance. If
  a release is created with the GitHub workflow token, it polls the GitHub API
  until that exact tag and commit are independently reported as immutable, then
  selects it for the downstream chain in the same workflow; workflow-token
  release events do not trigger a second workflow. If the release-only
  invocation fails, immediately set `RELEASE_PLEASE_ENABLED=false`, inspect tag
  and GitHub Release state read-only, and stop. Do not make another main push or
  use recovery until the exact external state is known and recovery is
  separately authorized.
- The `verify-recovery` path in `publish.yml` is the only manual publication
  path. It requires an exact immutable tag and commit, the protected default
  branch, and the temporary `RELEASE_RECOVERY_TAG` and `RELEASE_RECOVERY_SHA`
  identity opt-in before the shared release selector can continue. Delete both
  variables immediately after success or failure.
- `publish.yml` is the single top-level release and Trusted Publisher identity.
  It accepts only a protected `main` push or an exact manual recovery dispatch,
  selects only an independently verified immutable tag and commit, resolves the
  tag to the checked-out commit, fetches the protected default branch, and
  rejects a commit that is not reachable from that branch. A protected
  `live-smoke` job then checks out that exact verified commit and must succeed
  before the protected `pypi` job becomes eligible. The workflow publishes the
  previously verified artifacts with OIDC, then checks the public package
  against the exact pre-publication digests and Trusted Publisher provenance
  before a clean install explicitly from `https://pypi.org/simple/`. The exact
  release live model is the canonical active model enforced by the workflow
  checker and cannot be overridden by repository variables.
  Because the unused Release Please or recovery path is intentionally skipped,
  every job after the selector must use `always() && !cancelled()`, reject
  reruns, and require each direct dependency's result to equal `success`. This
  makes GitHub evaluate the successful path without accepting cancellation,
  failure, or a skipped direct dependency.

Third-party Actions are pinned to full commit SHAs. Workflow permissions are
read-only by default, and only the protected publishing job declares
`id-token: write`. The PyPI action must remain directly in `publish.yml`, the
workflow filename configured in the Trusted Publisher. PyPI validates uploaded
attestations against that workflow identity, so publishing from a reusable
workflow is unsupported and must fail static review. The semantic workflow
checker enforces the single top-level identity, exact selector bindings, and
OIDC scope; the live job checks the credential before making a request.
Publishing uses a protected `pypi` environment and concurrency control.
Arbitrary-branch publication is forbidden. Manual publication is limited to the
reviewed immutable-release recovery described below.

## Alpha release checklist (completed)

For the current canonical repository, private initialization, pre-visibility
closeout, public visibility, repository protection, environments, public
default-branch CI, the one-time Public Preview live smoke, and Registry Alpha
are completed historical steps. Do not recreate or repeat them. This checklist
records the dependency order that was executed; it grants no standing
permission for later remote mutations, live requests, release actions, or
registry actions.

The recorded Public Preview invariants were re-audited before release:
protected `main` and version tags, immutable releases, Private Vulnerability
Reporting, the `live-smoke` and `pypi` environment boundaries,
`LIVE_SMOKE_ENABLED=false`, absent `CODEOWNERS`, and disabled Release Please.
Maintainers then completed these steps in order:

1. Confirmed company-managed PyPI ownership and configured the Trusted
   Publisher for the exact repository, workflow, and `pypi` environment.
2. Confirmed the protected `COMETAPI_KEY`, approved live model, and explicit
   authorization for the documented four-request, 16-token, 30-second,
   concurrency-one, stop-on-failure budget.
3. Finalized the dated changelog and prerelease documentation and reran every
   candidate verification gate, including
   `uv run python scripts/check_version.py --require-changelog --require-releasable-docs`.
4. Reviewed the exact candidate and created the one-time immutable recovery tag
   and corresponding GitHub prerelease. The exact tombstone, tag, and package
   mapping are retained in the Registry Alpha evidence block and must not be
   incremented or reused for later releases. Release Please was kept disabled
   until a separate reviewed and tested `last-release-sha` bridge established
   this recovery commit as its previous-release boundary.
5. The release workflow proved `immutable=true`, resolved the tag to the
   checked-out commit, verified that commit was reachable from the protected
   default branch, and ran the bounded protected live suite against that exact
   commit before the protected PyPI approval was granted.
6. Verified publication, provenance, public artifact identity and digest, clean
   installation, import, and the public-registry mocked-call smoke.

Missing credentials, model/budget approval, environments, publisher
configuration, protection, or approval block the publication dependency chain
and cannot be bypassed. A default-branch live smoke does not prove the exact
release artifact.

Python publication is OIDC-only. There is no token-bootstrap exception for
PyPI.

The version checker must normalize the SemVer tag and PEP 440 package spelling
to the same candidate value across the tag, release manifest, package metadata,
changelog, GitHub release, wheel, and source distribution.

### Completed Registry Alpha evidence

<!-- cometapi-release-evidence:start version=0.1.0a1 date=2026-07-27 -->
<!-- cometapi-release-identity tag=v0.1.0-alpha.1+recovery.1 commit=31b68904141489ca04932edbf305ccf88af09372 workflow-run=30261746138 wheel-sha256=a6820347317943ca22f7632acbe354dd992f31a122a6172dfe45b57960e3a093 sdist-sha256=98d86829ef14771e8b7ec180d452c6638289f49c14a39b7207be5c47cb64cde7 -->

- Metadata [PR #16](https://github.com/cometapi-dev/cometapi-python/pull/16)
  merged as `6344c2d0e2e975360b42c887275c1950b82918ee`; recovery contract
  [PR #17](https://github.com/cometapi-dev/cometapi-python/pull/17) merged as
  release commit `31b68904141489ca04932edbf305ccf88af09372`.
- Annotated tag `v0.1.0-alpha.1+recovery.1` has tag object
  `fdc4a6cce31f4534f83903f3f95e7757a4d4049f`, peels to the release commit,
  and identifies the
  [immutable GitHub prerelease](https://github.com/cometapi-dev/cometapi-python/releases/tag/v0.1.0-alpha.1%2Brecovery.1).
- [Release workflow run 30261746138](https://github.com/cometapi-dev/cometapi-python/actions/runs/30261746138)
  passed the exact artifact gates, authorized protected live smoke, protected
  environment approval, PyPI OIDC Trusted Publishing, provenance check, public
  digest comparison, clean registry installation, imports, and mocked-call
  smoke.
- The exact [PyPI release](https://pypi.org/project/cometapi/0.1.0a1/) has wheel
  SHA256 `a6820347317943ca22f7632acbe354dd992f31a122a6172dfe45b57960e3a093`
  and source-distribution SHA256
  `98d86829ef14771e8b7ec180d452c6638289f49c14a39b7207be5c47cb64cde7`.
- `LIVE_SMOKE_ENABLED=false`. Release Please remains disabled outside an
  explicitly authorized release sequence. The reviewed `last-release-sha`
  bridge generated the stable release PR and was removed during human
  finalization.

<!-- cometapi-release-evidence:end version=0.1.0a1 date=2026-07-27 -->

## Stable release sequence

```text
feature or fix pull request
    -> required offline CI
    -> merge to the default branch
    -> automated release pull request
    -> human review of generated versions, changelog, and durable metadata
    -> required release-PR CI, review, and merge
    -> immutable tag and GitHub release
    -> bounded API verification of immutable tag and commit identity
    -> same top-level workflow selects the independently verified release
    -> verify immutable tag commit and protected-default-branch ancestry
    -> rebuild and verify exact artifacts
    -> protected live smoke against that exact commit
    -> protected PyPI OIDC publication
    -> provenance verification
    -> public-registry install/import/mocked-call smoke
    -> roadmap milestone marked released
```

The first stable release additionally required the complete blocking Python matrix,
executed README examples against the built package, trusted live evidence, and
reviewed release-PR and changelog agreement. Its one-time finalization removed
the `last-release-sha` and prerelease-versioning controls. Later maintenance
releases keep those controls absent and must retain publication-neutral README
metadata throughout the release and post-release sequence. The manifest,
project metadata, lock file, and changelog must remain at the exact generated
version. If GitHub requires approval before checks run on the automated pull
request, approve only that reviewed workflow execution and wait for every
blocking check.

## Immutable release publication recovery

Use recovery only when an immutable GitHub release exists, its protected
publication chain stopped before PyPI accepted the version, and a reviewed fix
has already reached `main`. Do not create another tag or release, change the
existing release, bypass live smoke, or publish an artifact retained from the
failed run.

Before dispatch, verify that the exact PyPI version is absent, the release is
immutable and non-draft, its tag resolves to the supplied commit, that commit is
reachable from protected `main`, and PyPI's Trusted Publisher names
`publish.yml`. Confirm that the PyPI action still executes directly in that
top-level workflow. Then enable only the one-time recovery gate and dispatch
the workflow from `main` with the exact immutable identity:

```bash
gh variable set RELEASE_RECOVERY_TAG --body '<exact-tag>'
gh variable set RELEASE_RECOVERY_SHA --body '<exact-commit>'
gh workflow run publish.yml --ref main \
  -f release-tag='<exact-tag>' \
  -f release-sha='<exact-commit>'
```

The run must rebuild and verify the exact tag, pass the credential preflight and
bounded four-request live suite, wait for protected `pypi` approval, publish by
OIDC, verify provenance and public digests, and pass the registry clean-install
smoke. Delete the gate as soon as `verify-recovery` succeeds; if verification
never succeeds, delete it immediately when the run stops:

```bash
gh variable delete RELEASE_RECOVERY_TAG
gh variable delete RELEASE_RECOVERY_SHA
```

A recovery failure stops the sequence. Diagnose and land a separate reviewed
fix before requesting another explicit recovery authorization; do not rerun a
failed job merely to obtain a different result. The workflow enforces this by
allowing only `github.run_attempt == 1` for verification, selection, build,
live smoke, publication, and registry verification. Every selector descendant
also evaluates skipped ancestry with `always() && !cancelled()` and requires
each direct dependency's result to equal `success`.

[Recovery run 30353657522](https://github.com/cometapi-dev/cometapi-python/actions/runs/30353657522)
passed immutable identity verification, the exact artifact rebuild, credential
preflight, four-request live suite, and protected `pypi` approval. PyPI then
rejected the upload before accepting any distribution because the reusable
caller produced an attestation Build Config URI for `release-recovery.yml`
while the Trusted Publisher expected `publish.yml`. The permanent correction
keeps attestations enabled and moves the PyPI action into the single top-level
`publish.yml`; it does not weaken or reconfigure the Trusted Publisher.

[Recovery run 30357111315](https://github.com/cometapi-dev/cometapi-python/actions/runs/30357111315)
then passed immutable recovery verification and the shared release selector,
but GitHub propagated the intentionally skipped Release Please ancestry to the
plain downstream job conditions. Build, live smoke, publication, and registry
verification were all skipped while the overall workflow incorrectly reported
success. No live request or PyPI upload occurred, and the stable distribution
remained absent. The permanent correction explicitly evaluates every selector descendant
and requires all of its direct dependencies to succeed. A further recovery
remained blocked until that fix reached `main` and a new recovery was explicitly
authorized.

### Completed first stable release evidence

<!-- cometapi-release-evidence:start version=0.1.0 date=2026-07-28 -->
<!-- cometapi-release-identity tag=v0.1.0 commit=6f42981edcc6c252f8db997606671c3da84d1dd8 workflow-run=30359383715 wheel-sha256=8eae758688bb6c98274e48d8d81f882eeae760f69cfd2f5e125004881d60e90f sdist-sha256=e9308b44f6091200b5121e24d1a0e1b9ea3e6bcccc109d6de87554b1ab2a8bca -->
<!-- cometapi-release-workflow-reference run=30358662050 -->
<!-- cometapi-release-workflow-reference run=30358990834 -->


- The immutable non-draft [GitHub release](https://github.com/cometapi-dev/cometapi-python/releases/tag/v0.1.0)
  and lightweight tag `v0.1.0` resolve to release commit
  `6f42981edcc6c252f8db997606671c3da84d1dd8` on protected `main`.
- Selector-descendant fix [PR #23](https://github.com/cometapi-dev/cometapi-python/pull/23)
  passed [pull-request CI run 30358662050](https://github.com/cometapi-dev/cometapi-python/actions/runs/30358662050),
  squash-merged as `9cd60419130533d6920083e2f4bf295a3b5a4fd7`, and passed
  [default-branch CI run 30358990834](https://github.com/cometapi-dev/cometapi-python/actions/runs/30358990834).
- Fresh first-attempt
  [recovery run 30359383715](https://github.com/cometapi-dev/cometapi-python/actions/runs/30359383715)
  passed immutable identity verification, the shared selector, an exact rebuild,
  the bounded four-request live suite, protected `pypi` approval, direct
  top-level OIDC publication with attestations, public digest and provenance
  verification, and the isolated public-registry install and mocked-call smoke.
- The exact [PyPI release](https://pypi.org/project/cometapi/0.1.0/) has wheel
  SHA256 `8eae758688bb6c98274e48d8d81f882eeae760f69cfd2f5e125004881d60e90f`
  and source-distribution SHA256
  `e9308b44f6091200b5121e24d1a0e1b9ea3e6bcccc109d6de87554b1ab2a8bca`.
  Both public files matched the retained pre-publication digest record and
  Trusted Publisher provenance independently verified against this repository.
- The immediate one-attempt local simple-index install encountered PyPI CDN
  propagation and still saw only `0.1.0a1`. The documented bounded retry then
  installed `cometapi==0.1.0`, verified the public imports and version, and
  passed all README mocked-call examples.
- `RELEASE_RECOVERY_TAG` and `RELEASE_RECOVERY_SHA` were deleted immediately
  after recovery identity verification. At that closeout,
  `LIVE_SMOKE_ENABLED=false` was the only remaining release-related repository
  variable.

<!-- cometapi-release-evidence:end version=0.1.0 date=2026-07-28 -->

### Completed configuration maintenance release evidence

<!-- cometapi-release-evidence:start version=0.1.1 date=2026-07-29 -->
<!-- cometapi-release-identity tag=v0.1.1 commit=576e7503a0a8c1103faca5143e4b8d576f8e8b44 workflow-run=30429821548 wheel-sha256=27e7904542f82fbbcd60e0de23a4a62c042420b6d004d00286d1f37d2ec4c5e5 sdist-sha256=64c7cb87745032703b3374cc562ea00b979416c54908862dbcebd116b2dc44c8 -->
<!-- cometapi-release-workflow-reference run=30419881169 -->
<!-- cometapi-release-workflow-reference run=30420057230 -->
<!-- cometapi-release-workflow-reference run=30423490399 -->
<!-- cometapi-release-workflow-reference run=30424732041 -->
<!-- cometapi-release-workflow-reference run=30429821579 -->


- Configuration fix [PR #25](https://github.com/cometapi-dev/cometapi-python/pull/25)
  passed [pull-request CI run 30419881169](https://github.com/cometapi-dev/cometapi-python/actions/runs/30419881169)
  and squash-merged as `d02b1dba277ac72229b772d29ea1870b569edd88`.
- The first
  [Release Please run 30420057230](https://github.com/cometapi-dev/cometapi-python/actions/runs/30420057230)
  failed before creating a pull request because the repository had not enabled
  GitHub Actions pull-request creation. It created no tag, release, live
  request, or PyPI file. The repository-level permission was restored without
  changing the read-only default workflow permission, and
  [PR #26](https://github.com/cometapi-dev/cometapi-python/pull/26)
  recorded the required preflight as
  `18de120c79b5a4fde5d125d56238f7f3b28e69bf`.
- Fresh [Release Please run 30423490399](https://github.com/cometapi-dev/cometapi-python/actions/runs/30423490399)
  created [release PR #27](https://github.com/cometapi-dev/cometapi-python/pull/27).
  Its final head `7d24b4079b232c6c5e9b09b3d182ded230840ea8` passed
  [all required CI in run 30424732041](https://github.com/cometapi-dev/cometapi-python/actions/runs/30424732041),
  received human owner approval at that exact head, and squash-merged as
  `576e7503a0a8c1103faca5143e4b8d576f8e8b44`. The release commit passed
  [default-branch CI run 30429821579](https://github.com/cometapi-dev/cometapi-python/actions/runs/30429821579).
- First-attempt [release run 30429821548](https://github.com/cometapi-dev/cometapi-python/actions/runs/30429821548)
  created and verified immutable non-draft release
  [v0.1.1](https://github.com/cometapi-dev/cometapi-python/releases/tag/v0.1.1)
  at the exact release commit, rebuilt and clean-installed both artifacts,
  passed the four-request exact-release live suite, received protected `pypi`
  approval, published directly from top-level `publish.yml` by OIDC with
  attestations, and passed public registry verification.
- The exact [PyPI release](https://pypi.org/project/cometapi/0.1.1/) has wheel
  SHA256 `27e7904542f82fbbcd60e0de23a4a62c042420b6d004d00286d1f37d2ec4c5e5`
  and source-distribution SHA256
  `64c7cb87745032703b3374cc562ea00b979416c54908862dbcebd116b2dc44c8`.
  Both files match the retained pre-publication digest record. PyPI Integrity
  API provenance identifies repository `cometapi-dev/cometapi-python`, workflow
  `publish.yml`, environment `pypi`, release commit `576e7503`, and release
  [run attempt 1](https://github.com/cometapi-dev/cometapi-python/actions/runs/30429821548/attempts/1).
- An independent post-workflow verification downloaded both public files,
  verified both provenance records with `pypi-attestations==0.0.29`, installed
  `cometapi==0.1.1` from `https://pypi.org/simple/`, verified the public version
  and imports, and passed supported mocked calls plus all README examples.
- `RELEASE_PLEASE_ENABLED=false` and `LIVE_SMOKE_ENABLED=false`.
  `RELEASE_RECOVERY_TAG` and `RELEASE_RECOVERY_SHA` are absent; no recovery tag
  or recovery workflow was used for `0.1.1`.

<!-- cometapi-release-evidence:end version=0.1.1 date=2026-07-29 -->

### Completed release-metadata maintenance evidence

<!-- cometapi-release-evidence:start version=0.1.2 date=2026-07-30 -->
<!-- cometapi-release-identity tag=v0.1.2 commit=710c56491d9ef5f47cccff3ce837ab7e799455b0 workflow-run=30515861246 wheel-sha256=3f12c26ae1ae7a1de5ac19d8ef27a784b2bf592143c716493f1b0f35ec19daca sdist-sha256=21c8edc0586610de1a9a8cd39b54ed23d2b1e20552100f69f53938cb7678da3d -->
<!-- cometapi-release-workflow-reference run=30509063138 -->
<!-- cometapi-release-workflow-reference run=30509764960 -->
<!-- cometapi-release-workflow-reference run=30510887049 -->
<!-- cometapi-release-workflow-reference run=30511071674 -->
<!-- cometapi-release-workflow-reference run=30511373822 -->
<!-- cometapi-release-workflow-reference run=30515861285 -->


- Metadata and runtime [PR #29](https://github.com/cometapi-dev/cometapi-python/pull/29)
  made packaged long descriptions release-neutral, added artifact assertions,
  pinned Release Please v5 to its Node 24 action commit, passed
  [CI run 30509063138](https://github.com/cometapi-dev/cometapi-python/actions/runs/30509063138),
  and squash-merged as `67bd1893983c724d1cc81b824106b7c3d9418e97`.
- [Release Please run 30509764960](https://github.com/cometapi-dev/cometapi-python/actions/runs/30509764960)
  encountered an Undici/global `fetch` closed-connection race and created or
  updated no Git tree, commit, ref, pull request, tag, release, live request, or
  registry state.
  Transport-boundary [PR #31](https://github.com/cometapi-dev/cometapi-python/pull/31)
  separated non-retryable immutable release creation from one bounded retry of
  mutable PR maintenance, passed
  [CI run 30510887049](https://github.com/cometapi-dev/cometapi-python/actions/runs/30510887049),
  and squash-merged as `a411bf5c4aeba341a2d4520a023ad0fe2c5ccee3`.
- Fresh first-attempt
  [Release Please run 30511071674](https://github.com/cometapi-dev/cometapi-python/actions/runs/30511071674)
  created and maintained
  [release PR #32](https://github.com/cometapi-dev/cometapi-python/pull/32).
  Its final head `322fdf40585f46aef64bc8b881ee2ce36c09c951` passed
  [all required CI in run 30511373822](https://github.com/cometapi-dev/cometapi-python/actions/runs/30511373822),
  received human owner approval at that exact head, and squash-merged as release
  commit `710c56491d9ef5f47cccff3ce837ab7e799455b0`. The release commit passed
  [default-branch CI run 30515861285](https://github.com/cometapi-dev/cometapi-python/actions/runs/30515861285).
- First-attempt
  [release run 30515861246](https://github.com/cometapi-dev/cometapi-python/actions/runs/30515861246)
  created and independently verified immutable non-draft release
  [v0.1.2](https://github.com/cometapi-dev/cometapi-python/releases/tag/v0.1.2)
  at the exact release commit, rebuilt and clean-installed both artifacts,
  passed the bounded four-request exact-release live suite, received protected
  `pypi` approval, published directly from top-level `publish.yml` by OIDC with
  attestations, and passed public registry verification.
- The exact [PyPI release](https://pypi.org/project/cometapi/0.1.2/) has wheel
  SHA256 `3f12c26ae1ae7a1de5ac19d8ef27a784b2bf592143c716493f1b0f35ec19daca`
  and source-distribution SHA256
  `21c8edc0586610de1a9a8cd39b54ed23d2b1e20552100f69f53938cb7678da3d`.
  Both files match the retained pre-publication digest record. PyPI Integrity
  API provenance identifies repository `cometapi-dev/cometapi-python`, workflow
  `publish.yml`, environment `pypi`, release commit `710c5649`, and release
  [run attempt 1](https://github.com/cometapi-dev/cometapi-python/actions/runs/30515861246/attempts/1).
- An independent post-workflow verification downloaded both public files,
  verified both provenance records with `pypi-attestations==0.0.29`, installed
  `cometapi==0.1.2` from `https://pypi.org/simple/`, verified the public version
  and imports, and passed supported mocked calls plus all README examples. The
  wheel metadata contains the release-neutral 0.1.x installation guidance.
- `RELEASE_PLEASE_ENABLED=false` and `LIVE_SMOKE_ENABLED=false`.
  `RELEASE_RECOVERY_TAG` and `RELEASE_RECOVERY_SHA` are absent; no recovery tag,
  workflow dispatch, or workflow rerun was used for `0.1.2`.

<!-- cometapi-release-evidence:end version=0.1.2 date=2026-07-30 -->

### Completed release-claim maintenance evidence

<!-- cometapi-release-evidence:start version=0.1.3 date=2026-07-30 -->
<!-- cometapi-release-identity tag=v0.1.3 commit=45429f373bbd11314ec43ba81904fdbb78db2522 workflow-run=30550536000 wheel-sha256=9ac2f8062a8554943649bffd7ec859fc90491f76bbe2b0165327722201417d6f sdist-sha256=07ded54606d50f44b689dad38cf93a74e1175370efaa33be84a3c01240d48e66 -->
<!-- cometapi-release-workflow-reference run=30547956809 -->
<!-- cometapi-release-workflow-reference run=30548315785 -->
<!-- cometapi-release-workflow-reference run=30548348489 -->
<!-- cometapi-release-workflow-reference run=30548842807 -->
<!-- cometapi-release-workflow-reference run=30550533622 -->


- Mutable-release-claim [PR #34](https://github.com/cometapi-dev/cometapi-python/pull/34)
  removed the published patch number from persistent guidance and extended the
  existing document/version checker through pull-request CI, release source and
  artifact verification, copied standalone repositories, wheel metadata, and
  source-distribution documents. It passed
  [CI run 30547956809](https://github.com/cometapi-dev/cometapi-python/actions/runs/30547956809)
  and squash-merged as `c5b422cdff9d3751323b0aa470091b09db253d1e`.
  Its mutation coverage rejects mutable current/latest claims, permits
  immutable historical evidence, and accepts a synchronized next-patch
  candidate without any persistent-document version edit.
- First-attempt
  [Release Please run 30548315785](https://github.com/cometapi-dev/cometapi-python/actions/runs/30548315785)
  created [release PR #35](https://github.com/cometapi-dev/cometapi-python/pull/35).
  The generated head `4728f111ada71cfb538da35ad14a5540294d2338`
  failed
  [CI run 30548348489](https://github.com/cometapi-dev/cometapi-python/actions/runs/30548348489)
  because its link-style changelog heading did not satisfy the required dated
  release heading. Finalization commit
  `b26c6e645fec131e9b1cd9360bf79651c32808ce` made only that correction, passed
  [all required CI in run 30548842807](https://github.com/cometapi-dev/cometapi-python/actions/runs/30548842807),
  received exact-head human owner approval, and squash-merged as release commit
  `45429f373bbd11314ec43ba81904fdbb78db2522`. The release commit passed
  [default-branch CI run 30550533622](https://github.com/cometapi-dev/cometapi-python/actions/runs/30550533622).
- First-attempt
  [release run 30550536000](https://github.com/cometapi-dev/cometapi-python/actions/runs/30550536000)
  created and independently verified immutable non-draft release
  [v0.1.3](https://github.com/cometapi-dev/cometapi-python/releases/tag/v0.1.3)
  and its lightweight tag at the exact release commit, rebuilt and
  clean-installed both artifacts, passed the bounded four-request exact-release
  live suite, received protected `pypi` approval, published directly from
  top-level `publish.yml` by OIDC with attestations, and passed public registry
  verification.
- The exact [PyPI release](https://pypi.org/project/cometapi/0.1.3/) has wheel
  SHA256 `9ac2f8062a8554943649bffd7ec859fc90491f76bbe2b0165327722201417d6f`
  and source-distribution SHA256
  `07ded54606d50f44b689dad38cf93a74e1175370efaa33be84a3c01240d48e66`.
  Both files match the retained pre-publication digest record. PyPI Integrity
  API provenance identifies repository `cometapi-dev/cometapi-python`, workflow
  `publish.yml`, environment `pypi`, release commit `45429f37`, and release
  [run attempt 1](https://github.com/cometapi-dev/cometapi-python/actions/runs/30550536000/attempts/1).
- Independent post-workflow verification downloaded both public files,
  verified both provenance records with `pypi-attestations==0.0.29`, installed
  `cometapi==0.1.3` from `https://pypi.org/simple/`, verified the public version
  and imports, passed the canonical supported-operation mocked-call smoke and
  all four README examples, and then passed the release commit's full ten-case
  supported-operation contract suite against that public installation. The
  workflow's first registry probe observed CDN propagation lag; its bounded
  retry passed.
- `RELEASE_PLEASE_ENABLED=false` and `LIVE_SMOKE_ENABLED=false`.
  `RELEASE_RECOVERY_TAG` and `RELEASE_RECOVERY_SHA` are absent; no recovery tag,
  workflow dispatch, or release-workflow rerun was used for `0.1.3`.

<!-- cometapi-release-evidence:end version=0.1.3 date=2026-07-30 -->
