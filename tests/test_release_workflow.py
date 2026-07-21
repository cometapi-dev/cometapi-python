from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts.check_workflows import (
    check_action_pins,
    check_ci_workflow,
    check_publish_workflow,
    check_release_please_workflow,
)
from tests.live.test_live_smoke import resolve_live_model

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
PUBLISH_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "publish.yml"
LIVE_SMOKE_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "live-smoke.yml"
RELEASE_PLEASE_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "release-please.yml"
TRUST_SCRIPT = PROJECT_ROOT / "scripts" / "verify_release_trust.sh"


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
) -> subprocess.CompletedProcess[str]:
    output = tmp_path / "github-output.txt"
    environment = os.environ.copy()
    environment.update(
        {
            "DEFAULT_BRANCH": "main",
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
        "RELEASE_IMMUTABLE: ${{ github.event.release.immutable }}",
        'RELEASE_IMMUTABLE: "true"',
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
    text = CI_WORKFLOW.read_text(encoding="utf-8").replace(
        "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
        "actions/checkout@v4",
        1,
    )
    with pytest.raises(RuntimeError, match="full commit SHA"):
        check_action_pins(text, CI_WORKFLOW.name)


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


def test_current_release_please_workflow_is_disabled_by_default() -> None:
    check_release_please_workflow(RELEASE_PLEASE_WORKFLOW.read_text(encoding="utf-8"))


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


def test_current_ci_workflow_covers_private_remote_validation() -> None:
    check_ci_workflow(CI_WORKFLOW.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "needle",
    [
        "      - name: Check lock consistency\n        run: uv lock --check\n",
        "      - name: Check canonical public content and identity\n"
        "        run: uv run python scripts/check_version.py --require-public-preview-docs\n",
        "      - name: Verify from a copied standalone repository\n"
        "        run: python scripts/check_repository_independence.py\n",
    ],
    ids=["lock", "public-content", "standalone"],
)
def test_ci_contract_rejects_missing_private_validation_gate(needle: str) -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8").replace(needle, "", 1)
    with pytest.raises(RuntimeError):
        check_ci_workflow(text)


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


def test_release_trust_rejects_non_immutable_release(
    release_repository: tuple[Path, str], tmp_path: Path
) -> None:
    repository, _release_commit = release_repository
    result = _verify_trust(repository, tmp_path, immutable="false")

    assert result.returncode != 0
    assert "immutable=true" in result.stderr


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
