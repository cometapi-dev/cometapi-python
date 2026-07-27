# Release Guide

## Evidence states

Use these states precisely:

| State | Required evidence |
| --- | --- |
| Local code-complete | Source, tests, documentation, metadata, scripts, and workflow definitions exist and applicable offline checks pass. |
| Private Remote Validation ready | Local gates pass, the sanitized history and maintainer-confirmed identity are complete, and real credential-free private default-branch CI passes. |
| Public Preview ready | After visibility changes, public-only repository rules, security reporting, environments, default-branch CI, the content gate, and authorized protected live smoke all pass. |
| Registry Alpha candidate | The exact `0.1.0a1` wheel and source distribution pass metadata, file-list, clean-install, import, and mocked-call checks. |
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
execution was required to fail closed unless `LIVE_SMOKE_ENABLED=true`, and
`RELEASE_PLEASE_ENABLED` was kept disabled through the initial manual alpha. An
unset or non-true value prevents the corresponding gated job from executing.
The release live-model configuration resolves an unset or empty
`COMETAPI_LIVE_MODEL` to `gpt-5.4`.

The completed private stage validated sanitized history, the complete local
gate, and real credential-free default-branch CI only. It did not configure or
exercise branch or tag rules, Private Vulnerability Reporting, secrets,
protected environments, Trusted Publishing, live API calls, tags, releases, or
registry publication. Its recorded CI result is historical evidence, not a
reason to repeat initialization.

The fail-closed content and identity gate was required before the historical
first remote push and passed again before Public Preview readiness. Keep running
it before Registry Alpha preparation and after public-document changes:

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

Build output must contain exactly the intended `0.1.0a1` wheel and source
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

Release mode (`check_version.py --require-releasable-docs`) also fails closed
until project authorship, the canonical GitHub repository URL, the copyright
holder, security and support contacts, and the approved README/changelog
release state are present. Public Preview validation reports all discovered
violations in one run and still returns non-zero when any violation exists.

## Workflow responsibilities

- `ci.yml` runs credential-free lint, type, unit, contract, package, artifact,
  and clean-install checks for pull requests and default-branch pushes.
- `live-smoke.yml` checks out and runs only the canonical default branch on
  trusted scheduled or manual events with a maintainer-approved key and model. It
  is ongoing monitoring only and cannot satisfy a release gate. It is capped at
  four requests, 16 output tokens
  per generation, a 30-second request timeout, concurrency one, a ten-minute
  workflow timeout, and stop on the first failure. Every trigger requires
  `LIVE_SMOKE_ENABLED=true`.
- `release-please.yml` maintains a human-reviewed version and changelog pull
  request from Conventional Commits after maintainers enable the
  `RELEASE_PLEASE_ENABLED` repository variable. Keep it disabled until the
  initial `v0.1.0-alpha.1` tag exists because the checked-in manifest seeds the
  next release from the equivalent package version `0.1.0a1`.
- `publish.yml` runs only for a published immutable GitHub release. It resolves
  the tag to the checked-out commit, fetches the protected default branch, and
  rejects a commit that is not reachable from that branch. A protected
  `live-smoke` job then checks out that exact verified commit and must succeed
  before the protected `pypi` job becomes eligible. The workflow publishes the
  previously verified artifacts with OIDC, then checks the public package
  against the exact pre-publication digests and Trusted Publisher provenance
  before a clean install explicitly from `https://pypi.org/simple/`. An unset
  or empty live-model repository variable resolves to `gpt-5.4`.

Third-party Actions are pinned to full commit SHAs. Workflow permissions are
read-only by default; only the publishing job receives `id-token: write`.
Publishing uses a protected `pypi` environment and concurrency control.
Arbitrary-branch and manual publication are forbidden.

## Alpha release checklist

For the current canonical repository, private initialization, pre-visibility
closeout, public visibility, repository protection, environments, public
default-branch CI, and the one-time Public Preview live smoke are completed
historical prerequisites. Do not recreate or repeat them. The next external
actions prepare Registry Alpha and require separate explicit authorization.
This checklist defines dependency order, not standing permission: every remote
mutation, live request, release action, and registry action must be explicitly
authorized in the current maintainer request; stop otherwise.

Before continuing, re-audit the recorded Public Preview invariants: protected
`main` and version tags, immutable releases, Private Vulnerability Reporting,
the `live-smoke` and `pypi` environment boundaries, `LIVE_SMOKE_ENABLED=false`,
absent `CODEOWNERS`, and disabled Release Please. Maintainers then execute the
remaining authorized steps in order:

1. Confirm that the company-managed PyPI identity `dev@cometapi.com` owns or can
   create the unscoped PyPI package `cometapi`, and configure the
   Trusted Publisher for the exact repository, workflow, and `pypi`
   environment.
2. Confirm the protected `COMETAPI_KEY`, the approved `COMETAPI_LIVE_MODEL`,
   and explicit authorization for the documented four-request, 16-token, 30-second,
   concurrency-one, stop-on-failure budget before creating the GitHub
   prerelease.
3. Replace the pre-release availability notice and source-installation text in
   `README.md` with the release-neutral, maintainer-confirmed sentence
   “`0.1.0a1` is approved for PyPI publication.” Date the `0.1.0a1` heading in
   `CHANGELOG.md`, remove its candidate/unpublished wording, and rerun every
   candidate verification gate, including
   `uv run python scripts/check_version.py --expected 0.1.0a1 --require-changelog --require-releasable-docs`.
4. Review the exact candidate and create the immutable SemVer tag
   `v0.1.0-alpha.1` and corresponding GitHub prerelease. The package and Python
   metadata use the equivalent PEP 440 version `0.1.0a1`. This is the canonical
   tag spelling; do not use `v0.1.0a1`. After this initial alpha exists, enable
   Release Please for later reviewed release pull requests.
5. Allow the release workflow to prove `immutable=true`, resolve the tag to the
   checked-out commit, verify that commit is reachable from the protected
   default branch, and run the bounded protected live suite against that exact
   commit. Only successful completion makes the protected PyPI approval
   eligible; approve that job after reviewing its retained artifact digests.
6. Verify publication, provenance, public artifact identity and digest, clean
   installation, import, and the public-registry mocked-call smoke.

Missing credentials, model/budget approval, environments, publisher
configuration, protection, or approval block the publication dependency chain
and cannot be bypassed. A default-branch live smoke does not prove the exact
release artifact.

Python publication is OIDC-only. There is no token-bootstrap exception for
PyPI.

The version checker must normalize the SemVer tag and PEP 440 package spelling
to the same `0.1.0a1` value across the tag, release manifest, package metadata,
changelog, GitHub release, wheel, and source distribution.

## Stable release sequence

```text
feature or fix pull request
    -> required offline CI
    -> merge to the default branch
    -> automated release pull request
    -> human review and merge
    -> immutable tag and GitHub release
    -> verify immutable tag commit and protected-default-branch ancestry
    -> rebuild and verify exact artifacts
    -> protected live smoke against that exact commit
    -> protected PyPI OIDC publication
    -> provenance verification
    -> public-registry install/import/mocked-call smoke
    -> roadmap milestone marked released
```

Stable `0.1.0` additionally requires the complete blocking Python matrix,
executed README examples against the built package, trusted live evidence, and
reviewed release-PR and changelog agreement.
