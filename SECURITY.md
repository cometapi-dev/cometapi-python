# Security Policy

## Supported versions

The SDK's supported 0.1 API surface is stable. Security support applies to
packages that have been independently verified from PyPI.

| Version | Status |
| --- | --- |
| `0.1.x` stable | Supported |
| `0.1.x` prereleases | Best-effort security fixes |
| Older versions | Unsupported |

## Reporting a vulnerability

Do not disclose a suspected vulnerability, credential, customer data, or
exploit details in a public issue.

Use the repository's
[private security advisory form](https://github.com/cometapi-dev/cometapi-python/security/advisories/new).
If that form is unavailable, email `support@cometapi.com` with the subject
"Security report" and only the minimum details needed to establish a
confidential follow-up channel. Do not disclose sensitive details publicly.

The maintainers will acknowledge and triage reports as soon as practical, but
no response-time service-level agreement is promised.
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

Third-party GitHub Actions must be pinned to full commit SHAs. The PyPI action
must execute directly in the top-level `publish.yml` workflow configured as the
Trusted Publisher; a reusable or split publication workflow is forbidden
because its attestation identity can differ from the publisher identity. Only
the protected publishing job may declare `id-token: write`. The protected live
job may reference `COMETAPI_KEY` only in its credential preflight and live-test
steps. Recovery verification, release selection, and downstream publication
jobs must reject workflow reruns so an old authorization cannot be replayed.

## Scope

This policy covers the SDK source, packaging, release automation, and accidental
credential disclosure caused by the SDK. Service availability, account access,
billing disputes, and model behavior are outside this repository's support
scope; maintainers must publish the appropriate service support channel.
