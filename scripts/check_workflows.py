#!/usr/bin/env python3
"""Enforce release-workflow trust invariants that actionlint cannot prove."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import yaml

try:
    from ._checks import CANONICAL_ACTIVE_MODEL, PROJECT_ROOT, CheckError
except ImportError:  # Direct execution from the repository root.
    from _checks import CANONICAL_ACTIVE_MODEL, PROJECT_ROOT, CheckError

RELEASE_PLEASE_BASELINE_SHA = "31b68904141489ca04932edbf305ccf88af09372"
RELEASE_PLEASE_LOCK_JSONPATH = "$.package[?(@.name.value == 'cometapi')].version"
RELEASE_PLEASE_ACTION_SHA = "45996ed1f6d02564a971a2fa1b5860e934307cf7"
RELEASE_PLEASE_ACTION_VERSION = "5.0.0"
RELEASE_PLEASE_ACTION_RUNTIME = "node24"
RELEASE_PLEASE_ACTION = f"googleapis/release-please-action@{RELEASE_PLEASE_ACTION_SHA}"
PYPI_PUBLISH_ACTION_SHA = "ba38be9e461d3875417946c167d0b5f3d385a247"
PYPI_PUBLISH_ACTION_VERSION = "1.14.1"
PYPI_PUBLISH_ACTION_RUNTIME = "node24"
PYPI_PUBLISH_ACTION = f"pypa/gh-action-pypi-publish@{PYPI_PUBLISH_ACTION_SHA}"
RELEASE_PLEASE_BRIDGE_VERSION = "0.1.0-alpha.1"
RELEASE_PLEASE_STABLE_VERSION_PATTERN = re.compile(r"0\.1\.(?:0|[1-9][0-9]*)")
RELEASE_PR_CONDITION = "steps.release.outputs.release_created != 'true'"
RELEASE_PR_RETRY_CONDITION = (
    "steps.release.outputs.release_created != 'true' && steps.release-pr.outcome == 'failure'"
)
RELEASE_VERIFY_CONDITION = "steps.release.outputs.release_created == 'true'"
REVIEWED_RELEASE_PR_FIRST_ATTEMPT: dict[str, object] = {
    "name": "Open or update the release PR",
    "id": "release-pr",
    "if": RELEASE_PR_CONDITION,
    "continue-on-error": "true",
    "uses": RELEASE_PLEASE_ACTION,
    "with": {
        "config-file": "release-please-config.json",
        "manifest-file": ".release-please-manifest.json",
        "skip-github-release": "true",
    },
}
RELEASE_PLEASE_VERIFY_COMMAND = """\
test -n "$EXPECTED_TAG"
test -n "$EXPECTED_SHA"
release=""
for attempt in $(seq 1 12); do
  release=$(gh api "repos/${{ github.repository }}/releases/tags/$EXPECTED_TAG") || true
  if test -n "$release" && test "$(jq -r .immutable <<<"$release")" = "true"; then
    break
  fi
  if test "$attempt" -ge 12; then
    echo "release did not become immutable" >&2
    exit 1
  fi
  sleep 5
done
test "$(jq -r .tag_name <<<"$release")" = "$EXPECTED_TAG"
test "$(jq -r .draft <<<"$release")" = "false"
test "$(jq -r .prerelease <<<"$release")" = "false"
test "$(jq -r .immutable <<<"$release")" = "true"
ref=$(gh api "repos/${{ github.repository }}/git/ref/tags/$EXPECTED_TAG")
tag_type=$(jq -r .object.type <<<"$ref")
tag_sha=$(jq -r .object.sha <<<"$ref")
if test "$tag_type" = "tag"; then
  tag_sha=$(gh api "repos/${{ github.repository }}/git/tags/$tag_sha" --jq .object.sha)
else
  test "$tag_type" = "commit"
fi
test "$tag_sha" = "$EXPECTED_SHA"
{
  echo "release-tag=$EXPECTED_TAG"
  echo "release-sha=$EXPECTED_SHA"
  echo "release-verified=true"
} >> "$GITHUB_OUTPUT"
"""
PUBLISH_JOB_NAMES = {
    "release-please",
    "verify-recovery",
    "select-release",
    "build",
    "release-live-smoke",
    "publish",
    "verify-registry",
}
RELEASE_PLEASE_JOB_CONDITION = (
    "github.run_attempt == 1 && github.event_name == 'push' && "
    "vars.RELEASE_PLEASE_ENABLED == 'true'"
)
RECOVERY_JOB_CONDITION = (
    "github.run_attempt == 1 && github.event_name == 'workflow_dispatch' && "
    "github.ref == format('refs/heads/{0}', github.event.repository.default_branch) && "
    "vars.RELEASE_RECOVERY_TAG == inputs.release-tag && "
    "vars.RELEASE_RECOVERY_SHA == inputs.release-sha"
)
SELECT_RELEASE_CONDITION = (
    "always() && !cancelled() && github.run_attempt == 1 && "
    "( ( github.event_name == 'push' && needs.release-please.result == 'success' && "
    "needs.release-please.outputs.release-created == 'true' && "
    "needs.release-please.outputs.release-verified == 'true' ) || "
    "( github.event_name == 'workflow_dispatch' && "
    "needs.verify-recovery.result == 'success' ) )"
)
BUILD_JOB_CONDITION = (
    "always() && !cancelled() && github.run_attempt == 1 && "
    "needs.select-release.result == 'success'"
)
RELEASE_LIVE_JOB_CONDITION = (
    "always() && !cancelled() && github.run_attempt == 1 && needs.build.result == 'success'"
)
PUBLISH_JOB_CONDITION = (
    "always() && !cancelled() && github.run_attempt == 1 && "
    "needs.build.result == 'success' && "
    "needs.release-live-smoke.result == 'success'"
)
REGISTRY_JOB_CONDITION = (
    "always() && !cancelled() && github.run_attempt == 1 && "
    "needs.build.result == 'success' && needs.publish.result == 'success'"
)
SELECT_RELEASE_COMMAND = """\
case "$EVENT_NAME" in
  push)
    release_sha=$RELEASE_PLEASE_SHA
    release_tag=$RELEASE_PLEASE_TAG
    ;;
  workflow_dispatch)
    release_sha=$RECOVERY_SHA
    release_tag=$RECOVERY_TAG
    ;;
  *)
    exit 1
    ;;
esac
test -n "$release_sha"
test -n "$release_tag"
{
  echo "release-sha=$release_sha"
  echo "release-tag=$release_tag"
} >> "$GITHUB_OUTPUT"
"""


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CheckError(f"{label} must be a mapping")
    raw = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        raise CheckError(f"{label} must use scalar string keys")
    mapping = {cast(str, key): item for key, item in raw.items()}
    if "<<" in mapping:
        raise CheckError(f"{label} must not use YAML merge keys")
    return mapping


def _sequence(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise CheckError(f"{label} must be a sequence")
    return cast(list[object], value)


def _scalar(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise CheckError(f"{label} must be a scalar string")
    return value


def _require_exact_keys(mapping: dict[str, object], expected: set[str], label: str) -> None:
    actual = set(mapping)
    if actual != expected:
        missing = ", ".join(sorted(expected - actual)) or "none"
        unexpected = ", ".join(sorted(actual - expected)) or "none"
        raise CheckError(
            f"{label} keys do not match the reviewed contract "
            f"(missing: {missing}; unexpected: {unexpected})"
        )


def _load_workflow(text: str, source: str) -> dict[str, object]:
    try:
        loaded: object = yaml.load(text, Loader=yaml.BaseLoader)
    except yaml.YAMLError as error:
        raise CheckError(f"{source} is not valid YAML: {error}") from error
    return _mapping(loaded, source)


def _workflow_job(workflow: dict[str, object], name: str, source: str) -> dict[str, object]:
    jobs = _mapping(workflow.get("jobs"), f"{source} jobs")
    if name not in jobs:
        raise CheckError(f"{source} has no {name!r} job")
    return _mapping(jobs[name], f"{source} {name!r} job")


def _workflow_steps(job: dict[str, object], label: str) -> list[dict[str, object]]:
    return [
        _mapping(item, f"{label} step {index}")
        for index, item in enumerate(_sequence(job.get("steps"), f"{label} steps"))
    ]


def _walk_mappings(value: object, label: str) -> Iterator[dict[str, object]]:
    if isinstance(value, dict):
        mapping = _mapping(cast(dict[object, object], value), label)
        yield mapping
        for key, child in mapping.items():
            yield from _walk_mappings(child, f"{label}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(cast(list[object], value)):
            yield from _walk_mappings(child, f"{label}[{index}]")


def _walk_scalars(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in cast(dict[object, object], value).values():
            yield from _walk_scalars(child)
    elif isinstance(value, list):
        for child in cast(list[object], value):
            yield from _walk_scalars(child)


def _secret_references(value: object) -> list[str]:
    pattern = re.compile(r"\$\{\{[^}]*\bsecrets\b[^}]*\}\}", flags=re.IGNORECASE)
    return [scalar for scalar in _walk_scalars(value) if pattern.search(scalar)]


def _require_unconditional(mapping: dict[str, object], label: str) -> None:
    if "if" in mapping:
        raise CheckError(f"{label} must not be conditional")
    if "continue-on-error" in mapping:
        raise CheckError(f"{label} must not allow failure")
    if "defaults" in mapping:
        raise CheckError(f"{label} must not override command defaults")
    if "shell" in mapping:
        raise CheckError(f"{label} must not override the command shell")


def _require_blocking_job(job: dict[str, object], label: str) -> None:
    _require_unconditional(job, label)
    if "permissions" in job:
        raise CheckError(f"{label} must not override credential-free workflow permissions")
    if "env" in job:
        raise CheckError(f"{label} must not override the reviewed CI environment")
    for index, step in enumerate(_workflow_steps(job, label)):
        _require_unconditional(step, f"{label} step {index}")
        if "env" in step:
            raise CheckError(f"{label} step {index} must not override the CI environment")


def _run_step(job: dict[str, object], command: str, label: str) -> tuple[int, dict[str, object]]:
    matches = [
        (index, step)
        for index, step in enumerate(_workflow_steps(job, label))
        if step.get("run") == command
    ]
    if len(matches) != 1:
        raise CheckError(f"{label} must contain exactly one active run step: {command}")
    index, step = matches[0]
    _require_unconditional(step, f"{label} run step {command!r}")
    return index, step


def _action_step(job: dict[str, object], action: str, label: str) -> tuple[int, dict[str, object]]:
    matches: list[tuple[int, dict[str, object]]] = []
    for index, step in enumerate(_workflow_steps(job, label)):
        uses = step.get("uses")
        if isinstance(uses, str) and uses.rpartition("@")[0] == action:
            matches.append((index, step))
    if len(matches) != 1:
        raise CheckError(f"{label} must contain exactly one {action} step")
    index, step = matches[0]
    _require_unconditional(step, f"{label} {action} step")
    return index, step


def _named_step(job: dict[str, object], name: str, label: str) -> tuple[int, dict[str, object]]:
    matches = [
        (index, step)
        for index, step in enumerate(_workflow_steps(job, label))
        if step.get("name") == name
    ]
    if len(matches) != 1:
        raise CheckError(f"{label} must contain exactly one {name!r} step")
    index, step = matches[0]
    _require_unconditional(step, f"{label} {name!r} step")
    return index, step


def _named_run_step(
    job: dict[str, object], name: str, command: str, label: str
) -> tuple[int, dict[str, object]]:
    index, step = _named_step(job, name, label)
    if step.get("run") != command or "uses" in step:
        raise CheckError(f"{label} {name!r} step must run exactly: {command}")
    return index, step


def _named_action_step(
    job: dict[str, object], name: str, action: str, label: str
) -> tuple[int, dict[str, object]]:
    index, step = _action_step(job, action, label)
    if step.get("name") != name or "run" in step:
        raise CheckError(f"{label} must use {action} in its {name!r} step")
    return index, step


def _require_step_names(job: dict[str, object], expected: list[str], label: str) -> None:
    names = [step.get("name") for step in _workflow_steps(job, label)]
    if names != expected:
        raise CheckError(f"{label} steps must match the reviewed sequence")


def _require_needs(job: dict[str, object], expected: list[str], label: str) -> None:
    value = job.get("needs")
    if isinstance(value, str):
        actual = [value]
    else:
        actual = [
            _scalar(item, f"{label} dependency")
            for item in _sequence(value, f"{label} dependencies")
        ]
    if actual != expected:
        raise CheckError(f"{label} must depend on {', '.join(expected)}")


def _require_permissions(mapping: dict[str, object], expected: dict[str, str], label: str) -> None:
    permissions = _mapping(mapping.get("permissions"), f"{label} permissions")
    if permissions != expected:
        raise CheckError(f"{label} permissions do not match the reviewed least-privilege map")


def _require_options(step: dict[str, object], expected: dict[str, str], label: str) -> None:
    options = _mapping(step.get("with"), f"{label} options")
    if options != expected:
        raise CheckError(f"{label} options do not match the reviewed contract")


def _require_step_environments(
    job: dict[str, object], expected: dict[str, dict[str, str]], label: str
) -> None:
    for index, step in enumerate(_workflow_steps(job, label)):
        name = _scalar(step.get("name"), f"{label} step {index} name")
        if name in expected:
            environment = _mapping(step.get("env"), f"{label} {name!r} environment")
            if environment != expected[name]:
                raise CheckError(f"{label} {name!r} environment does not match the contract")
        elif "env" in step:
            raise CheckError(f"{label} {name!r} step must not override the environment")


def _require_step_working_directories(
    job: dict[str, object], expected: dict[str, str], label: str
) -> None:
    matched: set[str] = set()
    for index, step in enumerate(_workflow_steps(job, label)):
        name = _scalar(step.get("name"), f"{label} step {index} name")
        if name in expected:
            if step.get("working-directory") != expected[name]:
                raise CheckError(f"{label} {name!r} step must use its reviewed working directory")
            matched.add(name)
        elif "working-directory" in step:
            raise CheckError(f"{label} {name!r} step must run from the checked-out repository root")
    if matched != set(expected):
        raise CheckError(f"{label} reviewed working-directory steps are missing")


def _action_references(workflow: dict[str, object], source: str) -> Iterator[tuple[str, str]]:
    jobs = _mapping(workflow.get("jobs"), f"{source} jobs")
    for job_name, value in jobs.items():
        job = _mapping(value, f"{source} {job_name!r} job")
        if "uses" in job:
            yield (
                f"{source} {job_name!r} job",
                _scalar(job["uses"], f"{source} {job_name!r} job uses"),
            )
        if "steps" not in job:
            continue
        for index, step in enumerate(_workflow_steps(job, f"{source} {job_name!r} job")):
            if "uses" in step:
                yield (
                    f"{source} {job_name!r} step {index}",
                    _scalar(step["uses"], f"{source} {job_name!r} step {index} uses"),
                )


def check_action_pins(text: str, source: str) -> None:
    workflow = _load_workflow(text, source)
    for label, value in _action_references(workflow, source):
        if value.startswith("./"):
            continue
        if value.startswith("docker://"):
            raise CheckError(f"{label}: Docker action references are not permitted")
        action, separator, reference = value.rpartition("@")
        if not separator or not action:
            raise CheckError(f"{label}: external action reference {value!r} has no ref")
        if re.fullmatch(r"[0-9a-f]{40}", reference) is None:
            raise CheckError(f"{label}: {action} must be pinned to a full commit SHA")


def check_ci_workflow(text: str) -> None:
    """Require credential-free CI to cover every private-validation evidence layer."""
    workflow = _load_workflow(text, "CI workflow")
    _require_permissions(workflow, {"contents": "read"}, "credential-free CI")
    if "defaults" in workflow:
        raise CheckError("credential-free CI must not override command defaults")
    if _mapping(workflow.get("env"), "CI workflow environment") != {"UV_VERSION": "0.11.8"}:
        raise CheckError("credential-free CI must retain only its pinned uv frontend version")
    triggers = _mapping(workflow.get("on"), "CI workflow triggers")
    if set(triggers) != {"pull_request", "push", "schedule"}:
        raise CheckError("CI triggers must equal pull requests, main pushes, and weekly schedule")
    if triggers["pull_request"] != "":
        raise CheckError("CI pull-request validation must not use activity or path filters")
    push = _mapping(triggers["push"], "CI push trigger")
    if set(push) != {"branches"}:
        raise CheckError("CI main-push validation must not use path, tag, or activity filters")
    branches = [
        _scalar(item, "CI push branch")
        for item in _sequence(push.get("branches"), "CI push branches")
    ]
    if branches != ["main"]:
        raise CheckError("CI must run only for default-branch pushes")
    schedule = _sequence(triggers["schedule"], "CI schedule trigger")
    if schedule != [{"cron": "23 4 * * 1"}]:
        raise CheckError("CI must retain its reviewed weekly schedule")
    concurrency = _mapping(workflow.get("concurrency"), "CI workflow concurrency")
    if concurrency != {
        "group": "ci-${{ github.workflow }}-${{ github.ref }}",
        "cancel-in-progress": "true",
    }:
        raise CheckError("CI must retain reviewed per-ref cancellation")
    _require_exact_keys(
        workflow,
        {"name", "on", "permissions", "concurrency", "env", "jobs"},
        "CI workflow",
    )
    if _secret_references(workflow):
        raise CheckError("credential-free CI must not reference repository secrets")

    jobs = _mapping(workflow.get("jobs"), "CI workflow jobs")
    expected_jobs = {
        "quality",
        "locked-runtime",
        "minimum-openai",
        "package",
        "standalone",
    }
    if set(jobs) != expected_jobs:
        raise CheckError("CI jobs must match the reviewed validation chain")
    quality = _workflow_job(workflow, "quality", "CI workflow")
    locked_runtime = _workflow_job(workflow, "locked-runtime", "CI workflow")
    minimum_openai = _workflow_job(workflow, "minimum-openai", "CI workflow")
    package = _workflow_job(workflow, "package", "CI workflow")
    standalone = _workflow_job(workflow, "standalone", "CI workflow")
    expected_job_keys = {
        "quality": {"name", "runs-on", "timeout-minutes", "steps"},
        "locked-runtime": {"name", "runs-on", "timeout-minutes", "strategy", "steps"},
        "minimum-openai": {"name", "runs-on", "timeout-minutes", "steps"},
        "package": {"name", "needs", "runs-on", "timeout-minutes", "steps"},
        "standalone": {"name", "needs", "runs-on", "timeout-minutes", "steps"},
    }
    for name, job in (
        ("quality", quality),
        ("locked-runtime", locked_runtime),
        ("minimum-openai", minimum_openai),
        ("package", package),
        ("standalone", standalone),
    ):
        _require_blocking_job(job, f"CI {name!r} job")
    for name, value in jobs.items():
        job = _mapping(value, f"CI {name!r} job")
        _require_exact_keys(job, expected_job_keys[name], f"CI {name!r} job")

    _require_needs(
        package,
        ["quality", "locked-runtime", "minimum-openai"],
        "CI package job",
    )
    _require_needs(standalone, ["package"], "CI standalone job")

    required_commands = {
        "quality": (
            "uv lock --check",
            "uv sync --locked",
            "uv run ruff check src tests scripts",
            "uv run ruff format --check src tests scripts",
            "uv run pyright",
            'uv run pytest -m "not live"',
            'uv pip install --python .venv/bin/python --upgrade "openai>=2.45.0,<3.0.0"',
            'uv run --no-sync pytest -m "not live"',
            "uv run python scripts/check_version.py --require-changelog "
            "--require-public-preview-docs",
            "uv run python scripts/check_secrets.py",
            "uv run python scripts/run_actionlint.py",
            "uv run python scripts/check_workflows.py",
        ),
        "locked-runtime": ("uv sync --locked", 'uv run pytest -m "not live"'),
        "minimum-openai": (
            "uv sync --locked",
            'uv pip install --python .venv/bin/python "openai==2.45.0"',
            'uv run --no-sync pytest -m "not live"',
        ),
        "package": (
            "uv sync --locked",
            "uv build",
            "uv run twine check dist/*",
            "uv run python scripts/check_artifacts.py dist/*",
            "uv run python scripts/check_clean_install.py dist/*",
            "sha256sum dist/* > artifact-sha256.txt",
        ),
        "standalone": (
            "python scripts/check_repository_independence.py",
            "sha256sum --check artifact-sha256.txt",
        ),
    }
    required_jobs = {
        "quality": quality,
        "locked-runtime": locked_runtime,
        "minimum-openai": minimum_openai,
        "package": package,
        "standalone": standalone,
    }
    expected_step_names = {
        "quality": [
            "Check out the candidate",
            "Set up Python",
            "Install the pinned uv frontend",
            "Check lock consistency",
            "Reproduce the locked environment",
            "Lint",
            "Check formatting",
            "Type check",
            "Run offline unit and contract tests",
            "Select latest OpenAI within the supported major",
            "Run latest-within-major tests without resyncing the lock",
            "Check version agreement and durable public content",
            "Scan for credentials and scope mistakes",
            "Validate workflow syntax with checksum-pinned actionlint",
            "Verify release-workflow trust semantics",
        ],
        "locked-runtime": [
            "Check out the candidate",
            "Set up Python",
            "Install the pinned uv frontend",
            "Reproduce the locked environment",
            "Run offline tests",
        ],
        "minimum-openai": [
            "Check out the candidate",
            "Set up Python",
            "Install the pinned uv frontend",
            "Create the development environment",
            "Select the minimum supported OpenAI dependency",
            "Run offline tests without resyncing the lock",
        ],
        "package": [
            "Check out the candidate",
            "Set up Python",
            "Install the pinned uv frontend",
            "Reproduce the locked environment",
            "Build wheel and source distribution",
            "Check package metadata rendering",
            "Inspect artifact identity and shape",
            "Install and smoke-test each exact artifact",
            "Record immutable artifact digests",
            "Retain verified artifacts",
        ],
        "standalone": [
            "Check out the candidate",
            "Set up Python",
            "Install the pinned uv frontend",
            "Verify from a copied standalone repository",
            "Download the verified package artifacts",
            "Recheck retained artifact digests",
        ],
    }
    expected_timeouts = {
        "quality": "20",
        "locked-runtime": "20",
        "minimum-openai": "20",
        "package": "25",
        "standalone": "35",
    }
    expected_python = {
        "quality": "3.14",
        "locked-runtime": "${{ matrix.python-version }}",
        "minimum-openai": "3.10",
        "package": "3.14",
        "standalone": "3.14",
    }
    for name, job in required_jobs.items():
        if job.get("runs-on") != "ubuntu-latest":
            raise CheckError(f"CI {name} job must use the reviewed GitHub-hosted runner")
        if job.get("timeout-minutes") != expected_timeouts[name]:
            raise CheckError(f"CI {name} job must retain its reviewed timeout")
        _, setup_step = _named_action_step(
            job, "Set up Python", "actions/setup-python", f"CI {name} job"
        )
        _, checkout_step = _named_action_step(
            job, "Check out the candidate", "actions/checkout", f"CI {name} job"
        )
        if "with" in checkout_step:
            raise CheckError(f"CI {name} checkout must use the triggering candidate defaults")
        _require_options(
            setup_step,
            {"python-version": expected_python[name]},
            f"CI {name} Python setup",
        )
    for name, commands in required_commands.items():
        for command in commands:
            _run_step(required_jobs[name], command, f"CI {name} job")

    strategy = _mapping(locked_runtime.get("strategy"), "CI locked-runtime strategy")
    if set(strategy) != {"fail-fast", "matrix"} or strategy["fail-fast"] != "false":
        raise CheckError("CI runtime matrix must retain fail-fast: false")
    matrix = _mapping(strategy.get("matrix"), "CI locked-runtime matrix")
    if set(matrix) != {"python-version"}:
        raise CheckError("CI runtime matrix must vary only the supported Python version")
    python_versions = [
        _scalar(item, "CI locked-runtime Python version")
        for item in _sequence(matrix.get("python-version"), "CI locked-runtime Python versions")
    ]
    if python_versions != ["3.10", "3.11", "3.12", "3.13", "3.14"]:
        raise CheckError("CI must block on every supported Python runtime")
    package_digest, _ = _run_step(
        package, "sha256sum dist/* > artifact-sha256.txt", "CI package job"
    )
    package_upload, upload_step = _named_action_step(
        package, "Retain verified artifacts", "actions/upload-artifact", "CI package job"
    )
    _require_options(
        upload_step,
        {
            "name": "python-distributions",
            "path": "dist/*\nartifact-sha256.txt\n",
            "if-no-files-found": "error",
            "retention-days": "7",
        },
        "CI package artifact upload",
    )
    if package_digest >= package_upload:
        raise CheckError("CI package job must digest artifacts before retaining them")
    copied_checkout, _ = _run_step(
        standalone,
        "python scripts/check_repository_independence.py",
        "CI standalone job",
    )
    artifact_download, download_step = _action_step(
        standalone, "actions/download-artifact", "CI standalone job"
    )
    _require_options(
        download_step,
        {"name": "python-distributions", "path": "verified-artifacts"},
        "CI artifact download",
    )
    digest_check, digest_step = _run_step(
        standalone,
        "sha256sum --check artifact-sha256.txt",
        "CI standalone job",
    )
    if digest_step.get("working-directory") != "verified-artifacts":
        raise CheckError("CI must recheck retained artifact digests after download")
    if not copied_checkout < artifact_download < digest_check:
        raise CheckError(
            "CI must finish copied-checkout verification before downloading and "
            "rechecking retained artifacts"
        )
    for name, job in required_jobs.items():
        _require_step_names(job, expected_step_names[name], f"CI {name} job")
        _require_step_working_directories(
            job,
            (
                {"Recheck retained artifact digests": "verified-artifacts"}
                if name == "standalone"
                else {}
            ),
            f"CI {name} job",
        )


def _check_publish_envelope(workflow: dict[str, object], source: str) -> None:
    """Require one top-level workflow identity for release creation and publication."""
    _require_exact_keys(
        workflow,
        {"name", "on", "permissions", "concurrency", "env", "jobs"},
        source,
    )
    if workflow.get("name") != "Publish immutable release":
        raise CheckError("publication must retain its canonical top-level workflow identity")
    _require_permissions(workflow, {"contents": "read"}, source)
    if "defaults" in workflow:
        raise CheckError("publication workflow must not override command defaults")
    triggers = _mapping(workflow.get("on"), f"{source} triggers")
    if set(triggers) != {"push", "workflow_dispatch"}:
        raise CheckError("publication must run only for main pushes or explicit recovery dispatch")
    push = _mapping(triggers["push"], f"{source} push trigger")
    if set(push) != {"branches"}:
        raise CheckError("publication push trigger must not use path or tag filters")
    branches = [
        _scalar(item, "publication push branch")
        for item in _sequence(push.get("branches"), "publication push branches")
    ]
    if branches != ["main"]:
        raise CheckError("publication push trigger must use only main")
    dispatch = _mapping(triggers["workflow_dispatch"], f"{source} recovery dispatch")
    _require_exact_keys(dispatch, {"inputs"}, "publication recovery dispatch")
    inputs = _mapping(dispatch["inputs"], "publication recovery inputs")
    expected_descriptions = {
        "release-tag": "Exact immutable GitHub release tag",
        "release-sha": "Exact commit resolved by the release tag",
    }
    if set(inputs) != set(expected_descriptions):
        raise CheckError("publication recovery must accept only the exact release identity")
    for name, description in expected_descriptions.items():
        if _mapping(inputs[name], f"publication recovery input {name}") != {
            "description": description,
            "required": "true",
            "type": "string",
        }:
            raise CheckError(f"publication recovery input {name} must be an exact required string")
    concurrency = _mapping(workflow.get("concurrency"), f"{source} concurrency")
    if concurrency != {"group": "pypi-publish", "cancel-in-progress": "false"}:
        raise CheckError("publication must serialize the complete release workflow")
    if _mapping(workflow.get("env"), f"{source} environment") != {"UV_VERSION": "0.11.8"}:
        raise CheckError("publication must retain its pinned uv frontend version")
    jobs = _mapping(workflow.get("jobs"), f"{source} jobs")
    if set(jobs) != PUBLISH_JOB_NAMES:
        raise CheckError("publication jobs must match the reviewed top-level release chain")


def check_release_please_workflow(text: str) -> None:
    """Require Release Please to remain explicitly disabled by default."""
    workflow = _load_workflow(text, "Release Please workflow")
    _check_publish_envelope(workflow, "Release Please workflow")
    release_job = _workflow_job(workflow, "release-please", "Release Please workflow")
    _require_exact_keys(
        release_job,
        {"name", "if", "runs-on", "timeout-minutes", "outputs", "permissions", "steps"},
        "Release Please job",
    )
    release_condition = " ".join(_scalar(release_job.get("if"), "Release Please condition").split())
    if release_condition != RELEASE_PLEASE_JOB_CONDITION:
        raise CheckError(
            "Release Please must require a first-attempt main push and RELEASE_PLEASE_ENABLED=true"
        )
    if release_job.get("runs-on") != "ubuntu-latest":
        raise CheckError("Release Please must use the reviewed GitHub-hosted runner")
    if release_job.get("timeout-minutes") != "15":
        raise CheckError("Release Please must retain its fifteen-minute timeout")
    if "continue-on-error" in release_job:
        raise CheckError("Release Please must not allow its job to fail")
    if "env" in release_job:
        raise CheckError("Release Please job must not override the action environment")
    _require_permissions(
        release_job,
        {"contents": "write", "pull-requests": "write"},
        "Release Please job",
    )
    if "defaults" in workflow or "defaults" in release_job:
        raise CheckError("Release Please must not override command defaults")
    _require_step_names(
        release_job,
        [
            "Create the approved immutable release",
            "Open or update the release PR",
            "Retry release PR maintenance once",
            "Verify the immutable release created by Release Please",
        ],
        "Release Please job",
    )
    outputs = _mapping(release_job["outputs"], "Release Please job outputs")
    if outputs != {
        "release-created": "${{ steps.release.outputs.release_created }}",
        "release-sha": "${{ steps.verify-release.outputs.release-sha }}",
        "release-tag": "${{ steps.verify-release.outputs.release-tag }}",
        "release-verified": "${{ steps.verify-release.outputs.release-verified }}",
    }:
        raise CheckError("Release Please must expose only the verified release identity")
    _require_step_environments(
        release_job,
        {
            "Verify the immutable release created by Release Please": {
                "EXPECTED_SHA": "${{ steps.release.outputs.sha }}",
                "EXPECTED_TAG": "${{ steps.release.outputs.tag_name }}",
                "GH_TOKEN": "${{ github.token }}",
            }
        },
        "Release Please job",
    )
    _require_step_working_directories(release_job, {}, "Release Please job")
    release_step, release_pr_step, retry_release_pr_step, verify_step = _workflow_steps(
        release_job, "Release Please job"
    )
    common_options = {
        "config-file": "release-please-config.json",
        "manifest-file": ".release-please-manifest.json",
    }
    reviewed_steps = [
        (
            release_step,
            "release",
            common_options | {"skip-github-pull-request": "true"},
            {"name", "id", "uses", "with"},
        ),
        (
            release_pr_step,
            "release-pr",
            common_options | {"skip-github-release": "true"},
            {"name", "id", "if", "continue-on-error", "uses", "with"},
        ),
        (
            retry_release_pr_step,
            "retry-release-pr",
            common_options | {"skip-github-release": "true"},
            {"name", "id", "if", "uses", "with"},
        ),
    ]
    for step, expected_id, options, keys in reviewed_steps:
        _require_exact_keys(step, keys, f"Release Please {expected_id} step")
        if step.get("id") != expected_id:
            raise CheckError(f"Release Please {expected_id} step must retain its reviewed id")
        if step.get("uses") != RELEASE_PLEASE_ACTION:
            raise CheckError(
                "Release Please must retain the release-please "
                f"{RELEASE_PLEASE_ACTION_VERSION} ({RELEASE_PLEASE_ACTION_RUNTIME}) action pin"
            )
        _require_options(step, options, f"Release Please {expected_id} action")
    if release_pr_step.get("if") != RELEASE_PR_CONDITION:
        raise CheckError("Release Please must run PR maintenance only when no release was created")
    if release_pr_step.get("continue-on-error") != "true":
        raise CheckError("Release Please must permit exactly one bounded PR-maintenance retry")
    retry_condition = " ".join(
        _scalar(retry_release_pr_step.get("if"), "Release Please PR retry condition").split()
    )
    if retry_condition != RELEASE_PR_RETRY_CONDITION:
        raise CheckError("Release Please PR retry must require the first PR-only attempt to fail")
    _require_exact_keys(
        verify_step,
        {"name", "id", "if", "env", "run"},
        "Release Please immutable-release verification",
    )
    if verify_step.get("run") != RELEASE_PLEASE_VERIFY_COMMAND or "uses" in verify_step:
        raise CheckError("Release Please immutable-release verification is not exact")
    if (
        verify_step.get("id") != "verify-release"
        or verify_step.get("if") != RELEASE_VERIFY_CONDITION
    ):
        raise CheckError("Release Please must verify only the release it just created")
    if _secret_references(release_job):
        raise CheckError("Release Please must not depend on repository credentials")


def check_release_recovery_workflow(text: str) -> None:
    """Require a default-branch-only, explicitly enabled immutable release recovery."""
    workflow = _load_workflow(text, "release recovery workflow")
    _check_publish_envelope(workflow, "release recovery workflow")
    verify = _workflow_job(workflow, "verify-recovery", "release recovery workflow")
    _require_exact_keys(
        verify,
        {
            "name",
            "if",
            "runs-on",
            "timeout-minutes",
            "outputs",
            "permissions",
            "steps",
        },
        "release recovery verification job",
    )
    if " ".join(_scalar(verify["if"], "release recovery condition").split()) != (
        RECOVERY_JOB_CONDITION
    ):
        raise CheckError(
            "release recovery must require an explicit first-attempt dispatch from the "
            "protected default branch and the exact authorized release tag and commit"
        )
    if verify["runs-on"] != "ubuntu-latest" or verify["timeout-minutes"] != "5":
        raise CheckError("release recovery verification must use the reviewed bounded runner")
    _require_permissions(verify, {"contents": "read"}, "release recovery verification job")
    outputs = _mapping(verify["outputs"], "release recovery outputs")
    if outputs != {
        "release-sha": "${{ steps.verify-release.outputs.release-sha }}",
        "release-tag": "${{ steps.verify-release.outputs.release-tag }}",
    }:
        raise CheckError("release recovery must expose only the verified release identity")
    _require_step_names(
        verify,
        ["Verify the immutable release selected for recovery"],
        "release recovery verification job",
    )
    _require_step_environments(
        verify,
        {
            "Verify the immutable release selected for recovery": {
                "EXPECTED_SHA": "${{ inputs.release-sha }}",
                "EXPECTED_TAG": "${{ inputs.release-tag }}",
                "GH_TOKEN": "${{ github.token }}",
            }
        },
        "release recovery verification job",
    )
    _require_step_working_directories(verify, {}, "release recovery verification job")
    _, verify_step = _named_run_step(
        verify,
        "Verify the immutable release selected for recovery",
        RELEASE_PLEASE_VERIFY_COMMAND,
        "release recovery verification job",
    )
    if verify_step.get("id") != "verify-release":
        raise CheckError("release recovery verification must expose its exact outputs")

    selector = _workflow_job(workflow, "select-release", "release recovery workflow")
    _require_exact_keys(
        selector,
        {"name", "needs", "if", "runs-on", "timeout-minutes", "outputs", "permissions", "steps"},
        "release identity selector",
    )
    _require_needs(
        selector,
        ["release-please", "verify-recovery"],
        "release identity selector",
    )
    selector_condition = " ".join(
        _scalar(selector["if"], "release identity selector condition").split()
    )
    if selector_condition != SELECT_RELEASE_CONDITION:
        raise CheckError(
            "release identity selector must accept only one successfully verified path"
        )
    if selector["runs-on"] != "ubuntu-latest" or selector["timeout-minutes"] != "5":
        raise CheckError("release identity selector must use the reviewed bounded runner")
    _require_permissions(selector, {"contents": "read"}, "release identity selector")
    if _mapping(selector["outputs"], "release identity selector outputs") != {
        "release-sha": "${{ steps.select.outputs.release-sha }}",
        "release-tag": "${{ steps.select.outputs.release-tag }}",
    }:
        raise CheckError("release identity selector must expose only the selected tag and commit")
    _require_step_names(
        selector,
        ["Select the independently verified release identity"],
        "release identity selector",
    )
    _require_step_environments(
        selector,
        {
            "Select the independently verified release identity": {
                "EVENT_NAME": "${{ github.event_name }}",
                "RECOVERY_SHA": "${{ needs.verify-recovery.outputs.release-sha }}",
                "RECOVERY_TAG": "${{ needs.verify-recovery.outputs.release-tag }}",
                "RELEASE_PLEASE_SHA": "${{ needs.release-please.outputs.release-sha }}",
                "RELEASE_PLEASE_TAG": "${{ needs.release-please.outputs.release-tag }}",
            }
        },
        "release identity selector",
    )
    _require_step_working_directories(selector, {}, "release identity selector")
    _, selector_step = _named_run_step(
        selector,
        "Select the independently verified release identity",
        SELECT_RELEASE_COMMAND,
        "release identity selector",
    )
    if selector_step.get("id") != "select":
        raise CheckError("release identity selector must expose its exact selected outputs")
    if _secret_references(verify) or _secret_references(selector):
        raise CheckError("release identity verification must not reference credentials")


def check_release_please_config(text: str, manifest_text: str) -> None:
    """Require either the reviewed bridge or a stable 0.1.x cleanup state."""
    try:
        value = cast(object, json.loads(text))
    except json.JSONDecodeError as error:
        raise CheckError(f"Release Please config is not valid JSON: {error}") from error
    config = _mapping(value, "Release Please config")
    try:
        manifest_value = cast(object, json.loads(manifest_text))
    except json.JSONDecodeError as error:
        raise CheckError(f"Release Please manifest is not valid JSON: {error}") from error
    manifest = _mapping(manifest_value, "Release Please manifest")
    _require_exact_keys(manifest, {"."}, "Release Please manifest")
    version = manifest["."]
    stable_version = (
        isinstance(version, str)
        and RELEASE_PLEASE_STABLE_VERSION_PATTERN.fullmatch(version) is not None
    )
    if version != RELEASE_PLEASE_BRIDGE_VERSION and not stable_version:
        raise CheckError(
            "Release Please manifest must be the reviewed bridge or a stable 0.1.x version"
        )

    common_keys = {
        "$schema",
        "release-type",
        "include-component-in-tag",
        "include-v-in-tag",
        "packages",
    }
    bridge_keys = {"last-release-sha", "prerelease", "versioning"}
    bridge_enabled = set(config) == common_keys | bridge_keys
    if bridge_enabled:
        _require_exact_keys(
            config,
            common_keys | bridge_keys,
            "Release Please bridge config",
        )
        if config["last-release-sha"] != RELEASE_PLEASE_BASELINE_SHA:
            raise CheckError("Release Please must stop history at the recovery alpha commit")
        if config["versioning"] != "prerelease" or config["prerelease"] is not False:
            raise CheckError(
                "Release Please must make the reviewed prerelease-to-stable transition"
            )
        if version != RELEASE_PLEASE_BRIDGE_VERSION:
            raise CheckError(
                "Release Please stable release PR must remove the one-time bridge before merge"
            )
    else:
        _require_exact_keys(config, common_keys, "Release Please stable config")
        if not stable_version:
            raise CheckError("Release Please may remove the one-time bridge only after stable")
    if config["release-type"] != "python":
        raise CheckError("Release Please must retain its Python release type")
    if config["$schema"] != (
        "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json"
    ):
        raise CheckError("Release Please must retain the reviewed upstream schema")
    if config["include-component-in-tag"] is not False or config["include-v-in-tag"] is not True:
        raise CheckError("Release Please tag spelling does not match the reviewed contract")
    packages = _mapping(config["packages"], "Release Please packages")
    _require_exact_keys(packages, {"."}, "Release Please packages")
    package = _mapping(packages["."], "Release Please root package")
    _require_exact_keys(
        package,
        {"package-name", "extra-files"},
        "Release Please root package",
    )
    if package["package-name"] != "cometapi":
        raise CheckError("Release Please must update only the cometapi package")
    extra_files = _sequence(package["extra-files"], "Release Please extra files")
    if len(extra_files) != 1:
        raise CheckError("Release Please must contain exactly one reviewed extra-file updater")
    updater = _mapping(extra_files[0], "Release Please uv.lock updater")
    if updater != {
        "type": "toml",
        "path": "uv.lock",
        "jsonpath": RELEASE_PLEASE_LOCK_JSONPATH,
    }:
        raise CheckError("Release Please must update the editable cometapi version in uv.lock")


def check_publish_workflow(text: str, live_smoke_text: str) -> None:
    """Validate fail-closed publication, live, permission, and evidence ordering."""
    workflow = _load_workflow(text, "publish workflow")
    live_workflow = _load_workflow(live_smoke_text, "live-smoke workflow")
    _check_publish_envelope(workflow, "publish workflow")
    check_release_please_workflow(text)
    check_release_recovery_workflow(text)
    _require_exact_keys(
        live_workflow,
        {"name", "on", "permissions", "concurrency", "env", "jobs"},
        "live-smoke workflow",
    )

    live_triggers = _mapping(live_workflow.get("on"), "live-smoke triggers")
    if set(live_triggers) != {"schedule", "workflow_dispatch"}:
        raise CheckError("monitoring live smoke must run only on schedule or manual dispatch")
    live_dispatch = _mapping(
        live_triggers["workflow_dispatch"], "monitoring live smoke manual dispatch"
    )
    _require_exact_keys(
        live_dispatch,
        {"inputs"},
        "monitoring live smoke manual dispatch",
    )
    live_inputs = _mapping(live_dispatch.get("inputs"), "monitoring live smoke inputs")
    _require_exact_keys(
        live_inputs,
        {"max_output_tokens"},
        "monitoring live smoke inputs",
    )
    max_output_tokens = _mapping(
        live_inputs.get("max_output_tokens"),
        "monitoring live smoke max_output_tokens input",
    )
    if max_output_tokens != {
        "description": "Maximum output tokens for each bounded live request",
        "required": "true",
        "default": "64",
        "type": "choice",
        "options": ["64", "128", "256"],
    }:
        raise CheckError(
            "monitoring live smoke max_output_tokens must be the reviewed 64/128/256 "
            "choice with a 64-token default"
        )
    if _sequence(live_triggers["schedule"], "live-smoke schedule") != [{"cron": "17 3 * * *"}]:
        raise CheckError("monitoring live smoke must retain its reviewed daily schedule")
    _require_permissions(live_workflow, {"contents": "read"}, "live-smoke workflow")
    if "defaults" in live_workflow:
        raise CheckError("monitoring live smoke must not override command defaults")
    live_concurrency = _mapping(live_workflow.get("concurrency"), "live-smoke workflow concurrency")
    if live_concurrency != {"group": "trusted-live-smoke", "cancel-in-progress": "false"}:
        raise CheckError(
            "release and monitoring live smokes must share one non-cancelling concurrency group"
        )
    live_environment = _mapping(live_workflow.get("env"), "live-smoke workflow environment")
    if live_environment != {
        "UV_VERSION": "0.11.8",
        "COMETAPI_LIVE_MAX_REQUESTS": "4",
        "COMETAPI_LIVE_MAX_OUTPUT_TOKENS": "${{ inputs.max_output_tokens || '64' }}",
        "COMETAPI_LIVE_MODEL": CANONICAL_ACTIVE_MODEL,
        "COMETAPI_LIVE_REQUEST_TIMEOUT_SECONDS": "30",
        "COMETAPI_LIVE_CONCURRENCY": "1",
        "COMETAPI_LIVE_RUN": "1",
        "COMETAPI_LIVE_STOP_ON_FAILURE": "1",
    }:
        raise CheckError("monitoring live smoke must retain its bounded execution budget")

    conditions: list[str] = []
    for mapping in _walk_mappings(workflow, "publish workflow"):
        if "if" in mapping:
            conditions.append(" ".join(_scalar(mapping["if"], "release condition").split()))
        if "continue-on-error" in mapping and mapping != REVIEWED_RELEASE_PR_FIRST_ATTEMPT:
            raise CheckError("release gates must not be allowed to continue on error")
        if "defaults" in mapping or "shell" in mapping:
            raise CheckError("release gates must not override command execution")
    expected_conditions = [
        RELEASE_PLEASE_JOB_CONDITION,
        RELEASE_PR_CONDITION,
        RELEASE_PR_RETRY_CONDITION,
        RELEASE_VERIFY_CONDITION,
        RECOVERY_JOB_CONDITION,
        SELECT_RELEASE_CONDITION,
        BUILD_JOB_CONDITION,
        RELEASE_LIVE_JOB_CONDITION,
        PUBLISH_JOB_CONDITION,
        REGISTRY_JOB_CONDITION,
    ]
    if sorted(conditions) != sorted(expected_conditions):
        raise CheckError(
            "publication must retain only the reviewed first-attempt release conditions"
        )

    monitoring_job = _workflow_job(live_workflow, "smoke", "live-smoke workflow")
    _require_exact_keys(
        monitoring_job,
        {"name", "if", "runs-on", "timeout-minutes", "environment", "steps"},
        "monitoring live-smoke job",
    )
    monitoring_condition = " ".join(
        _scalar(monitoring_job.get("if"), "monitoring live-smoke condition").split()
    )
    expected_monitoring_condition = (
        "github.ref == format('refs/heads/{0}', "
        "github.event.repository.default_branch) && "
        "vars.LIVE_SMOKE_ENABLED == 'true'"
    )
    if monitoring_condition != expected_monitoring_condition:
        raise CheckError(
            "monitoring live smoke must run only against the canonical default branch and "
            "require LIVE_SMOKE_ENABLED=true for every trigger"
        )
    live_jobs = _mapping(live_workflow.get("jobs"), "live-smoke workflow jobs")
    if set(live_jobs) != {"smoke"}:
        raise CheckError("monitoring live smoke must contain only its bounded smoke job")
    if "continue-on-error" in monitoring_job:
        raise CheckError("monitoring live smoke must not allow its job to fail")
    if any(key in monitoring_job for key in ("permissions", "defaults", "env", "shell")):
        raise CheckError("monitoring live smoke must retain workflow-level execution controls")
    for index, step in enumerate(_workflow_steps(monitoring_job, "monitoring live-smoke job")):
        _require_unconditional(step, f"monitoring live-smoke step {index}")
    if monitoring_job.get("timeout-minutes") != "10":
        raise CheckError("monitoring live smoke must have a ten-minute timeout")
    if monitoring_job.get("runs-on") != "ubuntu-latest":
        raise CheckError("monitoring live smoke must use the reviewed GitHub-hosted runner")
    if monitoring_job.get("environment") != "live-smoke":
        raise CheckError("monitoring live smoke must use its protected environment")
    _require_step_names(
        monitoring_job,
        [
            "Check out the trusted default branch",
            "Set up Python",
            "Install the pinned uv frontend",
            "Reproduce the locked environment",
            "Run the separately marked, bounded live suite",
        ],
        "monitoring live-smoke job",
    )
    _require_step_environments(
        monitoring_job,
        {
            "Run the separately marked, bounded live suite": {
                "COMETAPI_KEY": "${{ secrets.COMETAPI_KEY }}"
            }
        },
        "monitoring live-smoke job",
    )
    _require_step_working_directories(monitoring_job, {}, "monitoring live-smoke job")
    _, monitoring_checkout = _named_action_step(
        monitoring_job,
        "Check out the trusted default branch",
        "actions/checkout",
        "monitoring live-smoke job",
    )
    _require_options(
        monitoring_checkout,
        {
            "ref": "${{ github.event.repository.default_branch }}",
            "persist-credentials": "false",
        },
        "monitoring live-smoke checkout",
    )
    _, monitoring_setup = _named_action_step(
        monitoring_job, "Set up Python", "actions/setup-python", "monitoring live-smoke job"
    )
    _require_options(
        monitoring_setup, {"python-version": "3.14"}, "monitoring live-smoke Python setup"
    )
    _named_run_step(
        monitoring_job,
        "Install the pinned uv frontend",
        'python -m pip install --disable-pip-version-check "uv==$UV_VERSION"',
        "monitoring live-smoke job",
    )
    _named_run_step(
        monitoring_job,
        "Reproduce the locked environment",
        "uv sync --locked",
        "monitoring live-smoke job",
    )
    _, monitoring_test = _named_run_step(
        monitoring_job,
        "Run the separately marked, bounded live suite",
        "uv run pytest -m live --maxfail=1 -q",
        "monitoring live-smoke job",
    )
    monitoring_test_environment = _mapping(
        monitoring_test.get("env"), "monitoring live-smoke test environment"
    )
    if monitoring_test_environment != {"COMETAPI_KEY": "${{ secrets.COMETAPI_KEY }}"}:
        raise CheckError("monitoring live credentials must be scoped only to the bounded test step")
    if _secret_references(live_workflow) != ["${{ secrets.COMETAPI_KEY }}"]:
        raise CheckError("monitoring live smoke must use only its scoped COMETAPI_KEY")

    jobs = _mapping(workflow.get("jobs"), "publish workflow jobs")
    if set(jobs) != PUBLISH_JOB_NAMES:
        raise CheckError("publish workflow jobs must match the reviewed release chain")
    build = _workflow_job(workflow, "build", "publish workflow")
    release_live = _workflow_job(workflow, "release-live-smoke", "publish workflow")
    publish = _workflow_job(workflow, "publish", "publish workflow")
    registry = _workflow_job(workflow, "verify-registry", "publish workflow")
    expected_release_job_keys = {
        "build": {
            "name",
            "if",
            "needs",
            "runs-on",
            "timeout-minutes",
            "outputs",
            "permissions",
            "steps",
        },
        "release-live-smoke": {
            "name",
            "if",
            "needs",
            "concurrency",
            "runs-on",
            "timeout-minutes",
            "permissions",
            "environment",
            "env",
            "steps",
        },
        "publish": {
            "name",
            "if",
            "needs",
            "runs-on",
            "timeout-minutes",
            "environment",
            "permissions",
            "steps",
        },
        "verify-registry": {
            "name",
            "if",
            "needs",
            "runs-on",
            "timeout-minutes",
            "permissions",
            "steps",
        },
    }
    expected_release_conditions = {
        "build": BUILD_JOB_CONDITION,
        "release-live-smoke": RELEASE_LIVE_JOB_CONDITION,
        "publish": PUBLISH_JOB_CONDITION,
        "verify-registry": REGISTRY_JOB_CONDITION,
    }
    for name, job in (
        ("build", build),
        ("release-live-smoke", release_live),
        ("publish", publish),
        ("verify-registry", registry),
    ):
        _require_exact_keys(job, expected_release_job_keys[name], f"release {name} job")
        condition = " ".join(_scalar(job["if"], f"release {name} condition").split())
        if condition != expected_release_conditions[name]:
            raise CheckError(
                f"release {name} job must evaluate skipped ancestry, reject cancellation "
                "and reruns, and require every direct dependency to succeed"
            )
        _require_step_working_directories(
            job,
            ({"Recheck immutable artifact digests": "release-bundle"} if name == "publish" else {}),
            f"release {name} job",
        )
    for name, job, timeout in (
        ("build", build, "25"),
        ("release-live-smoke", release_live, "10"),
        ("publish", publish, "10"),
        ("verify-registry", registry, "10"),
    ):
        if job.get("runs-on") != "ubuntu-latest":
            raise CheckError(f"release {name} job must use the reviewed GitHub-hosted runner")
        if job.get("timeout-minutes") != timeout:
            raise CheckError(f"release {name} job must retain its reviewed timeout")
    for name, job in (("build", build), ("publish", publish), ("verify-registry", registry)):
        if "env" in job:
            raise CheckError(f"release {name} job must not override the workflow environment")

    _require_permissions(build, {"contents": "read"}, "release build job")
    _require_needs(build, ["select-release"], "release build job")
    outputs = _mapping(build.get("outputs"), "release build outputs")
    if outputs != {
        "release-commit": "${{ steps.trust.outputs.release-commit }}",
        "version": "${{ steps.version.outputs.version }}",
    }:
        raise CheckError("release build must expose only its verified commit and version")
    _require_step_names(
        build,
        [
            "Check out the published release tag",
            "Reject an untrusted release target",
            "Set up Python",
            "Install the pinned uv frontend",
            "Reproduce the locked environment",
            "Verify project, manifest, changelog, release docs, and tag agreement",
            "Scan the immutable source for credentials and scope mistakes",
            "Verify release-workflow trust semantics",
            "Build wheel and source distribution from the tag",
            "Verify artifact versions against the tag",
            "Check package metadata rendering",
            "Inspect artifact identity and shape",
            "Install and smoke-test each exact artifact",
            "Record immutable artifact digests",
            "Retain only the verified release bundle",
        ],
        "release build job",
    )
    _require_step_environments(
        build,
        {
            "Reject an untrusted release target": {
                "DEFAULT_BRANCH": "${{ github.event.repository.default_branch }}",
                "EXPECTED_RELEASE_SHA": "${{ needs.select-release.outputs.release-sha }}",
                "RELEASE_IMMUTABLE": "true",
                "RELEASE_TAG": "${{ needs.select-release.outputs.release-tag }}",
            },
            "Verify project, manifest, changelog, release docs, and tag agreement": {
                "RELEASE_TAG": "${{ needs.select-release.outputs.release-tag }}"
            },
            "Verify artifact versions against the tag": {
                "RELEASE_TAG": "${{ needs.select-release.outputs.release-tag }}"
            },
        },
        "release build job",
    )
    _, build_checkout = _named_action_step(
        build,
        "Check out the published release tag",
        "actions/checkout",
        "release build job",
    )
    _require_options(
        build_checkout,
        {
            "ref": "refs/tags/${{ needs.select-release.outputs.release-tag }}",
            "fetch-depth": "0",
            "persist-credentials": "false",
        },
        "release build checkout",
    )
    _, trust_step = _named_run_step(
        build,
        "Reject an untrusted release target",
        "bash scripts/verify_release_trust.sh",
        "release build job",
    )
    if trust_step.get("id") != "trust":
        raise CheckError("release trust step must expose the trust output id")
    trust_environment = _mapping(trust_step.get("env"), "release trust environment")
    if trust_environment != {
        "DEFAULT_BRANCH": "${{ github.event.repository.default_branch }}",
        "EXPECTED_RELEASE_SHA": "${{ needs.select-release.outputs.release-sha }}",
        "RELEASE_IMMUTABLE": "true",
        "RELEASE_TAG": "${{ needs.select-release.outputs.release-tag }}",
    }:
        raise CheckError("release trust step must receive only the immutable release identity")
    _, build_setup = _named_action_step(
        build, "Set up Python", "actions/setup-python", "release build job"
    )
    _require_options(build_setup, {"python-version": "3.14"}, "release build Python setup")
    build_commands = {
        "Install the pinned uv frontend": (
            'python -m pip install --disable-pip-version-check "uv==$UV_VERSION"'
        ),
        "Reproduce the locked environment": "uv sync --locked",
        "Scan the immutable source for credentials and scope mistakes": (
            "uv run python scripts/check_secrets.py"
        ),
        "Verify release-workflow trust semantics": "uv run python scripts/check_workflows.py",
        "Build wheel and source distribution from the tag": "uv build",
        "Verify artifact versions against the tag": (
            'uv run python scripts/check_version.py --tag "$RELEASE_TAG" '
            "--require-changelog --require-releasable-docs dist/*"
        ),
        "Check package metadata rendering": "uv run twine check dist/*",
        "Inspect artifact identity and shape": "uv run python scripts/check_artifacts.py dist/*",
        "Install and smoke-test each exact artifact": (
            "uv run python scripts/check_clean_install.py dist/*"
        ),
        "Record immutable artifact digests": "sha256sum dist/* > artifact-sha256.txt",
    }
    for name, command in build_commands.items():
        _named_run_step(build, name, command, "release build job")
    _, version_step = _named_run_step(
        build,
        "Verify project, manifest, changelog, release docs, and tag agreement",
        'version=$(uv run python scripts/check_version.py --tag "$RELEASE_TAG" '
        "--require-changelog --require-releasable-docs --print-version)\n"
        'echo "version=$version" >> "$GITHUB_OUTPUT"\n',
        "release build job",
    )
    if version_step.get("id") != "version" or _mapping(
        version_step.get("env"), "release version environment"
    ) != {"RELEASE_TAG": "${{ needs.select-release.outputs.release-tag }}"}:
        raise CheckError("release version step must expose the verified tag-derived version")
    _, artifact_upload = _named_action_step(
        build,
        "Retain only the verified release bundle",
        "actions/upload-artifact",
        "release build job",
    )
    _require_options(
        artifact_upload,
        {
            "name": "release-${{ steps.version.outputs.version }}",
            "path": "dist/*\nartifact-sha256.txt\n",
            "if-no-files-found": "error",
            "retention-days": "30",
        },
        "release bundle upload",
    )

    _require_permissions(release_live, {"contents": "read"}, "exact-release live-smoke job")
    _require_needs(release_live, ["build"], "exact-release live-smoke job")
    if release_live.get("timeout-minutes") != "10":
        raise CheckError("exact-release live smoke must have a ten-minute timeout")
    if release_live.get("environment") != "live-smoke":
        raise CheckError("exact-release live smoke must use its protected environment")
    release_live_concurrency = _mapping(
        release_live.get("concurrency"), "exact-release live-smoke concurrency"
    )
    if release_live_concurrency != {
        "group": "trusted-live-smoke",
        "cancel-in-progress": "false",
    }:
        raise CheckError(
            "release and monitoring live smokes must share one non-cancelling concurrency group"
        )
    release_live_environment = _mapping(
        release_live.get("env"), "exact-release live-smoke environment"
    )
    if release_live_environment != {
        "COMETAPI_LIVE_CONCURRENCY": "1",
        "COMETAPI_LIVE_MAX_OUTPUT_TOKENS": "64",
        "COMETAPI_LIVE_MAX_REQUESTS": "4",
        "COMETAPI_LIVE_MODEL": CANONICAL_ACTIVE_MODEL,
        "COMETAPI_LIVE_REQUEST_TIMEOUT_SECONDS": "30",
        "COMETAPI_LIVE_RUN": "1",
        "COMETAPI_LIVE_STOP_ON_FAILURE": "1",
    }:
        raise CheckError("exact-release live smoke must retain its bounded execution budget")
    _require_step_names(
        release_live,
        [
            "Require the protected live credential",
            "Check out the verified release commit",
            "Require the exact verified release commit",
            "Set up Python",
            "Install the pinned uv frontend",
            "Reproduce the locked release environment",
            "Run the bounded exact-release live suite",
        ],
        "exact-release live-smoke job",
    )
    _require_step_environments(
        release_live,
        {
            "Require the protected live credential": {
                "COMETAPI_KEY": "${{ secrets.COMETAPI_KEY }}"
            },
            "Require the exact verified release commit": {
                "RELEASE_COMMIT": "${{ needs.build.outputs.release-commit }}"
            },
            "Run the bounded exact-release live suite": {
                "COMETAPI_KEY": "${{ secrets.COMETAPI_KEY }}"
            },
        },
        "exact-release live-smoke job",
    )
    _, credential_check = _named_run_step(
        release_live,
        "Require the protected live credential",
        'test -n "$COMETAPI_KEY"',
        "exact-release live-smoke job",
    )
    if _mapping(credential_check.get("env"), "exact-release credential-check environment") != {
        "COMETAPI_KEY": "${{ secrets.COMETAPI_KEY }}"
    }:
        raise CheckError("exact-release live credential preflight must stay step-scoped")
    _, release_checkout = _named_action_step(
        release_live,
        "Check out the verified release commit",
        "actions/checkout",
        "exact-release live-smoke job",
    )
    _require_options(
        release_checkout,
        {
            "ref": "${{ needs.build.outputs.release-commit }}",
            "persist-credentials": "false",
        },
        "exact-release live-smoke checkout",
    )
    _, commit_check = _named_run_step(
        release_live,
        "Require the exact verified release commit",
        'test "$(git rev-parse HEAD)" = "$RELEASE_COMMIT"',
        "exact-release live-smoke job",
    )
    if _mapping(commit_check.get("env"), "exact-release commit-check environment") != {
        "RELEASE_COMMIT": "${{ needs.build.outputs.release-commit }}"
    }:
        raise CheckError("exact-release commit check must use only the verified build output")
    _, release_setup = _named_action_step(
        release_live, "Set up Python", "actions/setup-python", "exact-release live-smoke job"
    )
    _require_options(
        release_setup, {"python-version": "3.14"}, "exact-release live-smoke Python setup"
    )
    _named_run_step(
        release_live,
        "Install the pinned uv frontend",
        'python -m pip install --disable-pip-version-check "uv==$UV_VERSION"',
        "exact-release live-smoke job",
    )
    _named_run_step(
        release_live,
        "Reproduce the locked release environment",
        "uv sync --locked",
        "exact-release live-smoke job",
    )
    _, live_test = _named_run_step(
        release_live,
        "Run the bounded exact-release live suite",
        "uv run pytest -m live --maxfail=1 -q",
        "exact-release live-smoke job",
    )
    if _mapping(live_test.get("env"), "exact-release live test environment") != {
        "COMETAPI_KEY": "${{ secrets.COMETAPI_KEY }}"
    }:
        raise CheckError("exact-release live credential must be scoped only to its test step")

    _require_permissions(publish, {"contents": "read", "id-token": "write"}, "PyPI publish job")
    _require_needs(
        publish,
        ["build", "release-live-smoke"],
        "PyPI publish job",
    )
    publish_environment = _mapping(publish.get("environment"), "PyPI publish environment")
    if publish_environment != {
        "name": "pypi",
        "url": "https://pypi.org/project/cometapi/${{ needs.build.outputs.version }}/",
    }:
        raise CheckError("publish must use the protected pypi environment and exact package URL")
    _require_step_names(
        publish,
        [
            "Download the verified release bundle",
            "Recheck immutable artifact digests",
            "Publish through the configured PyPI Trusted Publisher",
        ],
        "PyPI publish job",
    )
    _require_step_environments(publish, {}, "PyPI publish job")
    _, publish_download = _named_action_step(
        publish,
        "Download the verified release bundle",
        "actions/download-artifact",
        "PyPI publish job",
    )
    _require_options(
        publish_download,
        {
            "name": "release-${{ needs.build.outputs.version }}",
            "path": "release-bundle",
        },
        "PyPI release-bundle download",
    )
    _, publish_digest = _named_run_step(
        publish,
        "Recheck immutable artifact digests",
        "sha256sum --check artifact-sha256.txt",
        "PyPI publish job",
    )
    if publish_digest.get("working-directory") != "release-bundle":
        raise CheckError("PyPI publish job must recheck digests inside the retained bundle")
    _, pypi_publish = _named_action_step(
        publish,
        "Publish through the configured PyPI Trusted Publisher",
        "pypa/gh-action-pypi-publish",
        "PyPI publish job",
    )
    if pypi_publish.get("uses") != PYPI_PUBLISH_ACTION:
        raise CheckError(f"PyPI publish job must use exact reviewed action {PYPI_PUBLISH_ACTION}")
    _require_options(
        pypi_publish,
        {
            "packages-dir": "release-bundle/dist/",
            "print-hash": "true",
            "attestations": "true",
        },
        "PyPI Trusted Publisher action",
    )

    _require_permissions(registry, {"contents": "read"}, "registry verification job")
    _require_needs(registry, ["build", "publish"], "registry verification job")
    registry_step_names = [
        step.get("name") for step in _workflow_steps(registry, "registry verification job")
    ]
    checkout_name = "Check out the registry verification source"
    download_name = "Download the verified release bundle after checkout"
    if (
        checkout_name in registry_step_names
        and download_name in registry_step_names
        and registry_step_names.index(checkout_name) > registry_step_names.index(download_name)
    ):
        raise CheckError(
            "registry verification must check out source before downloading the release bundle"
        )
    _require_step_names(
        registry,
        [
            checkout_name,
            download_name,
            "Require retained pre-publication digest evidence",
            "Set up Python",
            "Install the pinned provenance verifier",
            "Verify public artifact identity, digests, and provenance",
            "Install from public PyPI and run the isolated mocked-call smoke",
        ],
        "registry verification job",
    )
    _require_step_environments(
        registry,
        {
            "Install the pinned provenance verifier": {
                "PIP_BUILD_CONSTRAINT": "",
                "PIP_CONFIG_FILE": "/dev/null",
                "PIP_CONSTRAINT": "",
                "PIP_EXTRA_INDEX_URL": "",
                "PIP_FIND_LINKS": "",
                "PIP_REQUIREMENT": "",
            },
            "Verify public artifact identity, digests, and provenance": {
                "RELEASE_VERSION": "${{ needs.build.outputs.version }}"
            },
            "Install from public PyPI and run the isolated mocked-call smoke": {
                "RELEASE_VERSION": "${{ needs.build.outputs.version }}"
            },
        },
        "registry verification job",
    )
    _, registry_checkout = _named_action_step(
        registry,
        "Check out the registry verification source",
        "actions/checkout",
        "registry verification job",
    )
    _require_options(
        registry_checkout,
        {
            "ref": "${{ needs.build.outputs.release-commit }}",
            "persist-credentials": "false",
        },
        "registry verification checkout",
    )
    _, registry_download = _named_action_step(
        registry,
        "Download the verified release bundle after checkout",
        "actions/download-artifact",
        "registry verification job",
    )
    _require_options(
        registry_download,
        {
            "name": "release-${{ needs.build.outputs.version }}",
            "path": "release-bundle",
        },
        "registry release-bundle download",
    )
    _named_run_step(
        registry,
        "Require retained pre-publication digest evidence",
        "test -f release-bundle/artifact-sha256.txt",
        "registry verification job",
    )
    _, registry_setup = _named_action_step(
        registry, "Set up Python", "actions/setup-python", "registry verification job"
    )
    _require_options(
        registry_setup, {"python-version": "3.14"}, "registry verification Python setup"
    )
    _, verifier_install = _named_run_step(
        registry,
        "Install the pinned provenance verifier",
        "python -m pip --isolated install --disable-pip-version-check "
        "--index-url https://pypi.org/simple/ --no-cache-dir "
        '"pypi-attestations==0.0.29"',
        "registry verification job",
    )
    if _mapping(verifier_install.get("env"), "provenance verifier environment") != {
        "PIP_BUILD_CONSTRAINT": "",
        "PIP_CONFIG_FILE": "/dev/null",
        "PIP_CONSTRAINT": "",
        "PIP_EXTRA_INDEX_URL": "",
        "PIP_FIND_LINKS": "",
        "PIP_REQUIREMENT": "",
    }:
        raise CheckError("provenance verifier must ignore ambient package configuration")
    _, registry_verification = _named_run_step(
        registry,
        "Verify public artifact identity, digests, and provenance",
        'python scripts/check_registry_release.py --version "$RELEASE_VERSION" '
        '--repository "https://github.com/${{ github.repository }}" '
        "--digest-file release-bundle/artifact-sha256.txt "
        "--download-directory registry-artifacts --attempts 12 --retry-delay 10",
        "registry verification job",
    )
    if _mapping(registry_verification.get("env"), "registry verification environment") != {
        "RELEASE_VERSION": "${{ needs.build.outputs.version }}"
    }:
        raise CheckError("registry verification must use the verified build version")
    _, public_install = _named_run_step(
        registry,
        "Install from public PyPI and run the isolated mocked-call smoke",
        'python scripts/check_clean_install.py --expected-version "$RELEASE_VERSION" '
        '--requirement "cometapi==$RELEASE_VERSION" '
        "--index-url https://pypi.org/simple/ --attempts 12 --retry-delay 10",
        "registry verification job",
    )
    if _mapping(public_install.get("env"), "registry clean-install environment") != {
        "RELEASE_VERSION": "${{ needs.build.outputs.version }}"
    }:
        raise CheckError("registry clean install must use the verified build version")

    if _secret_references(workflow) != [
        "${{ secrets.COMETAPI_KEY }}",
        "${{ secrets.COMETAPI_KEY }}",
    ]:
        raise CheckError(
            "COMETAPI_KEY must appear only in the exact-release credential preflight and test"
        )


def workflow_paths(directory: Path) -> list[Path]:
    return sorted(path for path in directory.iterdir() if path.suffix in {".yaml", ".yml"})


def check_workflow_inventory(directory: Path) -> list[Path]:
    if directory.is_symlink() or directory.parent.is_symlink() or not directory.is_dir():
        raise CheckError(
            "workflow directory and .github parent must be real repository directories"
        )
    paths = workflow_paths(directory)
    expected = {
        "ci.yml",
        "live-smoke.yml",
        "publish.yml",
    }
    actual = {path.name for path in paths}
    if actual != expected:
        missing = ", ".join(sorted(expected - actual)) or "none"
        unexpected = ", ".join(sorted(actual - expected)) or "none"
        raise CheckError(
            "workflow inventory does not match the reviewed contract "
            f"(missing: {missing}; unexpected: {unexpected})"
        )
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise CheckError(f"{path.name}: reviewed workflows must be regular, non-symlink files")
    return paths


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
        "--ci-workflow",
        type=Path,
        default=PROJECT_ROOT / ".github" / "workflows" / "ci.yml",
    )
    parser.add_argument(
        "--release-please-config",
        type=Path,
        default=PROJECT_ROOT / "release-please-config.json",
    )
    parser.add_argument(
        "--release-please-manifest",
        type=Path,
        default=PROJECT_ROOT / ".release-please-manifest.json",
    )
    args = parser.parse_args()
    paths = check_workflow_inventory(args.ci_workflow.parent)
    publish_text = args.publish_workflow.read_text(encoding="utf-8")
    check_publish_workflow(
        publish_text,
        args.live_smoke_workflow.read_text(encoding="utf-8"),
    )
    check_release_please_config(
        args.release_please_config.read_text(encoding="utf-8"),
        args.release_please_manifest.read_text(encoding="utf-8"),
    )
    check_ci_workflow(args.ci_workflow.read_text(encoding="utf-8"))
    for path in paths:
        check_action_pins(path.read_text(encoding="utf-8"), path.name)
    print("release workflow semantic checks passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CheckError, OSError) as error:
        raise SystemExit(f"workflow semantic check failed: {error}") from error
