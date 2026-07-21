# Security Policy

## Supported versions

The SDK is in pre-release development. Published support claims begin only
after a package is independently verified from PyPI.

| Version | Status |
| --- | --- |
| `0.1.x` prereleases | Best-effort security fixes after verified publication |
| `0.1.x` stable | Planned support after verified publication |
| Older versions | Unsupported |

## Reporting a vulnerability

Do not disclose a suspected vulnerability, credential, customer data, or
exploit details in a public issue.

Use the repository's
[private security advisory form](https://github.com/cometapi-dev/cometapi-python/security/advisories/new)
when it is available. During private validation, before GitHub Private
Vulnerability Reporting is enabled, email `support@cometapi.com` with the
subject "Security report" and only the minimum details needed to establish a
confidential follow-up channel. Do not disclose sensitive details publicly.

The maintainers will acknowledge and triage reports as soon as practical, but
no response-time service-level agreement is promised for prereleases.
Coordinated disclosure timing will be agreed with the reporter.

## Credential safety

- Create API keys only through <https://www.cometapi.com/console/token>.
- Keep keys in environment variables or an appropriate secret manager.
- Never commit keys, paste them into examples, attach them to issues, or record
  them in fixtures.
- Do not run the trusted live-smoke workflow from unreviewed code or expose its
  environment to pull requests.
- Revoke and replace a key immediately if exposure is suspected.

Users are responsible for all usage and charges incurred with their keys.

## Release security

Public packages must be produced from a reviewed immutable tag and published
to PyPI using GitHub OIDC Trusted Publishing from a protected environment.
Long-lived PyPI tokens are not an accepted publication path. A successful
upload is incomplete until provenance and a clean public-registry installation
have been verified.

Third-party GitHub Actions must be pinned to full commit SHAs. Only the
publishing job may receive `id-token: write`.

## Scope

This policy covers the SDK source, packaging, release automation, and accidental
credential disclosure caused by the SDK. Service availability, account access,
billing disputes, and model behavior are outside this repository's support
scope; maintainers must publish the appropriate service support channel.
