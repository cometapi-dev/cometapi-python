from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts.check_workflows import (
    check_action_pins,
    check_ci_workflow,
    check_publish_workflow,
    check_release_please_config,
    check_release_please_workflow,
    check_release_recovery_workflow,
    check_workflow_inventory,
    workflow_paths,
)
from tests.live.test_live_smoke import resolve_live_model

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
PUBLISH_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "publish.yml"
LIVE_SMOKE_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "live-smoke.yml"
RELEASE_PLEASE_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "release-please.yml"
RELEASE_RECOVERY_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "release-recovery.yml"
RELEASE_PLEASE_CONFIG = PROJECT_ROOT / "release-please-config.json"
RELEASE_PLEASE_MANIFEST = PROJECT_ROOT / ".release-please-manifest.json"
TRUST_SCRIPT = PROJECT_ROOT / "scripts" / "verify_release_trust.sh"


def _reviewed_release_please_bridge_config() -> str:
    stable = RELEASE_PLEASE_CONFIG.read_text(encoding="utf-8")
    marker = '  "include-v-in-tag": true,\n'
    if marker not in stable:
        raise AssertionError("stable Release Please config lost its tag contract")
    bridge = (
        '  "last-release-sha": "31b68904141489ca04932edbf305ccf88af09372",\n'
        '  "prerelease": false,\n'
        '  "versioning": "prerelease",\n'
    )
    return stable.replace(marker, marker + bridge, 1)


def _git(root: Path, *arguments: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        input=input_text,
        text=True,
        check=True,
        capture_output=True,
    )
    return result.stdout.strip()


@pytest.fixture
def release_repository(tmp_path: Path) -> tuple[Path, str]:
    remote = tmp_path / "origin.git"
    repository = tmp_path / "repository"
    remote.mkdir()
    repository.mkdir()
    _git(remote, "init", "--bare")
    _git(repository, "init", "--initial-branch=main")
    _git(repository, "config", "user.name", "Release Contract")
    _git(repository, "config", "user.email", "release-contract@example.invalid")
    (repository / "tracked.txt").write_text("main\n", encoding="utf-8")
    _git(repository, "add", "tracked.txt")
    _git(repository, "commit", "-m", "initial")
    release_commit = _git(repository, "rev-parse", "HEAD")
    _git(repository, "tag", "v0.1.0-alpha.1")
    _git(repository, "remote", "add", "origin", str(remote))
    _git(repository, "push", "--set-upstream", "origin", "main")
    _git(repository, "checkout", "--detach", "v0.1.0-alpha.1")
    return repository, release_commit


def _verify_trust(
    repository: Path,
    tmp_path: Path,
    *,
    immutable: str = "true",
    tag: str = "v0.1.0-alpha.1",
    expected_release_sha: str | None = None,
) -> subprocess.CompletedProcess[str]:
    output = tmp_path / "github-output.txt"
    environment = os.environ.copy()
    environment.update(
        {
            "DEFAULT_BRANCH": "main",
            "EXPECTED_RELEASE_SHA": expected_release_sha
            or _git(repository, "rev-parse", f"{tag}^{{commit}}"),
            "GITHUB_OUTPUT": str(output),
            "RELEASE_IMMUTABLE": immutable,
            "RELEASE_TAG": tag,
        }
    )
    return subprocess.run(
        ["bash", str(TRUST_SCRIPT)],
        cwd=repository,
        env=environment,
        text=True,
        check=False,
        capture_output=True,
    )


def _step(text: str, name: str) -> tuple[int, int]:
    start = text.index(f"      - name: {name}")
    next_step = text.find("\n      - name: ", start + 1)
    return start, len(text) if next_step < 0 else next_step + 1


def _bypass_immutable_event(text: str) -> str:
    return text.replace(
        'RELEASE_IMMUTABLE: "true"',
        'RELEASE_IMMUTABLE: "false"',
        1,
    )


def _remove_live_dependency(text: str) -> str:
    return text.replace("      - release-live-smoke\n", "", 1)


def _bypass_verified_release_commit(text: str) -> str:
    return text.replace(
        "ref: ${{ needs.build.outputs.release-commit }}",
        "ref: ${{ github.event.release.tag_name }}",
        1,
    )


def _remove_publication_serialization(text: str) -> str:
    return text.replace("group: pypi-publish", "group: pypi-release-tag", 1)


def _split_live_concurrency_group(text: str) -> str:
    return text.replace("group: trusted-live-smoke", "group: release-live-smoke", 1)


def _remove_registry_publish_dependency(text: str) -> str:
    registry_start = text.index("  verify-registry:")
    return text[:registry_start] + text[registry_start:].replace("      - publish\n", "", 1)


def _grant_build_write_permission(text: str) -> str:
    build_start = text.index("  build:")
    return text[:build_start] + text[build_start:].replace(
        "permissions:\n      contents: read",
        "permissions:\n      contents: read\n      actions: write",
        1,
    )


def _broaden_live_credential_scope(text: str) -> str:
    text = text.replace(
        '      COMETAPI_LIVE_CONCURRENCY: "1"',
        '      COMETAPI_KEY: ${{ secrets.COMETAPI_KEY }}\n      COMETAPI_LIVE_CONCURRENCY: "1"',
        1,
    )
    return text.replace(
        "        env:\n          COMETAPI_KEY: ${{ secrets.COMETAPI_KEY }}\n",
        "",
        1,
    )


def _remove_public_registry_install(text: str) -> str:
    start, end = _step(text, "Install from public PyPI and run the isolated mocked-call smoke")
    return text[:start] + text[end:]


def _weaken_verifier_bootstrap(text: str) -> str:
    return (
        text.replace("          PIP_CONFIG_FILE: /dev/null\n", "", 1)
        .replace("python -m pip --isolated install", "python -m pip install", 1)
        .replace("          --no-cache-dir\n", "", 1)
    )


def _publish_regardless_of_failed_dependencies(text: str) -> str:
    return text.replace(
        "      - release-live-smoke\n    runs-on: ubuntu-latest",
        "      - release-live-smoke\n    if: always()\n    runs-on: ubuntu-latest",
        1,
    )


def _continue_after_live_failure(text: str) -> str:
    return text.replace(
        "      - name: Run the bounded exact-release live suite\n",
        "      - name: Run the bounded exact-release live suite\n        continue-on-error: true\n",
        1,
    )


def _continue_after_provenance_failure(text: str) -> str:
    return text.replace(
        "      - name: Verify public artifact identity, digests, and provenance\n",
        "      - name: Verify public artifact identity, digests, and provenance\n"
        "        continue-on-error: true\n",
        1,
    )


def _continue_after_public_install_failure(text: str) -> str:
    return text.replace(
        "      - name: Install from public PyPI and run the isolated mocked-call smoke\n",
        "      - name: Install from public PyPI and run the isolated mocked-call smoke\n"
        "        continue-on-error: true\n",
        1,
    )


def _grant_build_write_all(text: str) -> str:
    build_start = text.index("  build:")
    return text[:build_start] + text[build_start:].replace(
        "permissions:\n      contents: read",
        "permissions: write-all",
        1,
    )


def _replace_protected_live_environment(text: str) -> str:
    return text.replace(
        "    environment: live-smoke",
        "    environment: unprotected\n    # environment: live-smoke",
        1,
    )


def _replace_protected_pypi_environment(text: str) -> str:
    return text.replace(
        "      name: pypi",
        "      name: unprotected\n      # name: pypi",
        1,
    )


def _swallow_trust_failure(text: str) -> str:
    return text.replace(
        "run: bash scripts/verify_release_trust.sh",
        'run: bash scripts/verify_release_trust.sh || echo "release-commit=fallback"',
        1,
    )


def _swallow_live_failure(text: str) -> str:
    return text.replace(
        "run: uv run pytest -m live --maxfail=1 -q",
        "run: uv run pytest -m live --maxfail=1 -q || true",
        1,
    )


def _swallow_provenance_failure(text: str) -> str:
    provenance_start = text.index(
        "      - name: Verify public artifact identity, digests, and provenance"
    )
    return text[:provenance_start] + text[provenance_start:].replace(
        "          --retry-delay 10\n",
        "          --retry-delay 10 || true\n",
        1,
    )


def _swallow_public_install_failure(text: str) -> str:
    install_start = text.index(
        "      - name: Install from public PyPI and run the isolated mocked-call smoke"
    )
    return text[:install_start] + text[install_start:].replace(
        "          --retry-delay 10\n",
        "          --retry-delay 10 || true\n",
        1,
    )


def _quote_publish_if_key(text: str) -> str:
    return text.replace(
        "      - release-live-smoke\n    runs-on: ubuntu-latest",
        '      - release-live-smoke\n    "if": always()\n    runs-on: ubuntu-latest',
        1,
    )


def _quote_build_write_permission(text: str) -> str:
    build_start = text.index("  build:")
    return text[:build_start] + text[build_start:].replace(
        "permissions:\n      contents: read",
        'permissions:\n      contents: read\n      "actions": write',
        1,
    )


def _remove_live_model_fallback(text: str) -> str:
    return text.replace(
        "COMETAPI_LIVE_MODEL: ${{ vars.COMETAPI_LIVE_MODEL || 'gpt-5.4' }}",
        "COMETAPI_LIVE_MODEL: ${{ vars.COMETAPI_LIVE_MODEL }}",
        1,
    )


def _remove_live_credential_preflight(text: str) -> str:
    start, end = _step(text, "Require the protected live credential")
    return text[:start] + text[end:]


def _allow_publication_rerun(text: str) -> str:
    return text.replace("    if: github.run_attempt == 1\n", "    if: always()\n", 1)


PUBLICATION_BYPASSES: list[Callable[[str], str]] = [
    _bypass_immutable_event,
    _remove_live_dependency,
    _bypass_verified_release_commit,
    _remove_publication_serialization,
    _split_live_concurrency_group,
    _remove_registry_publish_dependency,
    _grant_build_write_permission,
    _broaden_live_credential_scope,
    _remove_public_registry_install,
    _weaken_verifier_bootstrap,
    _publish_regardless_of_failed_dependencies,
    _continue_after_live_failure,
    _continue_after_provenance_failure,
    _continue_after_public_install_failure,
    _grant_build_write_all,
    _replace_protected_live_environment,
    _replace_protected_pypi_environment,
    _swallow_trust_failure,
    _swallow_live_failure,
    _swallow_provenance_failure,
    _swallow_public_install_failure,
    _quote_publish_if_key,
    _quote_build_write_permission,
    _remove_live_model_fallback,
    _remove_live_credential_preflight,
    _allow_publication_rerun,
]


def test_current_publish_workflow_satisfies_semantic_contract() -> None:
    check_publish_workflow(
        PUBLISH_WORKFLOW.read_text(encoding="utf-8"),
        LIVE_SMOKE_WORKFLOW.read_text(encoding="utf-8"),
    )


@pytest.mark.parametrize("configured", [None, ""])
def test_live_model_defaults_when_unset_or_empty(configured: str | None) -> None:
    assert resolve_live_model(configured) == "gpt-5.4"


def test_workflow_contract_rejects_mutable_action_reference() -> None:
    text, replacements = re.subn(
        r"(actions/checkout@)[0-9a-f]{40}",
        r"\g<1>v4",
        CI_WORKFLOW.read_text(encoding="utf-8"),
        count=1,
    )
    assert replacements == 1
    with pytest.raises(RuntimeError, match="full commit SHA"):
        check_action_pins(text, CI_WORKFLOW.name)


@pytest.mark.parametrize(
    "text",
    [
        "jobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n"
        '      - "uses": actions/checkout@v4\n',
        "jobs:\n  check:\n    runs-on: ubuntu-latest\n    steps: [{ uses: actions/checkout@v4 }]\n",
        "jobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - uses: >-\n          actions/checkout@v4\n",
        "checkout: &checkout actions/checkout@v4\njobs:\n  check:\n"
        "    runs-on: ubuntu-latest\n    steps:\n      - uses: *checkout\n",
        "jobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - ? uses\n        : actions/checkout@v4\n",
        "jobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - uses: !!str actions/checkout@v4\n",
    ],
    ids=[
        "quoted-key",
        "inline-mapping",
        "folded-scalar",
        "alias",
        "explicit-mapping",
        "tagged-scalar",
    ],
)
def test_workflow_contract_rejects_disguised_mutable_action_reference(text: str) -> None:
    with pytest.raises(RuntimeError, match="full commit SHA"):
        check_action_pins(text, "adversarial workflow")


def test_workflow_contract_ignores_nonsemantic_uses_key() -> None:
    text = """\
env:
  uses: actions/checkout@v4
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: echo checked
"""
    check_action_pins(text, "nonsemantic uses workflow")


def test_workflow_contract_rejects_unpinned_docker_action() -> None:
    text = """\
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: docker://alpine:latest
"""
    with pytest.raises(RuntimeError, match="Docker action references are not permitted"):
        check_action_pins(text, "Docker workflow")


@pytest.mark.parametrize(
    "mutation",
    PUBLICATION_BYPASSES,
    ids=[
        "immutable-event-bypass",
        "live-dependency-bypass",
        "release-commit-bypass",
        "publication-concurrency-bypass",
        "live-concurrency-bypass",
        "registry-publication-bypass",
        "build-write-permission-bypass",
        "live-credential-scope-bypass",
        "public-registry-install-bypass",
        "verifier-bootstrap-bypass",
        "publish-always-bypass",
        "live-continue-on-error-bypass",
        "provenance-continue-on-error-bypass",
        "public-install-continue-on-error-bypass",
        "build-write-all-bypass",
        "live-environment-comment-bypass",
        "pypi-environment-comment-bypass",
        "trust-shell-failure-bypass",
        "live-shell-failure-bypass",
        "provenance-shell-failure-bypass",
        "public-install-shell-failure-bypass",
        "quoted-publish-if-bypass",
        "quoted-build-write-bypass",
        "empty-live-model-bypass",
        "missing-live-credential-preflight",
        "publication-rerun-bypass",
    ],
)
def test_semantic_contract_rejects_publication_bypasses(
    mutation: Callable[[str], str],
) -> None:
    with pytest.raises(RuntimeError):
        check_publish_workflow(
            mutation(PUBLISH_WORKFLOW.read_text(encoding="utf-8")),
            LIVE_SMOKE_WORKFLOW.read_text(encoding="utf-8"),
        )


@pytest.mark.parametrize(
    ("needle", "replacement"),
    [
        (
            "run: bash scripts/verify_release_trust.sh",
            'run: echo "bash scripts/verify_release_trust.sh"',
        ),
        (
            "run: uv run python scripts/check_workflows.py",
            "run: uv run python scripts/check_workflows.py | true",
        ),
        (
            'run: test "$(git rev-parse HEAD)" = "$RELEASE_COMMIT"',
            "run: true",
        ),
        (
            "run: uv run pytest -m live --maxfail=1 -q",
            "run: uv run pytest -m live --maxfail=1 -q --collect-only",
        ),
        (
            "run: sha256sum --check artifact-sha256.txt",
            'run: echo "sha256sum --check artifact-sha256.txt"',
        ),
        (
            "uses: pypa/gh-action-pypi-publish@",
            "uses: attacker/example-action@",
        ),
        (
            "python -m pip --isolated install",
            "echo python -m pip --isolated install",
        ),
        (
            "python scripts/check_registry_release.py",
            "echo python scripts/check_registry_release.py",
        ),
        (
            "python scripts/check_clean_install.py\n"
            '          --expected-version "$RELEASE_VERSION"',
            "echo python scripts/check_clean_install.py\n"
            '          --expected-version "$RELEASE_VERSION"',
        ),
    ],
    ids=[
        "trust-echo-decoy",
        "workflow-check-pipe-bypass",
        "commit-check-noop",
        "live-collect-only",
        "publish-digest-echo-decoy",
        "arbitrary-oidc-action",
        "provenance-install-echo-decoy",
        "registry-verification-echo-decoy",
        "registry-install-echo-decoy",
    ],
)
def test_semantic_contract_rejects_exact_step_decoys(needle: str, replacement: str) -> None:
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    assert needle in text
    with pytest.raises(RuntimeError):
        check_publish_workflow(
            text.replace(needle, replacement, 1),
            LIVE_SMOKE_WORKFLOW.read_text(encoding="utf-8"),
        )


def test_semantic_contract_rejects_registry_ref_decoy() -> None:
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    registry_start = text.index("  verify-registry:")
    registry = text[registry_start:].replace(
        "ref: ${{ needs.build.outputs.release-commit }}",
        "ref: main\n"
        "        env:\n"
        "          EXPECTED_REF: ${{ needs.build.outputs.release-commit }}",
        1,
    )
    with pytest.raises(RuntimeError):
        check_publish_workflow(
            text[:registry_start] + registry,
            LIVE_SMOKE_WORKFLOW.read_text(encoding="utf-8"),
        )


def test_semantic_contract_rejects_publish_environment_test_bypass() -> None:
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8").replace(
        "  UV_VERSION: 0.11.8",
        "  UV_VERSION: 0.11.8\n  PYTEST_ADDOPTS: --collect-only",
        1,
    )
    with pytest.raises(RuntimeError, match="pinned uv"):
        check_publish_workflow(
            text,
            LIVE_SMOKE_WORKFLOW.read_text(encoding="utf-8"),
        )


def test_semantic_contract_rejects_extra_oidc_step() -> None:
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8").replace(
        "    steps:\n      - name: Download the verified release bundle",
        "    steps:\n"
        "      - name: Unreviewed OIDC consumer\n"
        "        uses: attacker/example-action@"
        "0123456789abcdef0123456789abcdef01234567\n"
        "      - name: Download the verified release bundle",
        1,
    )
    with pytest.raises(RuntimeError, match="reviewed sequence"):
        check_publish_workflow(
            text,
            LIVE_SMOKE_WORKFLOW.read_text(encoding="utf-8"),
        )


def test_semantic_contract_rejects_split_monitoring_live_concurrency() -> None:
    live_smoke = LIVE_SMOKE_WORKFLOW.read_text(encoding="utf-8").replace(
        "group: trusted-live-smoke", "group: monitoring-live-smoke", 1
    )
    with pytest.raises(RuntimeError, match="monitoring live smokes must share"):
        check_publish_workflow(
            PUBLISH_WORKFLOW.read_text(encoding="utf-8"),
            live_smoke,
        )


@pytest.mark.parametrize(
    "replacement",
    [
        "github.event_name == 'workflow_dispatch'",
        "(github.event_name == 'workflow_dispatch' || vars.LIVE_SMOKE_ENABLED == 'true')",
        "vars.LIVE_SMOKE_ENABLED != 'false'",
        "vars.LIVE_SMOKE_ENABLED == 'true'\n      || github.event_name == 'workflow_dispatch'",
    ],
    ids=["manual-only", "manual-bypass", "non-exact-opt-in", "continued-manual-bypass"],
)
def test_semantic_contract_rejects_live_smoke_gate_bypasses(replacement: str) -> None:
    live_smoke = LIVE_SMOKE_WORKFLOW.read_text(encoding="utf-8").replace(
        "vars.LIVE_SMOKE_ENABLED == 'true'",
        replacement,
        1,
    )
    with pytest.raises(RuntimeError, match="every trigger"):
        check_publish_workflow(
            PUBLISH_WORKFLOW.read_text(encoding="utf-8"),
            live_smoke,
        )


def test_semantic_contract_checks_live_smoke_gate_on_smoke_job() -> None:
    live_smoke = LIVE_SMOKE_WORKFLOW.read_text(encoding="utf-8").replace(
        "vars.LIVE_SMOKE_ENABLED == 'true'",
        "github.event_name == 'workflow_dispatch'",
        1,
    )
    live_smoke += """
  decoy:
    if: >-
      github.ref == format('refs/heads/{0}', github.event.repository.default_branch) &&
      vars.LIVE_SMOKE_ENABLED == 'true'
    runs-on: ubuntu-latest
"""
    with pytest.raises(RuntimeError, match="every trigger"):
        check_publish_workflow(
            PUBLISH_WORKFLOW.read_text(encoding="utf-8"),
            live_smoke,
        )


@pytest.mark.parametrize(
    ("needle", "replacement", "message"),
    [
        (
            "permissions:\n  contents: read",
            "permissions:\n  contents: write",
            "permissions",
        ),
        (
            "run: uv run pytest -m live --maxfail=1 -q",
            "continue-on-error: true\n        run: uv run pytest -m live --maxfail=1 -q",
            "must not allow failure",
        ),
        (
            "on:\n  schedule:",
            "on:\n  push:\n    branches: [main]\n  schedule:",
            "only on schedule or manual dispatch",
        ),
        ("runs-on: ubuntu-latest", "runs-on: self-hosted", "GitHub-hosted runner"),
    ],
    ids=["write-token", "continued-test", "extra-trigger", "self-hosted-runner"],
)
def test_semantic_contract_rejects_monitoring_live_bypasses(
    needle: str, replacement: str, message: str
) -> None:
    live_smoke = LIVE_SMOKE_WORKFLOW.read_text(encoding="utf-8").replace(needle, replacement, 1)
    with pytest.raises(RuntimeError, match=message):
        check_publish_workflow(
            PUBLISH_WORKFLOW.read_text(encoding="utf-8"),
            live_smoke,
        )


@pytest.mark.parametrize(
    ("needle", "replacement"),
    [
        (
            "        run: bash scripts/verify_release_trust.sh",
            "        working-directory: decoy\n        run: bash scripts/verify_release_trust.sh",
        ),
        (
            "        run: uv run pytest -m live --maxfail=1 -q",
            "        working-directory: decoy\n        run: uv run pytest -m live --maxfail=1 -q",
        ),
        (
            "        run: >-\n          python scripts/check_registry_release.py",
            "        working-directory: decoy\n"
            "        run: >-\n"
            "          python scripts/check_registry_release.py",
        ),
    ],
    ids=["release-trust", "exact-release-live", "registry-provenance"],
)
def test_semantic_contract_rejects_release_working_directory_redirects(
    needle: str, replacement: str
) -> None:
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    assert needle in text
    with pytest.raises(RuntimeError, match="repository root"):
        check_publish_workflow(
            text.replace(needle, replacement, 1),
            LIVE_SMOKE_WORKFLOW.read_text(encoding="utf-8"),
        )


def test_semantic_contract_rejects_monitoring_working_directory_redirect() -> None:
    live_smoke = LIVE_SMOKE_WORKFLOW.read_text(encoding="utf-8").replace(
        "        run: uv run pytest -m live --maxfail=1 -q",
        "        working-directory: decoy\n        run: uv run pytest -m live --maxfail=1 -q",
        1,
    )
    with pytest.raises(RuntimeError, match="repository root"):
        check_publish_workflow(
            PUBLISH_WORKFLOW.read_text(encoding="utf-8"),
            live_smoke,
        )


@pytest.mark.parametrize(
    ("needle", "replacement"),
    [
        (
            "  build:\n    name:",
            "  build:\n    container: attacker/image:latest\n    name:",
        ),
        (
            "  release-live-smoke:\n    name:",
            "  release-live-smoke:\n"
            "    strategy:\n"
            "      matrix:\n"
            "        copy: [one, two]\n"
            "    name:",
        ),
        (
            "  publish:\n    name:",
            "  publish:\n    strategy:\n      matrix:\n        copy: [one, two]\n    name:",
        ),
        (
            "  verify-registry:\n    name:",
            "  verify-registry:\n"
            "    services:\n"
            "      unreviewed:\n"
            "        image: attacker/image:latest\n"
            "    name:",
        ),
    ],
    ids=["build-container", "live-matrix", "publish-matrix", "registry-service"],
)
def test_semantic_contract_rejects_unreviewed_release_job_controls(
    needle: str, replacement: str
) -> None:
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    assert needle in text
    with pytest.raises(RuntimeError, match="reviewed contract"):
        check_publish_workflow(
            text.replace(needle, replacement, 1),
            LIVE_SMOKE_WORKFLOW.read_text(encoding="utf-8"),
        )


@pytest.mark.parametrize(
    "control",
    [
        "    container: attacker/image:latest\n",
        "    strategy:\n      matrix:\n        copy: [one, two]\n",
        "    services:\n      unreviewed:\n        image: attacker/image:latest\n",
    ],
    ids=["container", "matrix", "service"],
)
def test_semantic_contract_rejects_unreviewed_monitoring_job_controls(control: str) -> None:
    live_smoke = LIVE_SMOKE_WORKFLOW.read_text(encoding="utf-8").replace(
        "  smoke:\n    name:",
        f"  smoke:\n{control}    name:",
        1,
    )
    with pytest.raises(RuntimeError, match="reviewed contract"):
        check_publish_workflow(
            PUBLISH_WORKFLOW.read_text(encoding="utf-8"),
            live_smoke,
        )


def test_current_release_please_workflow_is_disabled_by_default() -> None:
    check_release_please_workflow(RELEASE_PLEASE_WORKFLOW.read_text(encoding="utf-8"))


def test_current_release_recovery_workflow_is_disabled_by_default() -> None:
    check_release_recovery_workflow(RELEASE_RECOVERY_WORKFLOW.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("needle", "replacement", "message"),
    [
        (
            "github.run_attempt == 1 &&",
            "github.run_attempt >= 1 &&",
            "first workflow attempt",
        ),
        (
            "github.ref == format('refs/heads/{0}', github.event.repository.default_branch)",
            "github.event_name == 'workflow_dispatch'",
            "protected default branch",
        ),
        (
            "vars.RELEASE_RECOVERY_TAG == inputs.release-tag",
            "inputs.release-tag != ''",
            "exact authorized release tag",
        ),
        (
            "vars.RELEASE_RECOVERY_SHA == inputs.release-sha",
            "inputs.release-sha != ''",
            "exact authorized release tag and commit",
        ),
        (
            "    if: github.run_attempt == 1\n    permissions:",
            "    if: always()\n    permissions:",
            "first workflow attempt",
        ),
        (
            "release-tag: ${{ needs.verify-recovery.outputs.release-tag }}",
            "release-tag: ${{ inputs.release-tag }}",
            "verified outputs",
        ),
        (
            "secrets: inherit",
            "secrets:\n      COMETAPI_KEY: ${{ secrets.COMETAPI_KEY }}",
            "inherit environment secrets",
        ),
        (
            'test "$(jq -r .immutable <<<"$release")" = "true"',
            'test -n "$release"',
            "run exactly",
        ),
    ],
    ids=[
        "rerun-verification",
        "arbitrary-branch",
        "unbound-tag",
        "unbound-sha",
        "rerun-publication",
        "unverified-input",
        "explicit-secret",
        "immutable-release-bypass",
    ],
)
def test_release_recovery_rejects_trust_bypasses(
    needle: str, replacement: str, message: str
) -> None:
    text = RELEASE_RECOVERY_WORKFLOW.read_text(encoding="utf-8")
    assert needle in text
    with pytest.raises(RuntimeError, match=message):
        check_release_recovery_workflow(text.replace(needle, replacement, 1))


def test_release_please_publish_caller_requires_secret_inheritance() -> None:
    text = RELEASE_PLEASE_WORKFLOW.read_text(encoding="utf-8").replace(
        "    secrets: inherit\n",
        "    secrets:\n      COMETAPI_KEY: ${{ secrets.COMETAPI_KEY }}\n",
        1,
    )
    with pytest.raises(RuntimeError, match="inherit environment secrets"):
        check_release_please_workflow(text)


def test_current_release_please_config_has_reviewed_stable_cleanup() -> None:
    check_release_please_config(
        RELEASE_PLEASE_CONFIG.read_text(encoding="utf-8"),
        RELEASE_PLEASE_MANIFEST.read_text(encoding="utf-8"),
    )


def test_release_please_config_accepts_reviewed_stable_bridge() -> None:
    check_release_please_config(
        _reviewed_release_please_bridge_config(),
        '{".": "0.1.0-alpha.1"}\n',
    )


@pytest.mark.parametrize(
    ("needle", "replacement", "message"),
    [
        (
            '"31b68904141489ca04932edbf305ccf88af09372"',
            '"f39b4dc9f2e18e91ab3cbac202246f85658f71fd"',
            "recovery alpha commit",
        ),
        ('"prerelease": false', '"prerelease": true', "prerelease-to-stable"),
        ('"versioning": "prerelease"', '"versioning": "default"', "prerelease-to-stable"),
        ('"path": "uv.lock"', '"path": "pyproject.toml"', "uv.lock"),
        (
            "$.package[?(@.name.value == 'cometapi')].version",
            "$.package[0].version",
            "uv.lock",
        ),
    ],
    ids=["wrong-boundary", "prerelease", "versioning", "wrong-path", "wrong-jsonpath"],
)
def test_release_please_config_rejects_bridge_drift(
    needle: str, replacement: str, message: str
) -> None:
    text = _reviewed_release_please_bridge_config()
    assert needle in text
    with pytest.raises(RuntimeError, match=message):
        check_release_please_config(
            text.replace(needle, replacement, 1),
            '{".": "0.1.0-alpha.1"}\n',
        )


def test_release_please_config_rejects_alpha_type_and_extra_updaters() -> None:
    text = RELEASE_PLEASE_CONFIG.read_text(encoding="utf-8").replace(
        '"package-name": "cometapi",',
        '"package-name": "cometapi",\n      "prerelease-type": "alpha",',
        1,
    )
    with pytest.raises(RuntimeError, match="reviewed contract"):
        check_release_please_config(
            text,
            RELEASE_PLEASE_MANIFEST.read_text(encoding="utf-8"),
        )


def test_release_please_config_rejects_manifest_drift() -> None:
    with pytest.raises(RuntimeError, match="reviewed bridge or stable version"):
        check_release_please_config(
            RELEASE_PLEASE_CONFIG.read_text(encoding="utf-8"),
            '{".": "0.1.0-alpha.2"}\n',
        )


def test_release_please_config_accepts_exact_stable_cleanup() -> None:
    check_release_please_config(
        RELEASE_PLEASE_CONFIG.read_text(encoding="utf-8"),
        '{".": "0.1.0"}\n',
    )


def test_release_please_config_rejects_stable_manifest_with_bridge() -> None:
    with pytest.raises(RuntimeError, match="remove the one-time bridge"):
        check_release_please_config(
            _reviewed_release_please_bridge_config(),
            '{".": "0.1.0"}\n',
        )


def test_release_please_config_rejects_bridge_cleanup_before_stable() -> None:
    with pytest.raises(RuntimeError, match="only after stable"):
        check_release_please_config(
            RELEASE_PLEASE_CONFIG.read_text(encoding="utf-8"),
            '{".": "0.1.0-alpha.1"}\n',
        )


@pytest.mark.parametrize(
    "replacement",
    [
        "if: vars.RELEASE_PLEASE_ENABLED != 'false'",
        "if: github.ref == 'refs/heads/main'",
    ],
)
def test_release_please_requires_exact_enable_opt_in(replacement: str) -> None:
    text = RELEASE_PLEASE_WORKFLOW.read_text(encoding="utf-8").replace(
        "if: vars.RELEASE_PLEASE_ENABLED == 'true'",
        replacement,
        1,
    )
    with pytest.raises(RuntimeError, match="RELEASE_PLEASE_ENABLED=true"):
        check_release_please_workflow(text)


def test_release_please_checks_opt_in_on_real_job() -> None:
    text = RELEASE_PLEASE_WORKFLOW.read_text(encoding="utf-8").replace(
        "if: vars.RELEASE_PLEASE_ENABLED == 'true'",
        "if: github.ref == 'refs/heads/main'",
        1,
    )
    text = text.replace(
        "    steps:\n",
        "    steps:\n"
        "      - name: Decoy condition text\n"
        "        run: >-\n"
        "          echo \"if: vars.RELEASE_PLEASE_ENABLED == 'true'\"\n",
        1,
    )
    with pytest.raises(RuntimeError, match="RELEASE_PLEASE_ENABLED=true"):
        check_release_please_workflow(text)


def test_release_please_rejects_an_additional_ungated_job() -> None:
    text = (
        RELEASE_PLEASE_WORKFLOW.read_text(encoding="utf-8")
        + """
  decoy:
    runs-on: ubuntu-latest
    steps:
      - run: echo bypass
"""
    )
    with pytest.raises(RuntimeError, match="only its gated"):
        check_release_please_workflow(text)


def test_release_please_rejects_trigger_text_hidden_in_name() -> None:
    text = RELEASE_PLEASE_WORKFLOW.read_text(encoding="utf-8").replace(
        "name: Release Please",
        "name: |\n  push:\n    branches:\n      - main",
        1,
    )
    text = text.replace(
        "on:\n  push:\n    branches:\n      - main",
        'on:\n  schedule:\n    - cron: "0 0 * * *"',
        1,
    )
    with pytest.raises(RuntimeError, match="default-branch pushes"):
        check_release_please_workflow(text)


@pytest.mark.parametrize(
    ("needle", "replacement"),
    [
        (
            "    branches:\n      - main",
            "    branches:\n      - main\n    paths:\n      - src/**",
        ),
        (
            "uses: googleapis/release-please-action@",
            "uses: attacker/example-action@",
        ),
        (
            "config-file: release-please-config.json",
            "config-file: attacker-config.json",
        ),
        (
            "manifest-file: .release-please-manifest.json",
            "manifest-file: attacker-manifest.json",
        ),
    ],
    ids=["path-filter", "arbitrary-action", "config-decoy", "manifest-decoy"],
)
def test_release_please_rejects_structural_bypasses(needle: str, replacement: str) -> None:
    text = RELEASE_PLEASE_WORKFLOW.read_text(encoding="utf-8")
    assert needle in text
    with pytest.raises(RuntimeError):
        check_release_please_workflow(text.replace(needle, replacement, 1))


def test_release_please_rejects_extra_privileged_step() -> None:
    text = RELEASE_PLEASE_WORKFLOW.read_text(encoding="utf-8").replace(
        "    steps:\n",
        "    steps:\n"
        "      - name: Unreviewed token consumer\n"
        '        run: echo "${{ github.token }}"\n',
        1,
    )
    with pytest.raises(RuntimeError, match="reviewed sequence"):
        check_release_please_workflow(text)


@pytest.mark.parametrize(
    "control",
    [
        "    container: attacker/image:latest\n",
        "    strategy:\n      matrix:\n        copy: [one, two]\n",
        "    services:\n      unreviewed:\n        image: attacker/image:latest\n",
    ],
    ids=["container", "matrix", "service"],
)
def test_release_please_rejects_unreviewed_job_controls(control: str) -> None:
    text = RELEASE_PLEASE_WORKFLOW.read_text(encoding="utf-8").replace(
        "  release-please:\n    name:",
        f"  release-please:\n{control}    name:",
        1,
    )
    with pytest.raises(RuntimeError, match="reviewed contract"):
        check_release_please_workflow(text)


def test_current_ci_workflow_covers_private_remote_validation() -> None:
    check_ci_workflow(CI_WORKFLOW.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("needle", "replacement", "message"),
    [
        (
            "      - name: Check out the candidate\n",
            "      - name: Check out the candidate\n        with:\n          ref: main\n",
            "triggering candidate",
        ),
        (
            "      - name: Run offline unit and contract tests\n"
            '        run: uv run pytest -m "not live"',
            "      - name: Run offline unit and contract tests\n"
            "        working-directory: decoy\n"
            '        run: uv run pytest -m "not live"',
            "repository root",
        ),
        (
            "  quality:\n    name:",
            "  quality:\n    container: attacker/image:latest\n    name:",
            "reviewed contract",
        ),
        (
            "  quality:\n    name:",
            "  quality:\n"
            "    services:\n"
            "      unreviewed:\n"
            "        image: attacker/image:latest\n"
            "    name:",
            "reviewed contract",
        ),
        (
            "  quality:\n    name:",
            "  quality:\n    strategy:\n      matrix:\n        copy: [one, two]\n    name:",
            "reviewed contract",
        ),
        (
            "    steps:\n      - name: Check out the candidate",
            "    steps:\n"
            "      - name: Unreviewed action\n"
            "        uses: attacker/example-action@"
            "0123456789abcdef0123456789abcdef01234567\n"
            "      - name: Check out the candidate",
            "reviewed sequence",
        ),
    ],
    ids=[
        "checkout-ref",
        "working-directory",
        "container",
        "service",
        "matrix",
        "extra-action",
    ],
)
def test_ci_contract_rejects_candidate_execution_redirects(
    needle: str, replacement: str, message: str
) -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert needle in text
    with pytest.raises(RuntimeError, match=message):
        check_ci_workflow(text.replace(needle, replacement, 1))


def test_ci_contract_rejects_extra_skip_dependency_job() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8").replace(
        "  quality:\n",
        "  skip-gate:\n"
        "    name: Skip required evidence\n"
        "    if: github.event_name == 'never'\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: true\n\n"
        "  quality:\n"
        "    needs: skip-gate\n",
        1,
    )
    with pytest.raises(RuntimeError, match="reviewed validation chain"):
        check_ci_workflow(text)


@pytest.mark.parametrize(
    "needle",
    [
        "      - name: Check lock consistency\n        run: uv lock --check\n",
        "      - name: Check canonical public content and identity\n"
        "        run: uv run python scripts/check_version.py --require-public-preview-docs\n",
        "      - name: Verify from a copied standalone repository\n"
        "        run: python scripts/check_repository_independence.py\n",
        "      - name: Recheck retained artifact digests\n"
        "        working-directory: verified-artifacts\n"
        "        run: sha256sum --check artifact-sha256.txt\n",
    ],
    ids=["lock", "public-content", "standalone", "artifact-round-trip"],
)
def test_ci_contract_rejects_missing_private_validation_gate(needle: str) -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8").replace(needle, "", 1)
    with pytest.raises(RuntimeError):
        check_ci_workflow(text)


def test_ci_contract_rejects_commented_public_content_decoy() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8").replace(
        "      - name: Check canonical public content and identity\n"
        "        run: uv run python scripts/check_version.py --require-public-preview-docs\n",
        "      # run: uv run python scripts/check_version.py --require-public-preview-docs\n",
        1,
    )
    with pytest.raises(RuntimeError, match="public-preview-docs"):
        check_ci_workflow(text)


@pytest.mark.parametrize(
    ("needle", "replacement", "message"),
    [
        (
            "permissions:\n  contents: read",
            "permissions:\n  contents: write",
            "permissions",
        ),
        ("  package:\n", "  package:\n    if: github.event_name == 'never'\n", "conditional"),
        ("  quality:\n", "  quality:\n    continue-on-error: true\n", "allow failure"),
        ("run: uv lock --check", "run: uv lock --check || true", "active run step"),
        (
            "run: uv lock --check",
            "run: uv lock --check\n        shell: bash -c '{0} || true'",
            "command shell",
        ),
    ],
    ids=["write-token", "conditional-package", "continued-quality", "shell-or", "step-shell"],
)
def test_ci_contract_rejects_blocking_bypasses(needle: str, replacement: str, message: str) -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8").replace(needle, replacement, 1)
    with pytest.raises(RuntimeError, match=message):
        check_ci_workflow(text)


def test_ci_contract_rejects_workflow_shell_override() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8").replace(
        "\njobs:\n",
        "\ndefaults:\n  run:\n    shell: bash -c '{0} || true'\n\njobs:\n",
        1,
    )
    with pytest.raises(RuntimeError, match="command defaults"):
        check_ci_workflow(text)


def test_ci_contract_rejects_trigger_text_hidden_in_name() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8").replace(
        "name: CI",
        "name: |\n  pull_request:\n  push:\n    branches:\n      - main",
        1,
    )
    text = text.replace(
        "on:\n  pull_request:\n  push:\n    branches:\n      - main\n  schedule:",
        "on:\n  schedule:",
        1,
    )
    with pytest.raises(RuntimeError, match="pull requests"):
        check_ci_workflow(text)


@pytest.mark.parametrize(
    ("needle", "replacement"),
    [
        (
            "  pull_request:\n",
            "  pull_request:\n    paths:\n      - src/**\n",
        ),
        (
            "    branches:\n      - main\n  schedule:",
            "    branches:\n      - main\n    paths:\n      - src/**\n  schedule:",
        ),
        ('    - cron: "23 4 * * 1"', '    - cron: "23 4 * * 2"'),
        (
            "if: github.event_name == 'schedule' || github.actor == 'dependabot[bot]'",
            "if: github.event_name == 'never'",
        ),
        (
            'uv pip install --python .venv/bin/python --upgrade "openai>=2.45.0,<3.0.0"',
            'uv pip install --python .venv/bin/python "openai==2.45.0"',
        ),
        (
            'run: uv run --no-sync pytest -m "not live"',
            'run: uv run --no-sync pytest -m "not live" --collect-only',
        ),
        (
            "python-version: ${{ matrix.python-version }}",
            'python-version: "3.14"',
        ),
        ("runs-on: ubuntu-latest", "runs-on: self-hosted"),
        (
            "  UV_VERSION: 0.11.8",
            "  UV_VERSION: 0.11.8\n  PYTEST_ADDOPTS: --collect-only",
        ),
        (
            "run: uv run python scripts/check_clean_install.py dist/*",
            "run: uv run python scripts/check_clean_install.py dist/* | true",
        ),
    ],
    ids=[
        "pull-request-path-filter",
        "push-path-filter",
        "weekly-schedule-change",
        "latest-canary-condition",
        "latest-openai-no-upgrade",
        "canary-collect-only",
        "runtime-matrix-decoy",
        "self-hosted-runner",
        "workflow-pytest-addopts",
        "package-clean-install-pipe",
    ],
)
def test_ci_contract_rejects_structural_bypasses(needle: str, replacement: str) -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert needle in text
    with pytest.raises(RuntimeError):
        check_ci_workflow(text.replace(needle, replacement, 1))


@pytest.mark.parametrize(
    ("needle", "replacement"),
    [
        (
            "  quality:\n    name:",
            "  quality:\n    env:\n      PYTEST_ADDOPTS: --collect-only\n    name:",
        ),
        (
            '        run: uv run pytest -m "not live"',
            "        env:\n"
            "          PYTEST_ADDOPTS: --collect-only\n"
            '        run: uv run pytest -m "not live"',
        ),
    ],
    ids=["job-environment", "step-environment"],
)
def test_ci_contract_rejects_test_environment_bypasses(needle: str, replacement: str) -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert needle in text
    with pytest.raises(RuntimeError, match="environment"):
        check_ci_workflow(text.replace(needle, replacement, 1))


def test_ci_contract_rejects_bare_secrets_context() -> None:
    text = (
        CI_WORKFLOW.read_text(encoding="utf-8")
        + """
  secret-context-decoy:
    runs-on: ubuntu-latest
    steps:
      - run: echo "${{ toJSON(secrets) }}"
"""
    )
    with pytest.raises(RuntimeError, match="secrets"):
        check_ci_workflow(text)


def test_ci_contract_keeps_downloaded_artifacts_out_of_copied_candidate() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    copied_start, copied_end = _step(text, "Verify from a copied standalone repository")
    download_start, download_end = _step(text, "Download the verified package artifacts")
    copied_block = text[copied_start:copied_end]
    download_block = text[download_start:download_end]
    text = (
        text[:copied_start]
        + download_block
        + text[copied_end:download_start]
        + copied_block
        + text[download_end:]
    )
    with pytest.raises(RuntimeError, match="copied-checkout verification before downloading"):
        check_ci_workflow(text)


def test_workflow_path_discovery_includes_yaml_and_yml(tmp_path: Path) -> None:
    (tmp_path / "first.yml").write_text("name: first\n", encoding="utf-8")
    (tmp_path / "second.yaml").write_text("name: second\n", encoding="utf-8")
    (tmp_path / "ignored.txt").write_text("ignored\n", encoding="utf-8")
    assert [path.name for path in workflow_paths(tmp_path)] == ["first.yml", "second.yaml"]


def test_workflow_inventory_rejects_unreviewed_workflow(tmp_path: Path) -> None:
    for name in (
        "ci.yml",
        "live-smoke.yml",
        "publish.yml",
        "release-please.yml",
        "release-recovery.yml",
    ):
        (tmp_path / name).write_text("name: reviewed\n", encoding="utf-8")
    assert {path.name for path in check_workflow_inventory(tmp_path)} == {
        "ci.yml",
        "live-smoke.yml",
        "publish.yml",
        "release-please.yml",
        "release-recovery.yml",
    }

    (tmp_path / "rogue.yaml").write_text(
        "permissions:\n  id-token: write\njobs:\n  rogue:\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match=r"unexpected: rogue\.yaml"):
        check_workflow_inventory(tmp_path)


def test_workflow_inventory_rejects_expected_name_symlink(tmp_path: Path) -> None:
    workflow_root = tmp_path / "workflows"
    workflow_root.mkdir()
    for name in (
        "live-smoke.yml",
        "publish.yml",
        "release-please.yml",
        "release-recovery.yml",
    ):
        (workflow_root / name).write_text("name: reviewed\n", encoding="utf-8")
    outside = tmp_path / "outside-ci.yml"
    outside.write_text("name: outside\n", encoding="utf-8")
    (workflow_root / "ci.yml").symlink_to(outside)

    with pytest.raises(RuntimeError, match="regular, non-symlink files"):
        check_workflow_inventory(workflow_root)


@pytest.mark.parametrize("linked_component", ["github", "workflows"])
def test_workflow_inventory_rejects_linked_directory(tmp_path: Path, linked_component: str) -> None:
    outside = tmp_path / "outside"
    outside_workflows = outside / "workflows"
    outside_workflows.mkdir(parents=True)
    for name in (
        "ci.yml",
        "live-smoke.yml",
        "publish.yml",
        "release-please.yml",
        "release-recovery.yml",
    ):
        (outside_workflows / name).write_text("name: outside\n", encoding="utf-8")

    repository = tmp_path / "repository"
    repository.mkdir()
    github = repository / ".github"
    if linked_component == "github":
        github.symlink_to(outside, target_is_directory=True)
    else:
        github.mkdir()
        (github / "workflows").symlink_to(outside_workflows, target_is_directory=True)

    with pytest.raises(RuntimeError, match="real repository directories"):
        check_workflow_inventory(github / "workflows")


def test_secret_scope_scan_includes_yaml_workflows(tmp_path: Path) -> None:
    workflow_root = tmp_path / ".github/workflows"
    workflow_root.mkdir(parents=True)
    (workflow_root / "rogue.yaml").write_text(
        "permissions:\n  id-token: write\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts/check_secrets.py"),
            "--root",
            str(tmp_path),
        ],
        text=True,
        check=False,
        capture_output=True,
    )
    assert result.returncode != 0
    assert (
        ".github/workflows/rogue.yaml: id-token: write must match the reviewed "
        "publication chain count (0)"
    ) in result.stderr


def test_semantic_contract_rejects_download_before_checkout() -> None:
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    checkout_start, checkout_end = _step(text, "Check out the registry verification source")
    download_start, download_end = _step(
        text, "Download the verified release bundle after checkout"
    )
    checkout_block = text[checkout_start:checkout_end]
    download_block = text[download_start:download_end]
    mutated = text[:checkout_start] + download_block + checkout_block + text[download_end:]
    with pytest.raises(RuntimeError, match="check out source before downloading"):
        check_publish_workflow(
            mutated,
            LIVE_SMOKE_WORKFLOW.read_text(encoding="utf-8"),
        )


def test_release_trust_accepts_exact_immutable_default_branch_commit(
    release_repository: tuple[Path, str], tmp_path: Path
) -> None:
    repository, release_commit = release_repository
    result = _verify_trust(repository, tmp_path)

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "github-output.txt").read_text(encoding="utf-8") == (
        f"release-commit={release_commit}\n"
    )


def test_release_trust_accepts_approved_recovery_tag(
    release_repository: tuple[Path, str], tmp_path: Path
) -> None:
    repository, release_commit = release_repository
    recovery_tag = "v0.1.0-alpha.1+recovery.1"
    _git(repository, "tag", recovery_tag, release_commit)
    _git(repository, "checkout", "--detach", recovery_tag)
    result = _verify_trust(repository, tmp_path, tag=recovery_tag)

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "github-output.txt").read_text(encoding="utf-8") == (
        f"release-commit={release_commit}\n"
    )


def test_release_trust_rejects_non_immutable_release(
    release_repository: tuple[Path, str], tmp_path: Path
) -> None:
    repository, _release_commit = release_repository
    result = _verify_trust(repository, tmp_path, immutable="false")

    assert result.returncode != 0
    assert "immutable=true" in result.stderr


def test_release_trust_rejects_release_sha_that_differs_from_tag(
    release_repository: tuple[Path, str], tmp_path: Path
) -> None:
    repository, _release_commit = release_repository
    result = _verify_trust(repository, tmp_path, expected_release_sha="0" * 40)

    assert result.returncode != 0
    assert "expected 0000000000000000000000000000000000000000" in result.stderr


def test_release_trust_rejects_checkout_that_differs_from_tag(
    release_repository: tuple[Path, str], tmp_path: Path
) -> None:
    repository, _release_commit = release_repository
    _git(repository, "checkout", "main")
    (repository / "tracked.txt").write_text("new head\n", encoding="utf-8")
    _git(repository, "commit", "-am", "new head")
    result = _verify_trust(repository, tmp_path)

    assert result.returncode != 0
    assert "does not match" in result.stderr


def test_release_trust_rejects_unmerged_branch_commit(
    release_repository: tuple[Path, str], tmp_path: Path
) -> None:
    repository, _release_commit = release_repository
    _git(repository, "checkout", "main")
    _git(repository, "checkout", "-b", "release-from-feature")
    (repository / "tracked.txt").write_text("feature release\n", encoding="utf-8")
    _git(repository, "commit", "-am", "feature release")
    _git(repository, "tag", "v0.1.0-alpha.2")
    _git(repository, "checkout", "--detach", "v0.1.0-alpha.2")
    result = _verify_trust(repository, tmp_path, tag="v0.1.0-alpha.2")

    assert result.returncode != 0
    assert "not reachable from origin/main" in result.stderr


def test_release_trust_rejects_unrelated_commit(
    release_repository: tuple[Path, str], tmp_path: Path
) -> None:
    repository, _release_commit = release_repository
    tree = _git(repository, "mktree", input_text="")
    unrelated_commit = _git(repository, "commit-tree", tree, "-m", "unrelated release")
    _git(repository, "tag", "v0.1.0-alpha.2", unrelated_commit)
    _git(repository, "checkout", "--detach", unrelated_commit)
    result = _verify_trust(repository, tmp_path, tag="v0.1.0-alpha.2")

    assert result.returncode != 0
    assert "not reachable from origin/main" in result.stderr
