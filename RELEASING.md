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

Before Public Preview, initialize an empty private repository from a sanitized
first commit. Do not ask GitHub to generate a README, license, or ignore file.
The complete history must already be suitable for public visibility.

Apply these canonical values before the first push:

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

The package manifest uses `authors = [{ name = "CometAPI" }]`. Remove
`.github/CODEOWNERS` and its validation dependencies; it is not required while
the project has one active maintainer.

Before the first push, require `LIVE_SMOKE_ENABLED=true` for scheduled live
execution and keep `RELEASE_PLEASE_ENABLED` disabled through the initial manual
alpha. An unset or non-true value prevents the corresponding workflow from
running. The release live-model configuration resolves an unset or empty
`COMETAPI_LIVE_MODEL` to `gpt-5.4`.

The private stage validates sanitized history, the complete local gate, and
real credential-free default-branch CI only. Do not configure or exercise
branch or tag rules, Private Vulnerability Reporting, secrets, protected
environments, Trusted Publishing, live API calls, tags, releases, or registry
publication. Record the CI result and stop before changing visibility.

Run the fail-closed content and identity gate before the first remote push and
again before changing repository visibility:

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

Record every command, outcome, skipped check, and unavailable tool in the
verification record.

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
  workflow timeout, and stop on the first failure. Scheduled execution also
  requires `LIVE_SMOKE_ENABLED=true`.
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

Maintainers execute this sequence in order:

1. Complete the canonical identity table, replace unresolved public status
   text, remove `CODEOWNERS` and its checks, and run the local content,
   self-containment, package, secret, and workflow gates.
2. Create the empty private repository, push the sanitized first history, wait
   for real credential-free default-branch CI, record its result, and stop for
   explicit visibility-change authorization.
3. After the repository becomes public, require pull requests and blocking CI
   for `main` with zero required approvals, block force pushes and deletion,
   reserve administrator bypass for emergencies, protect version tags from
   updates and deletion, enable immutable releases and Private Vulnerability
   Reporting, and rerun default-branch CI.
4. Configure `live-smoke` with no required reviewer and `pypi` with approval by
   the current release approver and self-review allowed. Set
   `LIVE_SMOKE_ENABLED=true`, provide the authorized key, and run the protected
   budgeted live smoke. Record Public Preview readiness only after the public
   content gate and this live run pass.
5. Confirm ownership of the unscoped PyPI package `cometapi` and configure the
   Trusted Publisher for the exact repository, workflow, and `pypi`
   environment.
6. Supply `COMETAPI_KEY`, the approved `COMETAPI_LIVE_MODEL`, and explicit
   authorization for the documented four-request, 16-token, 30-second,
   concurrency-one, stop-on-failure budget before creating the GitHub
   prerelease.
7. Replace the pre-release availability notice and source-installation text in
   `README.md` with the release-neutral, maintainer-confirmed sentence
   “`0.1.0a1` is approved for PyPI publication.” Date the `0.1.0a1` heading in
   `CHANGELOG.md`, remove its candidate/unpublished wording, and rerun every
   candidate verification gate, including
   `uv run python scripts/check_version.py --expected 0.1.0a1 --require-changelog --require-releasable-docs`.
8. Review the exact candidate and create the immutable SemVer tag
   `v0.1.0-alpha.1` and corresponding GitHub prerelease. The package and Python
   metadata use the equivalent PEP 440 version `0.1.0a1`. This is the canonical
   tag spelling; do not use `v0.1.0a1`. After this initial alpha exists, enable
   Release Please for later reviewed release pull requests.
9. Allow the release workflow to prove `immutable=true`, resolve the tag to the
   checked-out commit, verify that commit is reachable from the protected
   default branch, and run the bounded protected live suite against that exact
   commit. Only successful completion makes the protected PyPI approval
   eligible; approve that job after reviewing its retained artifact digests.
10. Verify publication, provenance, public artifact identity and digest, clean
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
