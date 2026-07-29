# Changelog

All notable changes to this project are documented in this file. The project
follows Semantic Versioning and uses Conventional Commits for release-PR
automation.

## [Unreleased]

### Fixed

- Reject explicitly blank API keys and base URLs without fallback, treat blank
  environment keys as missing, and use the default CometAPI URL for a blank
  `COMETAPI_BASE_URL`.
- Add a fail-closed immutable-release recovery path with an environment-secret
  preflight before any live request.
- Execute PyPI Trusted Publishing directly in the single top-level
  `publish.yml` identity, and add regression gates that reject reusable
  publication, split attestation identities, and unverified recovery inputs.
- Prevent GitHub's skipped-ancestry propagation from silently skipping the
  release chain after a successful selector, while continuing to reject
  cancellation, reruns, and every non-successful direct dependency.

### Changed

- Trim leading and trailing whitespace from direct and environment string API
  keys and base URLs. Applications that intentionally supplied surrounding
  whitespace must pass the intended credential or URL without that padding;
  callable keys and `httpx.URL` objects are unchanged.

### Documentation

- Record completed stable publication, provenance, digest, and clean-install
  evidence for `cometapi==0.1.0`.

## [0.1.0] - 2026-07-28

### Features

- Prepare the stable release ([#19](https://github.com/cometapi-dev/cometapi-python/issues/19)) ([2e5407c](https://github.com/cometapi-dev/cometapi-python/commit/2e5407c106b6bc557c51e629b4713012dbce3744)).

### Documentation

- Record Registry Alpha release evidence ([#18](https://github.com/cometapi-dev/cometapi-python/issues/18)) ([f39b4dc](https://github.com/cometapi-dev/cometapi-python/commit/f39b4dc9f2e18e91ab3cbac202246f85658f71fd)).

- Release documentation now records completed Registry Alpha publication,
  provenance, digest, clean-install, import, and mocked-call verification.

## [0.1.0a1] - 2026-07-27

### Added

- `CometAPI` and `AsyncCometAPI` thin adapters over the official OpenAI SDK.
- Contract-tested Chat Completions and Responses in synchronous,
  asynchronous, streaming, and non-streaming modes.
- Contract-tested synchronous and asynchronous Models listing.
- `COMETAPI_KEY` and `COMETAPI_BASE_URL` configuration.
- Typed-package marker, mocked contracts, artifact and clean-install checks,
  self-containment verification, and offline CI definitions.
- Public contribution, conduct, security, support, architecture, compatibility,
  roadmap, and release documentation.

### Changed

- The OpenAI dependency contract is `openai>=2.45.0,<3.0.0`.
- Public client constructors now expose only named, precisely typed,
  CometAPI-compatible OpenAI options; private, arbitrary, and route-bypassing
  options are rejected.
- Release publication now requires immutable-tag/default-branch ancestry
  verification and protected live smoke against the exact release commit.
- Registry verification preserves the pre-publication digest bundle across
  checkout and compares public artifacts against those exact digests.
- Public Preview document checks report every violation together and fail
  closed on canonical identity, repository metadata, contacts, public-safe
  language, and standalone content.
- Scheduled live smoke requires the explicit repository opt-in, and release
  live smoke defaults an unset or empty model setting to `gpt-5.4`.
- Distribution metadata now exposes Support as an HTTPS link to `SUPPORT.md`;
  release checks reject non-HTTPS canonical project URLs.
- The initial GitHub prerelease uses the one-time recovery tag
  `v0.1.0-alpha.1+recovery.1` because GitHub permanently reserved the failed
  immutable release tag; the PyPI package version remains `0.1.0a1`.
- Release Please remains disabled until a separately reviewed and tested
  previous-release boundary bridges the recovery tag's build metadata.

### Removed

- Unsupported aliases `CometClient` and `AsyncCometClient`.
- Account, balance, token, log, task, and platform helpers from the 0.1 scope.
- The provisional single-maintainer `CODEOWNERS` requirement.

[0.1.0]: https://github.com/cometapi-dev/cometapi-python/compare/v0.1.0-alpha.1%2Brecovery.1...v0.1.0
