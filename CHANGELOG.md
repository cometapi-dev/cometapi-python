# Changelog

All notable changes to this project are documented in this file. The project
follows Semantic Versioning and uses Conventional Commits for release-PR
automation.

## [Unreleased]

### Changed

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
