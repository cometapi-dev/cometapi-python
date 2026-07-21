#!/usr/bin/env python3
"""Enforce release-workflow trust invariants that actionlint cannot prove."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

try:
    from ._checks import PROJECT_ROOT, CheckError
except ImportError:  # Direct execution from the repository root.
    from _checks import PROJECT_ROOT, CheckError


def _require(text: str, needle: str, message: str) -> None:
    if needle not in text:
        raise CheckError(message)


def _require_pattern(text: str, pattern: str, message: str) -> None:
    if re.search(pattern, text) is None:
        raise CheckError(message)


def _job(text: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^  {re.escape(name)}:\n(?P<body>.*?)(?=^  [a-zA-Z0-9_-]+:\n|\Z)",
        text,
    )
    if match is None:
        raise CheckError(f"publish workflow has no {name!r} job")
    return match.group(0)


def _step(job: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^      - name: {re.escape(name)}\n(?P<body>.*?)(?=^      - name: |\Z)",
        job,
    )
    if match is None:
        raise CheckError(f"publish workflow has no {name!r} step")
    return match.group(0)


def check_action_pins(text: str, source: str) -> None:
    for match in re.finditer(r"(?m)^\s*uses:\s*([^@\s]+)@([^\s#]+)", text):
        action, reference = match.groups()
        if re.fullmatch(r"[0-9a-f]{40}", reference) is None:
            raise CheckError(f"{source}: {action} must be pinned to a full commit SHA")


def check_ci_workflow(text: str) -> None:
    """Require credential-free CI to cover every private-validation evidence layer."""
    _prefix, separator, _jobs = text.partition("\njobs:\n")
    if not separator:
        raise CheckError("CI workflow has no jobs mapping")
    for needle, message in (
        ("pull_request:", "CI must run for pull requests"),
        ("push:\n    branches:\n      - main", "CI must run for default-branch pushes"),
        ("run: uv lock --check", "CI must verify lock consistency"),
        (
            "run: uv run python scripts/check_version.py --require-public-preview-docs",
            "CI must enforce canonical public content and identity",
        ),
        (
            "run: python scripts/check_repository_independence.py",
            "CI must run standalone copied-checkout verification",
        ),
        (
            'python-version: ["3.10", "3.11", "3.12", "3.13", "3.14"]',
            "CI must block on every supported Python runtime",
        ),
        (
            'run: uv pip install --python .venv/bin/python "openai==2.45.0"',
            "CI must cover the minimum supported OpenAI version",
        ),
    ):
        _require(text, needle, message)
    if re.search(r"\$\{\{\s*secrets\.", text, flags=re.IGNORECASE):
        raise CheckError("credential-free CI must not reference repository secrets")


def check_release_please_workflow(text: str) -> None:
    """Require Release Please to remain explicitly disabled by default."""
    prefix, separator, jobs = text.partition("\njobs:\n")
    if not separator:
        raise CheckError("release-please workflow has no jobs mapping")
    _require(
        prefix,
        "on:\n  push:\n    branches:\n      - main",
        "Release Please must run only for default-branch pushes",
    )
    if "workflow_dispatch:" in prefix or "release:" in prefix:
        raise CheckError("Release Please must not accept manual or release events")
    _require(
        jobs,
        "if: vars.RELEASE_PLEASE_ENABLED == 'true'",
        "Release Please must require RELEASE_PLEASE_ENABLED=true",
    )
    if "secrets." in text:
        raise CheckError("Release Please must not depend on repository credentials")


def check_publish_workflow(text: str, live_smoke_text: str) -> None:
    """Validate fail-closed publication, live, permission, and evidence ordering."""
    prefix, separator, _jobs = text.partition("\njobs:\n")
    if not separator:
        raise CheckError("publish workflow has no jobs mapping")
    _require(
        prefix,
        "on:\n  release:\n    types:\n      - published",
        "publication must be triggered only by a published GitHub release",
    )
    if "workflow_dispatch:" in prefix or "push:" in prefix:
        raise CheckError("production publication must not accept manual, push, or arbitrary refs")
    _require_pattern(
        prefix,
        r"(?m)^permissions:\n  contents: read$",
        "workflow permissions must default to contents: read",
    )
    _require_pattern(
        prefix,
        r"(?m)^concurrency:\n  group: pypi-publish\n  cancel-in-progress: false$",
        "publication must serialize all releases without cancellation",
    )
    if re.search(r"(?m)^\s+[\"']?(?:if|continue-on-error)[\"']?\s*:", text):
        raise CheckError("release gates must not be conditional or allowed to continue on error")
    shell_text = re.sub(r"\$\{\{[^}]*\}\}", "", text)
    if "||" in shell_text or re.search(r"(?m)^\s*set\s+\+e(?:\s|$)", shell_text):
        raise CheckError("release gate commands must not swallow shell failures")
    if re.search(r"(?m)^\s*[\"']?permissions[\"']?\s*:\s*(?:write-all|read-all)\s*$", text):
        raise CheckError("release workflow permissions must use explicit read-only job maps")
    write_permissions = re.findall(r"(?m)^\s+[\"']?([a-z-]+)[\"']?\s*:\s*write\s*$", text)
    if write_permissions != ["id-token"]:
        raise CheckError("id-token: write on the publish job must be the only write permission")

    _require_pattern(
        live_smoke_text,
        r"(?m)^concurrency:\n  group: trusted-live-smoke\n  cancel-in-progress: false$",
        "release and monitoring live smokes must share one non-cancelling concurrency group",
    )
    _require(
        live_smoke_text,
        "(github.event_name == 'workflow_dispatch' || vars.LIVE_SMOKE_ENABLED == 'true')",
        "scheduled live smoke must require LIVE_SMOKE_ENABLED=true",
    )
    _require(
        live_smoke_text,
        "github.ref == format('refs/heads/{0}', github.event.repository.default_branch)",
        "monitoring live smoke must run only against the canonical default branch",
    )

    build = _job(text, "build")
    _require_pattern(
        build,
        r"(?m)^    permissions:\n      contents: read$",
        "verified build permissions must be explicitly read-only",
    )
    for needle, message in (
        (
            "release-commit: ${{ steps.trust.outputs.release-commit }}",
            "build must expose the verified release commit",
        ),
        (
            "ref: refs/tags/${{ github.event.release.tag_name }}",
            "build must check out the published tag ref",
        ),
        ("fetch-depth: 0", "build must fetch history for ancestry validation"),
        (
            "DEFAULT_BRANCH: ${{ github.event.repository.default_branch }}",
            "trust validation must use the protected default branch",
        ),
        (
            "RELEASE_IMMUTABLE: ${{ github.event.release.immutable }}",
            "trust validation must receive release.immutable",
        ),
        (
            "RELEASE_TAG: ${{ github.event.release.tag_name }}",
            "trust validation must receive the release tag",
        ),
        (
            "run: bash scripts/verify_release_trust.sh",
            "build must execute the tested release-trust verifier",
        ),
        (
            "run: uv run python scripts/check_workflows.py",
            "release build must run the local workflow semantic check",
        ),
    ):
        _require(build, needle, message)
    if "id-token: write" in build or "secrets.COMETAPI_KEY" in build:
        raise CheckError(
            "build must receive neither OIDC publication permission nor live credentials"
        )

    live = _job(text, "release-live-smoke")
    _require_pattern(
        live,
        r"(?m)^    permissions:\n      contents: read$",
        "release live-smoke permissions must be explicitly read-only",
    )
    for needle, message in (
        ("needs:\n      - build", "exact-release live smoke must depend on verified build"),
        (
            "concurrency:\n      group: trusted-live-smoke\n      cancel-in-progress: false",
            "release and monitoring live smokes must share one non-cancelling concurrency group",
        ),
        (
            "ref: ${{ needs.build.outputs.release-commit }}",
            "release live smoke must check out the verified release commit",
        ),
        (
            'run: test "$(git rev-parse HEAD)" = "$RELEASE_COMMIT"',
            "release live smoke must recheck its exact commit",
        ),
        ('COMETAPI_LIVE_MAX_REQUESTS: "4"', "release live smoke must cap requests at four"),
        (
            'COMETAPI_LIVE_MAX_OUTPUT_TOKENS: "16"',
            "release live smoke must cap output tokens at 16",
        ),
        (
            'COMETAPI_LIVE_REQUEST_TIMEOUT_SECONDS: "30"',
            "release live smoke must cap request timeout at 30 seconds",
        ),
        ('COMETAPI_LIVE_CONCURRENCY: "1"', "release live smoke must use concurrency one"),
        ('COMETAPI_LIVE_STOP_ON_FAILURE: "1"', "release live smoke must stop on failure"),
        ("timeout-minutes: 10", "release live smoke must have a ten-minute job timeout"),
        (
            "COMETAPI_LIVE_MODEL: ${{ vars.COMETAPI_LIVE_MODEL || 'gpt-5.4' }}",
            "release live smoke must default an unset or empty model to gpt-5.4",
        ),
        (
            "COMETAPI_KEY: ${{ secrets.COMETAPI_KEY }}",
            "release live smoke must receive the protected credential only at its test step",
        ),
    ):
        _require(live, needle, message)
    _require_pattern(
        live,
        r"(?m)^    environment: live-smoke$",
        "release live smoke must use its protected environment",
    )
    if "id-token: write" in live:
        raise CheckError("release live smoke must not receive OIDC publication permission")
    live_test = _step(live, "Run the bounded exact-release live suite")
    _require(
        live_test,
        "env:\n          COMETAPI_KEY: ${{ secrets.COMETAPI_KEY }}\n"
        "        run: uv run pytest -m live --maxfail=1 -q",
        "release live credentials must be scoped only to the bounded test step",
    )

    publish = _job(text, "publish")
    for needle, message in (
        (
            "needs:\n      - build\n      - release-live-smoke",
            "publish must require both verified artifacts and successful exact-release live smoke",
        ),
        ("id-token: write", "only the publish job must receive PyPI OIDC permission"),
    ):
        _require(publish, needle, message)
    _require_pattern(
        publish,
        r"(?m)^    environment:\n      name: pypi\n"
        r"      url: https://pypi\.org/project/cometapi/"
        r"\$\{\{ needs\.build\.outputs\.version \}\}/$",
        "publish must use the protected pypi environment and exact package URL",
    )
    _require_pattern(
        publish,
        r"(?m)^    permissions:\n      contents: read\n      id-token: write$",
        "publish must receive only read access plus PyPI OIDC permission",
    )
    if "secrets.COMETAPI_KEY" in publish:
        raise CheckError("publish must not receive the live API credential")
    if "actions/checkout@" in publish:
        raise CheckError("publish must consume the verified bundle without a source checkout")

    registry = _job(text, "verify-registry")
    _require_pattern(
        registry,
        r"(?m)^    permissions:\n      contents: read$",
        "registry verification permissions must be explicitly read-only",
    )
    _require(
        registry,
        "needs:\n      - build\n      - publish",
        "registry verification must require the verified build and completed publication",
    )
    checkout = registry.find("- name: Check out the registry verification source")
    download = registry.find("- name: Download the verified release bundle after checkout")
    digest_guard = registry.find("run: test -f release-bundle/artifact-sha256.txt")
    verification = registry.find("python scripts/check_registry_release.py")
    if min(checkout, download, digest_guard, verification) < 0 or not (
        checkout < download < digest_guard < verification
    ):
        raise CheckError(
            "registry verification must check out source before downloading and retain "
            "digest evidence"
        )
    for needle, message in (
        (
            "ref: ${{ needs.build.outputs.release-commit }}",
            "registry verification must use the verified release commit",
        ),
        (
            "--digest-file release-bundle/artifact-sha256.txt",
            "registry verification must compare against the pre-publication digest manifest",
        ),
    ):
        _require(registry, needle, message)
    verifier_install = _step(registry, "Install the pinned provenance verifier")
    for needle in (
        'PIP_BUILD_CONSTRAINT: ""',
        "PIP_CONFIG_FILE: /dev/null",
        'PIP_CONSTRAINT: ""',
        'PIP_EXTRA_INDEX_URL: ""',
        'PIP_FIND_LINKS: ""',
        'PIP_REQUIREMENT: ""',
        "python -m pip --isolated install",
        "--index-url https://pypi.org/simple/",
        "--no-cache-dir",
        '"pypi-attestations==0.0.29"',
    ):
        _require(
            verifier_install,
            needle,
            "provenance-verifier bootstrap must retain its pinned isolated public-index setup",
        )
    public_install = _step(
        registry, "Install from public PyPI and run the isolated mocked-call smoke"
    )
    for needle in (
        "python scripts/check_clean_install.py",
        '--requirement "cometapi==$RELEASE_VERSION"',
        "--index-url https://pypi.org/simple/",
    ):
        _require(
            public_install,
            needle,
            "registry clean-install smoke must install the exact version from public PyPI",
        )
    if "id-token: write" in registry or "secrets.COMETAPI_KEY" in registry:
        raise CheckError("registry verification must receive neither OIDC nor live credentials")

    if text.count("secrets.COMETAPI_KEY") != 1:
        raise CheckError("COMETAPI_KEY must appear only in the exact-release live-smoke job")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--publish-workflow",
        type=Path,
        default=PROJECT_ROOT / ".github" / "workflows" / "publish.yml",
    )
    parser.add_argument(
        "--live-smoke-workflow",
        type=Path,
        default=PROJECT_ROOT / ".github" / "workflows" / "live-smoke.yml",
    )
    parser.add_argument(
        "--release-please-workflow",
        type=Path,
        default=PROJECT_ROOT / ".github" / "workflows" / "release-please.yml",
    )
    parser.add_argument(
        "--ci-workflow",
        type=Path,
        default=PROJECT_ROOT / ".github" / "workflows" / "ci.yml",
    )
    args = parser.parse_args()
    check_publish_workflow(
        args.publish_workflow.read_text(encoding="utf-8"),
        args.live_smoke_workflow.read_text(encoding="utf-8"),
    )
    check_release_please_workflow(args.release_please_workflow.read_text(encoding="utf-8"))
    check_ci_workflow(args.ci_workflow.read_text(encoding="utf-8"))
    for path in sorted(args.ci_workflow.parent.glob("*.yml")):
        check_action_pins(path.read_text(encoding="utf-8"), path.name)
    print("release workflow semantic checks passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CheckError, OSError) as error:
        raise SystemExit(f"workflow semantic check failed: {error}") from error
