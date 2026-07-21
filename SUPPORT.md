# Support Policy

## Project status

The SDK is in pre-release development. Support is best-effort, and no response
or resolution time is guaranteed.

## Supported SDK surface

Support requests may cover:

- installation and configuration of `CometAPI` and `AsyncCometAPI`;
- synchronous, asynchronous, streaming, and non-streaming Chat Completions and
  Responses calls;
- synchronous and asynchronous Models listing;
- documented OpenAI constructor option forwarding; and
- packaging, typing, or documented compatibility problems.

Inherited OpenAI methods outside `COMPATIBILITY.md`, provider-native adapters,
CometAPI account resources, media APIs, CLI behavior, service availability,
billing, quotas, and provider model output are not part of the 0.1 SDK support
contract.

## Asking for help

Use the canonical
[repository issue tracker](https://github.com/cometapi-dev/cometapi-python/issues)
for reproducible non-security bugs and questions. For private support matters,
email `support@cometapi.com`.

Include:

- Python, `cometapi`, and `openai` versions;
- operating system;
- the supported operation and mode involved;
- a minimal reproduction;
- expected and actual behavior; and
- sanitized exception type and message.

Never include API keys, authorization headers, customer prompts or responses,
account data, or other secrets. For vulnerabilities, follow `SECURITY.md`
instead of opening a detailed public issue.

## API keys and charges

Keys are created at <https://www.cometapi.com/console/token>. Users are
responsible for all usage and charges incurred with their keys. The SDK issue
tracker is not a billing or account-recovery channel; use the official service
support address, `support@cometapi.com`.
