from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts import check_repository_independence
from scripts._checks import (
    CANONICAL_AUTHOR,
    CANONICAL_COPYRIGHT,
    CANONICAL_PROJECT_URLS,
    CANONICAL_SECURITY,
    CANONICAL_SUPPORT,
    EXACT_RELEASE_VERSION_FIX,
    PUBLIC_README_INSTALL_COMMAND,
    CheckError,
    exact_release_version_violations,
    read_project_version,
)
from scripts.check_artifacts import check_metadata, check_sdist, check_wheel
from scripts.check_version import require_public_preview_docs, require_releasable_docs

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSION_SCRIPT = PROJECT_ROOT / "scripts" / "check_version.py"


def _copy_version_checker(root: Path) -> Path:
    scripts = root / "scripts"
    scripts.mkdir(exist_ok=True)
    for name in ("_checks.py", "check_version.py"):
        shutil.copy2(PROJECT_ROOT / "scripts" / name, scripts / name)
    return scripts / "check_version.py"


def _write_release_documents(root: Path) -> None:
    files = {
        "pyproject.toml": f'''\
[project]
name = "cometapi"
version = "0.1.0a1"
authors = [{{ name = "{CANONICAL_AUTHOR}" }}]

[project.urls]
Homepage = "{CANONICAL_PROJECT_URLS["Homepage"]}"
Documentation = "{CANONICAL_PROJECT_URLS["Documentation"]}"
Repository = "{CANONICAL_PROJECT_URLS["Repository"]}"
Issues = "{CANONICAL_PROJECT_URLS["Issues"]}"
Support = "{CANONICAL_PROJECT_URLS["Support"]}"
Security = "{CANONICAL_PROJECT_URLS["Security"]}"
''',
        ".release-please-manifest.json": '{".": "0.1.0-alpha.1"}\n',
        "LICENSE": f"{CANONICAL_COPYRIGHT}\n",
        "README.md": (
            f"Stable 0.1.x maintenance releases are available from PyPI.\n"
            f"{PUBLIC_README_INSTALL_COMMAND}\n"
            + "\n".join(CANONICAL_PROJECT_URLS.values())
            + f"\n{CANONICAL_SUPPORT}\n"
        ),
        "CHANGELOG.md": """\
# Changelog

## [0.1.0a1] - 2026-07-17

Initial alpha release.
""",
        "SECURITY.md": f"Report at {CANONICAL_SECURITY} or {CANONICAL_SUPPORT}.\n",
        "SUPPORT.md": (
            f"Use {CANONICAL_PROJECT_URLS['Issues']} or {CANONICAL_SUPPORT} for support.\n"
        ),
        "CODE_OF_CONDUCT.md": f"Report privately to {CANONICAL_SUPPORT}.\n",
        "ROADMAP.md": "# Roadmap\n\n## 0.1\n",
        "AGENTS.md": "# Engineering contract\n",
        "RELEASING.md": "# Releasing\n",
        "COMPATIBILITY.md": "# Compatibility\n",
        "ARCHITECTURE.md": "# Architecture\n",
        "CONTRIBUTING.md": "# Contributing\n",
        "CLAUDE.md": "@AGENTS.md.\n",
        ".github/PULL_REQUEST_TEMPLATE.md": "# Pull request\n",
        ".github/ISSUE_TEMPLATE/bug_report.yml": "name: Bug report\n",
        ".github/ISSUE_TEMPLATE/config.yml": "blank_issues_enabled: false\n",
        ".github/ISSUE_TEMPLATE/feature_request.yml": "name: Feature request\n",
    }
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _replace(root: Path, name: str, old: str, new: str) -> None:
    path = root / name
    path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")


def _change_author(root: Path) -> None:
    _replace(root, "pyproject.toml", CANONICAL_AUTHOR, "Another Author")


def _change_repository_url(root: Path) -> None:
    _replace(
        root,
        "pyproject.toml",
        CANONICAL_PROJECT_URLS["Repository"],
        "https://github.com/another-owner/another-repository",
    )


def _change_copyright(root: Path) -> None:
    (root / "LICENSE").write_text("Copyright (c) 2026 Another Author\n", encoding="utf-8")


def _change_security_contact(root: Path) -> None:
    _replace(root, "SECURITY.md", CANONICAL_SECURITY, "security@example.invalid")


def _change_support_contact(root: Path) -> None:
    _replace(root, "SUPPORT.md", CANONICAL_SUPPORT, "support@example.invalid")


def _change_conduct_contact(root: Path) -> None:
    _replace(root, "CODE_OF_CONDUCT.md", CANONICAL_SUPPORT, "conduct@example.invalid")


def _artifact_metadata(description: str) -> bytes:
    headers = [
        "Metadata-Version: 2.4",
        "Name: cometapi",
        "Version: 0.1.0a1",
        f"Author: {CANONICAL_AUTHOR}",
        "Requires-Dist: openai<3.0.0,>=2.45.0",
        "Description-Content-Type: text/markdown",
    ]
    headers.extend(f"Project-URL: {label}, {url}" for label, url in CANONICAL_PROJECT_URLS.items())
    return ("\n".join(headers) + "\n\n" + description + "\n").encode()


EVIDENCE_IDENTITY = (
    "<!-- cometapi-release-identity tag=v0.1.2 "
    "commit=710c56491d9ef5f47cccff3ce837ab7e799455b0 "
    "workflow-run=30515861246 "
    "wheel-sha256=3f12c26ae1ae7a1de5ac19d8ef27a784b2bf592143c716493f1b0f35ec19daca "
    "sdist-sha256=21c8edc0586610de1a9a8cd39b54ed23d2b1e20552100f69f53938cb7678da3d -->"
)


def _release_evidence_block() -> str:
    return f"""\
<!-- cometapi-release-evidence:start version=0.1.2 date=2026-07-30 -->
{EVIDENCE_IDENTITY}

## Completed 0.1.2 maintenance release evidence

- Release tag `v0.1.2` at release commit `710c56491d9ef5f47cccff3ce837ab7e799455b0`.
- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/30515861246
- https://pypi.org/project/cometapi/0.1.2/
- https://github.com/cometapi-dev/cometapi-python/releases/tag/v0.1.2
- Wheel SHA256: 3f12c26ae1ae7a1de5ac19d8ef27a784b2bf592143c716493f1b0f35ec19daca
- Source-distribution SHA256: 21c8edc0586610de1a9a8cd39b54ed23d2b1e20552100f69f53938cb7678da3d

<!-- cometapi-release-evidence:end version=0.1.2 date=2026-07-30 -->
"""


@pytest.fixture
def releasable_documents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _write_release_documents(tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_release_documents_accept_exact_canonical_identity(releasable_documents: Path) -> None:
    assert not (releasable_documents / ".github/CODEOWNERS").exists()
    require_releasable_docs("0.1.0a1")


def test_public_preview_documents_accept_durable_public_content(
    releasable_documents: Path,
) -> None:
    require_public_preview_docs()


@pytest.mark.parametrize(
    ("document", "claim"),
    [
        (
            "AGENTS.md",
            "`cometapi==0.1.2` is the latest publicly available maintenance release.",
        ),
        ("README.md", "The **current PyPI release** is\n`0.1.2`."),
        ("COMPATIBILITY.md", "LATEST stable version: **0.1.2**."),
        ("ARCHITECTURE.md", "`0.1.2` remains the current stable release."),
        ("ROADMAP.md", "Status: `0.1.2` stable maintenance released"),
        ("AGENTS.md", "Latest PyPI release: `0.1.2`."),
        ("README.md", "`0.1.2` is the latest PyPI release."),
        ("COMPATIBILITY.md", "PyPI currently publishes `0.1.2`."),
        ("ARCHITECTURE.md", "The currently published version is `0.1.2`."),
        ("CONTRIBUTING.md", "The version currently available from PyPI is `0.1.2`."),
        ("AGENTS.md", "Published version: `0.1.2`."),
        ("README.md", "CometAPI `0.1.2` is available from PyPI."),
        ("COMPATIBILITY.md", "Latest, stable distribution: `0.1.2`."),
        ("ARCHITECTURE.md", "PyPI currently has CometAPI `0.1.2`."),
        ("CONTRIBUTING.md", "The latest <strong>stable</strong> release is `0.1.2`."),
        (
            "AGENTS.md",
            "Historical evidence: immutable tag `v0.1.1`.\n\nCurrent PyPI release: `0.1.2`.",
        ),
        ("README.md", "| Current | `0.1.2` |"),
        (
            "README.md",
            "| Version | Status |\n| --- | --- |\n| `0.1.2` | Current |",
        ),
        (
            "README.md",
            "Current PyPI release: https://pypi.org/project/cometapi/0.1.2/",
        ),
        (
            "README.md",
            "The **latest stable version** is [`0.1.2`](https://example.invalid).",
        ),
        (
            ".github/ISSUE_TEMPLATE/feature_request.yml",
            "description: Current PyPI release is 0.1.2.",
        ),
        ("COMPATIBILITY.md", "| Status | Released | `0.1.2` |"),
        ("ARCHITECTURE.md", "The workflow was repaired, so PyPI publishes `0.1.2`."),
    ],
    ids=[
        "agents-old-claim",
        "readme-markdown-newline",
        "compatibility-case-markdown",
        "version-first-current-claim",
        "roadmap-status",
        "latest-pypi-release",
        "version-first-latest-pypi-release",
        "pypi-currently-publishes",
        "currently-published-version",
        "version-currently-available-from-pypi",
        "published-version",
        "cometapi-version-available-from-pypi",
        "punctuated-latest-distribution",
        "pypi-currently-has-cometapi",
        "html-latest-release",
        "prior-immutable-evidence-does-not-exempt-current-claim",
        "markdown-current-table",
        "markdown-version-first-current-table",
        "current-versioned-pypi-url",
        "markdown-linked-version-label",
        "issue-template-current-release",
        "markdown-released-table",
        "past-clause-does-not-exempt-current-publication",
    ],
)
def test_public_preview_cli_rejects_mutable_published_patch_claims(
    releasable_documents: Path,
    document: str,
    claim: str,
) -> None:
    version_script = _copy_version_checker(releasable_documents)
    with (releasable_documents / document).open("a", encoding="utf-8") as stream:
        stream.write(f"\n{claim}\n")

    result = subprocess.run(
        [sys.executable, str(version_script), "--require-public-preview-docs"],
        cwd=releasable_documents,
        text=True,
        check=False,
        capture_output=True,
    )

    assert result.returncode != 0
    assert f"{document}:" in result.stderr
    assert "exact CometAPI patch/recovery version" in result.stderr
    assert EXACT_RELEASE_VERSION_FIX in result.stderr


def test_releasable_cli_rejects_mutable_published_patch_claim(
    releasable_documents: Path,
) -> None:
    version_script = _copy_version_checker(releasable_documents)
    with (releasable_documents / "AGENTS.md").open("a", encoding="utf-8") as stream:
        stream.write("\n`cometapi==0.1.2` is the latest publicly available release.\n")

    result = subprocess.run(
        [sys.executable, str(version_script), "--require-releasable-docs"],
        cwd=releasable_documents,
        text=True,
        check=False,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "AGENTS.md:" in result.stderr
    assert (
        "exact CometAPI patch/recovery version outside immutable release evidence" in result.stderr
    )
    assert EXACT_RELEASE_VERSION_FIX in result.stderr


def test_public_preview_documents_allow_immutable_release_evidence(
    releasable_documents: Path,
) -> None:
    evidence = _release_evidence_block()
    for name in ("ROADMAP.md", "RELEASING.md"):
        with (releasable_documents / name).open("a", encoding="utf-8") as stream:
            stream.write(evidence)
    _replace(
        releasable_documents,
        "CHANGELOG.md",
        "# Changelog\n",
        "# Changelog\n\n## [0.1.2] - 2026-07-30\n\nImmutable history.\n",
    )

    require_public_preview_docs()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            "Source-distribution SHA256: "
            "21c8edc0586610de1a9a8cd39b54ed23d2b1e20552100f69f53938cb7678da3d",
            "missing exact source-distribution SHA256",
        ),
        (
            "<!-- cometapi-release-evidence:end version=0.1.3 date=2026-07-30 -->",
            "unpaired release-evidence end marker",
        ),
    ],
)
def test_public_preview_documents_reject_incomplete_or_unpaired_evidence(
    releasable_documents: Path,
    mutation: str,
    message: str,
) -> None:
    evidence = _release_evidence_block()
    if mutation and not mutation.startswith("<!--"):
        evidence = evidence.replace(mutation, "")
        mutation = ""
    with (releasable_documents / "ROADMAP.md").open("a", encoding="utf-8") as stream:
        stream.write(evidence + mutation)

    with pytest.raises(CheckError, match=message):
        require_public_preview_docs()


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("tag=v0.1.2", "tag=v0.1.9", "canonical tag v0.1.2"),
        (
            "commit=710c56491d9ef5f47cccff3ce837ab7e799455b0",
            "commit=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "missing exact release commit",
        ),
        ("workflow-run=30515861246", "workflow-run=999999", "missing exact release workflow"),
        (
            "sdist-sha256=21c8edc0586610de1a9a8cd39b54ed23d2b1e20552100f69f53938cb7678da3d",
            "sdist-sha256=3f12c26ae1ae7a1de5ac19d8ef27a784b2bf592143c716493f1b0f35ec19daca",
            "reuses one artifact digest",
        ),
    ],
    ids=["tag", "commit", "workflow-run", "duplicate-digest"],
)
def test_release_evidence_identity_rejects_internal_mismatch(
    releasable_documents: Path,
    old: str,
    new: str,
    message: str,
) -> None:
    evidence = _release_evidence_block().replace(old, new, 1)
    for name in ("ROADMAP.md", "RELEASING.md"):
        with (releasable_documents / name).open("a", encoding="utf-8") as stream:
            stream.write(evidence)

    with pytest.raises(CheckError, match=message):
        require_public_preview_docs()


def test_release_evidence_identity_must_match_across_history_documents(
    releasable_documents: Path,
) -> None:
    roadmap = _release_evidence_block()
    releasing = roadmap.replace(
        "commit=710c56491d9ef5f47cccff3ce837ab7e799455b0",
        "commit=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        1,
    ).replace(
        "release commit `710c56491d9ef5f47cccff3ce837ab7e799455b0`",
        "release commit `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`",
        1,
    )
    (releasable_documents / "ROADMAP.md").write_text(roadmap, encoding="utf-8")
    (releasable_documents / "RELEASING.md").write_text(releasing, encoding="utf-8")

    with pytest.raises(CheckError, match="must match exactly across both historical records"):
        require_public_preview_docs()


def test_release_evidence_identity_rejects_cross_version_reuse(
    releasable_documents: Path,
) -> None:
    original = _release_evidence_block()
    cloned = (
        original.replace("version=0.1.2", "version=0.1.3")
        .replace("tag=v0.1.2", "tag=v0.1.3")
        .replace("v0.1.2", "v0.1.3")
        .replace("/cometapi/0.1.2/", "/cometapi/0.1.3/")
        .replace("Completed 0.1.2", "Completed 0.1.3")
    )
    for name in ("ROADMAP.md", "RELEASING.md"):
        (releasable_documents / name).write_text(original + cloned, encoding="utf-8")
    with (releasable_documents / "CHANGELOG.md").open("a", encoding="utf-8") as stream:
        stream.write(
            "\n## [0.1.3] - 2026-07-30\n\nHistory.\n\n## [0.1.2] - 2026-07-30\n\nHistory.\n"
        )

    with pytest.raises(CheckError, match="reuse the same release commit"):
        require_public_preview_docs()


def test_release_evidence_block_rejects_unrelated_exact_version(
    releasable_documents: Path,
) -> None:
    evidence = _release_evidence_block().replace(
        "## Completed 0.1.2 maintenance release evidence",
        "## Completed 0.1.2 maintenance release evidence\n\nCurrent public version is 9.9.9.",
    )
    for name in ("ROADMAP.md", "RELEASING.md"):
        with (releasable_documents / name).open("a", encoding="utf-8") as stream:
            stream.write(evidence)

    with pytest.raises(CheckError, match="contains unrelated exact version"):
        require_public_preview_docs()


@pytest.mark.parametrize(
    ("label", "old", "new"),
    [
        (
            "release commit",
            "- Release tag `v0.1.2` at release commit `710c56491d9ef5f47cccff3ce837ab7e799455b0`.",
            "- Release tag `v0.1.2` at release commit "
            "`710c56491d9ef5f47cccff3ce837ab7e799455b0`.\n"
            "- Contradictory release commit "
            "`aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`.",
        ),
        (
            "release commit",
            "- Release tag `v0.1.2` at release commit `710c56491d9ef5f47cccff3ce837ab7e799455b0`.",
            "- Release tag `v0.1.2` at release commit "
            "`710c56491d9ef5f47cccff3ce837ab7e799455b0`.\n"
            "- Published commit `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`.",
        ),
        (
            "release commit",
            "- Release tag `v0.1.2` at release commit `710c56491d9ef5f47cccff3ce837ab7e799455b0`.",
            "- Release tag `v0.1.2` at release commit "
            "`710c56491d9ef5f47cccff3ce837ab7e799455b0`.\n"
            "- Tag target `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`.",
        ),
        (
            "release workflow run",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246\n"
            "- Contradictory release workflow "
            "https://github.com/cometapi-dev/cometapi-python/actions/runs/99999999999",
        ),
        (
            "release workflow run",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246\n"
            "- Release job run: "
            "https://github.com/cometapi-dev/cometapi-python/actions/runs/99999999999",
        ),
        (
            "release workflow run",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246\n"
            "- Publishing workflow "
            "https://github.com/cometapi-dev/cometapi-python/actions/runs/99999999999",
        ),
        (
            "release workflow run",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246\n"
            "- Release pipeline run "
            "https://github.com/cometapi-dev/cometapi-python/actions/runs/99999999999",
        ),
        (
            "release workflow run",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246\n"
            "- GitHub Actions run "
            "https://github.com/cometapi-dev/cometapi-python/actions/runs/99999999999",
        ),
        (
            "release workflow run",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246\n"
            "- Workflow run "
            "https://github.com/cometapi-dev/cometapi-python/actions/runs/99999999999",
        ),
        (
            "release workflow run",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246\n"
            "- Publish workflow "
            "https://github.com/cometapi-dev/cometapi-python/actions/runs/99999999999",
        ),
        (
            "release workflow run",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246\n"
            "- Release run: [details](https://github.com/cometapi-dev/cometapi-python/"
            "actions/runs/99999999999)",
        ),
        (
            "release workflow run",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246\n"
            "- **Release run:** [Actions](https://github.com/cometapi-dev/cometapi-python/"
            "actions/runs/99999999999)",
        ),
        (
            "release workflow run",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246\n"
            "- Release Actions run https://github.com/cometapi-dev/cometapi-python/actions/"
            "runs/99999999999",
        ),
        (
            "release workflow run",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246",
            "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "30515861246\n"
            "- [details](https://github.com/cometapi-dev/cometapi-python/actions/runs/"
            "99999999999) is the release run",
        ),
        (
            "wheel SHA256",
            "- Wheel SHA256: 3f12c26ae1ae7a1de5ac19d8ef27a784b2bf592143c716493f1b0f35ec19daca",
            "- Wheel SHA256: "
            "3f12c26ae1ae7a1de5ac19d8ef27a784b2bf592143c716493f1b0f35ec19daca\n"
            "- Wheel SHA256: "
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        ),
        (
            "wheel SHA256",
            "- Wheel SHA256: 3f12c26ae1ae7a1de5ac19d8ef27a784b2bf592143c716493f1b0f35ec19daca",
            "- Wheel SHA256: "
            "3f12c26ae1ae7a1de5ac19d8ef27a784b2bf592143c716493f1b0f35ec19daca\n"
            "- Wheel checksum: "
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        ),
        (
            "source-distribution SHA256",
            "- Source-distribution SHA256: "
            "21c8edc0586610de1a9a8cd39b54ed23d2b1e20552100f69f53938cb7678da3d",
            "- Source-distribution SHA256: "
            "21c8edc0586610de1a9a8cd39b54ed23d2b1e20552100f69f53938cb7678da3d\n"
            "- Source-distribution SHA256: "
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        ),
        (
            "source-distribution SHA256",
            "- Source-distribution SHA256: "
            "21c8edc0586610de1a9a8cd39b54ed23d2b1e20552100f69f53938cb7678da3d",
            "- Source-distribution SHA256: "
            "21c8edc0586610de1a9a8cd39b54ed23d2b1e20552100f69f53938cb7678da3d\n"
            "- Sdist digest "
            "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc.",
        ),
        (
            "source-distribution SHA256",
            "- Source-distribution SHA256: "
            "21c8edc0586610de1a9a8cd39b54ed23d2b1e20552100f69f53938cb7678da3d",
            "- Source-distribution SHA256: "
            "21c8edc0586610de1a9a8cd39b54ed23d2b1e20552100f69f53938cb7678da3d\n"
            "- Public sdist has SHA256 "
            "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd.",
        ),
        (
            "source-distribution SHA256",
            "- Source-distribution SHA256: "
            "21c8edc0586610de1a9a8cd39b54ed23d2b1e20552100f69f53938cb7678da3d",
            "- Source-distribution SHA256: "
            "21c8edc0586610de1a9a8cd39b54ed23d2b1e20552100f69f53938cb7678da3d\n"
            "- Sdist hash: "
            "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        ),
    ],
)
def test_release_evidence_rejects_contradictory_labeled_identity_values(
    releasable_documents: Path,
    label: str,
    old: str,
    new: str,
) -> None:
    evidence = _release_evidence_block().replace(old, new, 1)
    for name in ("ROADMAP.md", "RELEASING.md"):
        with (releasable_documents / name).open("a", encoding="utf-8") as stream:
            stream.write(evidence)

    with pytest.raises(CheckError) as caught:
        require_public_preview_docs()

    assert label in str(caught.value)
    assert "contradict" in str(caught.value)


def test_release_evidence_rejects_ancillary_workflow_run(
    releasable_documents: Path,
) -> None:
    evidence = _release_evidence_block().replace(
        "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
        "30515861246",
        "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
        "30515861246\n"
        "- Required CI https://github.com/cometapi-dev/cometapi-python/actions/runs/"
        "30511373822",
        1,
    )
    for name in ("ROADMAP.md", "RELEASING.md"):
        with (releasable_documents / name).open("a", encoding="utf-8") as stream:
            stream.write(evidence)
    _replace(
        releasable_documents,
        "CHANGELOG.md",
        "# Changelog\n",
        "# Changelog\n\n## [0.1.2] - 2026-07-30\n\nHistory.\n",
    )

    with pytest.raises(CheckError) as caught:
        require_public_preview_docs()

    message = str(caught.value)
    assert "workflow run" in message
    assert "contradicts its release-identity marker" in message
    assert "outside the immutable evidence block" in message


@pytest.mark.parametrize(
    "reference",
    [
        "<!-- cometapi-release-workflow-reference run=99999999999 -->",
        "<!-- cometapi-release-workflow-reference kind=unknown run=99999999999 -->",
        "<!-- cometapi-release-workflow-reference run=30515861246 -->",
    ],
)
def test_release_evidence_rejects_obsolete_workflow_reference_marker(
    releasable_documents: Path,
    reference: str,
) -> None:
    evidence = _release_evidence_block().replace(
        EVIDENCE_IDENTITY,
        EVIDENCE_IDENTITY + "\n" + reference,
        1,
    )
    for name in ("ROADMAP.md", "RELEASING.md"):
        with (releasable_documents / name).open("a", encoding="utf-8") as stream:
            stream.write(evidence)

    with pytest.raises(CheckError) as caught:
        require_public_preview_docs()

    assert "obsolete workflow-reference marker" in str(caught.value)
    assert "outside the immutable evidence block" in str(caught.value)


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/?next=https://github.com/cometapi-dev/cometapi-python/"
        "actions/runs/30511373822",
        "https://evil.example/#https://github.com/cometapi-dev/cometapi-python/"
        "actions/runs/30511373822",
        "http://github.com/cometapi-dev/cometapi-python/actions/runs/30511373822",
        "https://evil.example/?next=https%3A%2F%2Fgithub.com%2Fcometapi-dev%2F"
        "cometapi-python%2Factions%2Fruns%2F30511373822",
        "//github.com/cometapi-dev/cometapi-python/actions/runs/30511373822",
        "/cometapi-dev/cometapi-python/actions/runs/30511373822",
        "&#47;&#47;github.com/cometapi-dev/cometapi-python/actions/runs/30511373822",
        "mailto:https://github.com/cometapi-dev/cometapi-python/actions/runs/30511373822",
        "prefixhttps://github.com/cometapi-dev/cometapi-python/actions/runs/30511373822",
        "https://github.com/other/repository/actions/runs/30511373822",
        "https://github.com/CometAPI-dev/cometapi-python/actions/runs/30511373822",
        "https://github.com/cometapi-dev/cometapi-python/actions&#x2F;runs&#x2F;30511373822",
        "https://github.com/cometapi-dev/cometapi-python/actions\\/runs\\/30511373822",
        "https://github.com/cometapi-dev/cometapi-python/actions\\runs\\30511373822",
        "https://github.com/cometapi-dev/cometapi-python&#92;actions&#92;runs&#92;30511373822",
        "https://github.com/cometapi-dev/cometapi-python%5Cactions%5Cruns%5C30511373822",
        "https://evil.example/?next=https://github.com/cometapi-dev/cometapi-python%5Cactions%5Cruns%5C30511373822",
        '<a href="https://github.com/cometapi-dev/cometapi-python/'
        'act&#9;ions/runs/30511373822">Required CI</a>',
        "https:\\github.com\\cometapi-dev\\cometapi-python\\actions\\runs\\30511373822",
        "https:\\\\github.com\\cometapi-dev\\cometapi-python\\actions\\runs\\30511373822",
        "https:/\\github.com\\cometapi-dev\\cometapi-python\\actions\\runs\\30511373822",
        "https:\\/github.com\\cometapi-dev\\cometapi-python\\actions\\runs\\30511373822",
        "https://github.com/cometapi-dev/cometapi-python/actions/runs/30511373822.evil",
        "https://github.com/cometapi-dev/cometapi-python/actions/runs/30511373822/attempts/0",
    ],
)
def test_release_evidence_rejects_noncanonical_workflow_reference_url(
    releasable_documents: Path,
    url: str,
) -> None:
    evidence = _release_evidence_block().replace(
        "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
        "30515861246",
        "- Release workflow https://github.com/cometapi-dev/cometapi-python/actions/runs/"
        f"30515861246\n- Required CI {url}",
        1,
    )
    for name in ("ROADMAP.md", "RELEASING.md"):
        with (releasable_documents / name).open("a", encoding="utf-8") as stream:
            stream.write(evidence)

    with pytest.raises(CheckError) as caught:
        require_public_preview_docs()

    assert "non-canonical Actions URL" in str(caught.value)
    assert "/actions/runs/<positive-id>" in str(caught.value)


def test_fenced_release_evidence_is_not_accepted_as_history(
    releasable_documents: Path,
) -> None:
    fenced = f"\n```markdown\n{_release_evidence_block()}```\n"
    for name in ("ROADMAP.md", "RELEASING.md"):
        with (releasable_documents / name).open("a", encoding="utf-8") as stream:
            stream.write(fenced)

    with pytest.raises(CheckError) as caught:
        require_public_preview_docs()

    message = str(caught.value)
    assert "malformed release-evidence marker" in message
    assert "outside immutable release evidence" in message


def test_formatted_marker_examples_do_not_create_release_evidence(
    releasable_documents: Path,
) -> None:
    with (releasable_documents / "ROADMAP.md").open("a", encoding="utf-8") as stream:
        stream.write(
            "\n`<!-- cometapi-release-evidence:start version=9.9.9 date=2026-07-30 -->`\n"
            "Current public version is 9.9.9.\n"
            "`<!-- cometapi-release-evidence:end version=9.9.9 date=2026-07-30 -->`\n"
        )

    with pytest.raises(CheckError, match="malformed release-evidence marker"):
        require_public_preview_docs()


def test_stray_release_identity_marker_is_rejected(releasable_documents: Path) -> None:
    with (releasable_documents / "ROADMAP.md").open("a", encoding="utf-8") as stream:
        stream.write(f"\n{EVIDENCE_IDENTITY}\n")

    with pytest.raises(CheckError, match="must appear inside one release-evidence block"):
        require_public_preview_docs()


def test_malformed_evidence_marker_is_aggregated_with_other_document_failures(
    releasable_documents: Path,
) -> None:
    _change_author(releasable_documents)
    with (releasable_documents / "ROADMAP.md").open("a", encoding="utf-8") as stream:
        stream.write(
            "\n<!-- cometapi-release-evidence:start version=banana date=2026-07-30 -->\n"
            "<!-- cometapi-release-evidence:end version=banana date=2026-07-30 -->\n"
        )

    with pytest.raises(CheckError) as caught:
        require_public_preview_docs()

    message = str(caught.value)
    assert "pyproject.toml: [project].authors" in message
    assert "ROADMAP.md:" in message
    assert "malformed release-evidence marker" in message


def test_roadmap_exact_version_outside_evidence_block_is_rejected(
    releasable_documents: Path,
) -> None:
    with (releasable_documents / "ROADMAP.md").open("a", encoding="utf-8") as stream:
        stream.write("\nImmutable tag v0.1.2 without a complete evidence block.\n")

    with pytest.raises(CheckError, match=r"ROADMAP\.md:.*outside immutable release evidence"):
        require_public_preview_docs()


def test_changelog_allows_exact_historical_versions(releasable_documents: Path) -> None:
    _replace(
        releasable_documents,
        "CHANGELOG.md",
        "# Changelog\n",
        "# Changelog\n\n## [0.1.2] - 2026-07-30\n\nHistorical change.\n",
    )

    require_public_preview_docs()


def test_exact_release_scanner_ignores_third_party_versions() -> None:
    statement = "Current stable OpenAI release: 2.50.0; Ruff release: 0.12.0."
    assert exact_release_version_violations("README.md", statement, "0.1.3") == []


@pytest.mark.parametrize(
    "statement",
    [
        "Latest CometAPI release: 0.2.0.",
        "The current PyPI release is 1.2.3.",
        "Latest stable version: **10**.**4**.**7**.",
        "Latest stable version: `10`.`4`.`7`.",
        "Current release: 2.\n3.4.",
        "Current release: 2.\u200b3.\u200b4.",
        "OpenAI is supported. Current release: 0.1.2.",
        "OpenAI CometAPI 0.1.2 is current.",
        "Release Please reports the current CometAPI version as 0.1.2.",
        "Current CometAPI release 9.8.7 OpenAI.",
        "OpenAI\n9.8.7 is the latest CometAPI release.",
        "See https://github.com/acme/tool. Current CometAPI release 9.8.7.",
        "Python SDK current PyPI release is 0.1.2.",
        "Current cometapi-python version is 0.1.2.",
        "Current CometAPI-openai version is 0.1.2.",
        "Current CometAPI httpx version is 0.1.2.",
        "Current cometapi-python==0.1.2.",
        "CometAPI requirement: >=0.1,==0.1.2.",
        "https://github.com/cometapi-dev/cometapi-python/releases/tag/v0.1.2 current.",
        "Current CometAPI release is <span>0.1.2</span>.",
        "Current CometAPI release is 0.<span>1</span>.2.",
        "Latest stable version: 0.1.2rc1.",
        "Latest stable version: 0.1.2-beta.1.",
        "Current CometAPI SDK==0.1.2.",
        "Current CometAPI package==0.1.2.",
        "Current CometAPI project>=0.1.2.",
        "Current CometAPI library!=0.1.2.",
        "Current CometAPI distribution<0.1.2.",
        "Current CometAPI Python package==0.1.2.",
        "OpenAI 0.1.2 is the current CometAPI release.",
        "Release Please v0.1.2 produced the current CometAPI release.",
        '<a href="https://pypi.org/project/cometapi/0.1.2/">current</a>',
        '<meta content="Current CometAPI release 0.1.2">',
        "OpenAI 0.1.2 is a supported CometAPI release.",
        "Release Please v0.1.2 generated the CometAPI release.",
        "PyPI publisher v0.1.2 shipped the CometAPI release.",
        '<a href="https://pypi.org/project/cometapi/0%2E1%2E2/">current</a>',
        "OpenAI 0.1.2 is required by CometAPI.",
        "OpenAI 0.1.2 is supported by CometAPI.",
        "OpenAI 0.1.2 is bundled by CometAPI.",
        "Release Please v0.1.2 is pinned by CometAPI.",
        "actions/checkout 0.1.2 is pinned by CometAPI.",
        "OpenAI 0.1.2 (CometAPI).",
        "OpenAI version 0.1.2 for CometAPI.",
        "OpenAI release 0.1.2; CometAPI current.",
        "OpenAI 0.1.2 - CometAPI latest.",
        "OpenAI 0.1.2 | CometAPI latest",
        "OpenAI 0.1.2; current Python SDK release.",
        "[current](https://pypi.org/project/cometapi/0.1.2/)",
        "[current](https://github.com/cometapi-dev/cometapi-python/releases/tag/v0.1.2)",
        "![PyPI](https://img.shields.io/pypi/v/cometapi?version=0.1.2)",
        "[current](https://pypi.org/project/cometapi/0%2E1%2E2/)",
        r"[current\]](https://pypi.org/project/cometapi/0.1.2/)",
        "[current](https://pypi.org/project/cometapi/0.1.2/?label=(stable))",
        "Current CometAPI release is [0](https://example.invalid)."
        "[1](https://example.invalid).[2](https://example.invalid).",
        "Current CometAPI release is 0.\u034f1.\u034f2.",
    ],
)
def test_exact_release_scanner_rejects_future_and_obfuscated_first_party_versions(
    statement: str,
) -> None:
    assert exact_release_version_violations("README.md", statement, "0.1.3")


@pytest.mark.parametrize(
    "statement",
    [
        "OpenAI version 0.1.2 is an upstream historical fact.",
        "openai>=0.1.2,<1.0.0 is a third-party compatibility range.",
        "The fixture uses example-lib==0.1.2.",
        "Release Please v0.1.2 behavior is documented upstream.",
        "actions/checkout 0.1.2 to 0.1.3 is upstream history.",
        "https://github.com/acme/tool/releases/tag/v0.1.2",
        "https://pypi.org/project/example-lib/0.1.2/",
        "The current release is 2.50.0 for OpenAI.",
        "2.50.0 is the current OpenAI release.",
        "actions/checkout 7.0.1 is upstream history.",
        "CometAPI requires openai>=2.45.0,<3.0.0.",
        "The CometAPI SDK uses httpx==0.28.1.",
        "CometAPI supports Python 3.10.0 through 3.14.0.",
        "CometAPI pins Release Please v5.0.0.",
        "[upstream](https://pypi.org/project/example-lib/0.1.2/)",
        "[upstream](https://github.com/acme/tool/releases/tag/v0.1.2)",
        "![upstream](https://img.shields.io/pypi/v/example-lib?version=0.1.2)",
        "[redirect](https://example.invalid/?next=https://pypi.org/project/cometapi/0.1.2/)",
    ],
)
def test_exact_release_scanner_allows_structurally_attributed_third_party_versions(
    statement: str,
) -> None:
    assert exact_release_version_violations("README.md", statement, "0.1.3") == []


def test_releasable_cli_allows_next_patch_without_guidance_edits(
    releasable_documents: Path,
) -> None:
    version_script = _copy_version_checker(releasable_documents)
    _replace(releasable_documents, "pyproject.toml", "0.1.0a1", "0.1.3")
    _replace(
        releasable_documents,
        ".release-please-manifest.json",
        "0.1.0-alpha.1",
        "0.1.3",
    )
    changelog = releasable_documents / "CHANGELOG.md"
    changelog.write_text(
        changelog.read_text(encoding="utf-8").replace(
            "# Changelog\n",
            "# Changelog\n\n"
            "## [0.1.3](https://github.com/cometapi-dev/cometapi-python/compare/"
            "v0.1.0-alpha.1%2Brecovery.1...v0.1.3) (2026-07-30)\n\n"
            "Patch maintenance.\n",
            1,
        ),
        encoding="utf-8",
    )

    command = [
        sys.executable,
        str(version_script),
        "--require-changelog",
        "--require-releasable-docs",
    ]
    initial = subprocess.run(
        command,
        cwd=releasable_documents,
        text=True,
        check=False,
        capture_output=True,
    )
    assert initial.returncode == 0, initial.stderr
    assert "version agreement passed: 0.1.3" in initial.stdout

    durable_names = (
        "AGENTS.md",
        "ARCHITECTURE.md",
        "COMPATIBILITY.md",
        "CONTRIBUTING.md",
        "README.md",
    )
    durable_before = {name: (releasable_documents / name).read_bytes() for name in durable_names}
    _replace(releasable_documents, "pyproject.toml", "0.1.3", "0.1.4")
    _replace(releasable_documents, ".release-please-manifest.json", "0.1.3", "0.1.4")
    changelog.write_text(
        changelog.read_text(encoding="utf-8").replace(
            "# Changelog\n",
            "# Changelog\n\n"
            "## [0.1.4](https://github.com/cometapi-dev/cometapi-python/compare/"
            "v0.1.3...v0.1.4) (2026-08-01)\n\nPatch maintenance.\n",
            1,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        command,
        cwd=releasable_documents,
        text=True,
        check=False,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "version agreement passed: 0.1.4" in result.stdout
    assert {
        name: (releasable_documents / name).read_bytes() for name in durable_names
    } == durable_before


def test_releasable_cli_rejects_unmanaged_unreleased_heading(
    releasable_documents: Path,
) -> None:
    version_script = _copy_version_checker(releasable_documents)
    changelog = releasable_documents / "CHANGELOG.md"
    changelog.write_text(
        changelog.read_text(encoding="utf-8").replace(
            "# Changelog\n",
            "# Changelog\n\n## [Unreleased]\n",
            1,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(version_script), "--require-public-preview-docs"],
        cwd=releasable_documents,
        text=True,
        check=False,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "CHANGELOG.md:" in result.stderr
    assert "unmanaged Unreleased heading is forbidden" in result.stderr
    assert "remove it" in result.stderr
    assert "Release Please" in result.stderr


def test_releasable_docs_accept_release_please_native_heading(
    releasable_documents: Path,
) -> None:
    _replace(releasable_documents, "pyproject.toml", "0.1.0a1", "0.1.3")
    _replace(
        releasable_documents,
        ".release-please-manifest.json",
        "0.1.0-alpha.1",
        "0.1.3",
    )
    (releasable_documents / "CHANGELOG.md").write_text(
        """\
# Changelog

## [0.1.3](https://github.com/cometapi-dev/cometapi-python/compare/v0.1.2...v0.1.3) (2026-07-30)

### Fixed

- Deterministic release documents.

## [0.1.2] - 2026-07-29

- Previous release.
""",
        encoding="utf-8",
    )

    require_releasable_docs("0.1.3")


@pytest.mark.parametrize(
    "heading",
    [
        "## [0.1.3](https://github.com/wrong/repository/compare/v0.1.2...v0.1.3) (2026-07-30)",
        "## [0.1.3](https://github.com/cometapi-dev/cometapi-python/compare/"
        "v0.1.1...v0.1.3) (2026-07-30)",
        "## [0.1.3](https://github.com/cometapi-dev/cometapi-python/compare/"
        "v0.1.2...v0.1.4) (2026-07-30)",
        "## [0.1.3](https://github.com/cometapi-dev/cometapi-python/compare/"
        "v0.1.2...v0.1.3) (2026-02-30)",
    ],
)
def test_releasable_docs_reject_mutated_release_please_heading(
    releasable_documents: Path,
    heading: str,
) -> None:
    _replace(releasable_documents, "pyproject.toml", "0.1.0a1", "0.1.3")
    _replace(
        releasable_documents,
        ".release-please-manifest.json",
        "0.1.0-alpha.1",
        "0.1.3",
    )
    (releasable_documents / "CHANGELOG.md").write_text(
        f"# Changelog\n\n{heading}\n\n- Patch.\n\n## [0.1.2] - 2026-07-29\n",
        encoding="utf-8",
    )

    with pytest.raises(CheckError, match=r"canonical dated heading|valid ISO date"):
        require_releasable_docs("0.1.3")


@pytest.mark.parametrize(
    "extra",
    [
        "## [0.1.3] - 2026-07-29\n\nDuplicate.\n\n## [0.1.3] - 2026-07-30\n\nDuplicate current.\n",
        "## [0.1.2] - 2026-07-29\n\nOld.\n\n## [0.1.3] - 2026-07-30\n\nCurrent.\n",
    ],
    ids=["duplicate-current", "out-of-order-current"],
)
def test_releasable_docs_reject_duplicate_or_out_of_order_current_heading(
    releasable_documents: Path,
    extra: str,
) -> None:
    _replace(releasable_documents, "pyproject.toml", "0.1.0a1", "0.1.3")
    _replace(
        releasable_documents,
        ".release-please-manifest.json",
        "0.1.0-alpha.1",
        "0.1.3",
    )
    (releasable_documents / "CHANGELOG.md").write_text(
        "# Changelog\n\n" + extra + "\n## [0.1.2] - 2026-07-28\n\nPrevious.\n",
        encoding="utf-8",
    )

    with pytest.raises(CheckError, match="canonical dated heading"):
        require_releasable_docs("0.1.3")


def test_version_cli_rejects_project_manifest_disagreement(
    releasable_documents: Path,
) -> None:
    version_script = _copy_version_checker(releasable_documents)
    _replace(releasable_documents, ".release-please-manifest.json", "0.1.0-alpha.1", "0.1.4")

    result = subprocess.run(
        [sys.executable, str(version_script), "--require-public-preview-docs"],
        cwd=releasable_documents,
        text=True,
        check=False,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "version disagreement" in result.stderr
    assert "release-please manifest=0.1.4" in result.stderr


@pytest.mark.parametrize(
    "replacement",
    [
        "Pending owner identity must be filled.",
        "Pending ownership confirmation must be filled.",
        "Pending-owner identity must be filled.",
        "0.1.0a1 is approved for PyPI publication.",
        "python -m pip install 'cometapi==0.1.0a1'",
        "https://pypi.org/project/cometapi/0.1.0a1/",
        "https://github.com/cometapi-dev/cometapi-python/releases/tag/v0.1.0",
    ],
    ids=[
        "pending-owner",
        "pending-ownership",
        "pending-owner-hyphen",
        "approval-state",
        "version-pin",
        "pypi-version-link",
        "github-version-link",
    ],
)
def test_releasable_documents_reject_publication_specific_readme_state(
    releasable_documents: Path,
    replacement: str,
) -> None:
    readme = releasable_documents / "README.md"
    if replacement.startswith("https://"):
        readme.write_text(
            readme.read_text(encoding="utf-8") + replacement + "\n",
            encoding="utf-8",
        )
    else:
        _replace(
            releasable_documents,
            "README.md",
            "Stable 0.1.x maintenance releases are available from PyPI.\n"
            f"{PUBLIC_README_INSTALL_COMMAND}",
            replacement,
        )

    with pytest.raises(
        CheckError,
        match=r"publication-neutral release guidance|unpinned stable|exact CometAPI patch",
    ):
        require_releasable_docs("0.1.0a1")


def test_releasable_documents_require_unpinned_install_command(
    releasable_documents: Path,
) -> None:
    _replace(
        releasable_documents,
        "README.md",
        PUBLIC_README_INSTALL_COMMAND,
        "python -m pip install cometapi-sdk",
    )

    with pytest.raises(CheckError, match="unpinned stable install command"):
        require_releasable_docs("0.1.0a1")


def test_artifact_metadata_accepts_publication_neutral_long_description() -> None:
    description = (
        "Stable 0.1.x maintenance releases are available from PyPI.\n"
        f"{PUBLIC_README_INSTALL_COMMAND}"
    )
    check_metadata(
        _artifact_metadata(description),
        "fixture:METADATA",
        "0.1.0a1",
        f"{description}\n",
    )


@pytest.mark.parametrize(
    "description",
    [
        "Pending ownership confirmation.\npython -m pip install cometapi",
        "Pending-owner confirmation.\npython -m pip install cometapi",
        "0.1.0a1 is approved for PyPI publication.\npython -m pip install cometapi",
        "python -m pip install 'cometapi==0.1.0a1'",
        "python -m pip install cometapi\nhttps://pypi.org/project/cometapi/0.1.0a1/",
    ],
    ids=[
        "pending-ownership",
        "pending-owner-hyphen",
        "approval-state",
        "version-pin",
        "versioned-release-link",
    ],
)
def test_artifact_metadata_rejects_publication_specific_long_description(
    description: str,
) -> None:
    with pytest.raises(CheckError, match="long description contains publication-specific"):
        check_metadata(
            _artifact_metadata(description),
            "fixture:METADATA",
            "0.1.0a1",
            f"{description}\n",
        )


def test_artifact_metadata_requires_unpinned_install_command() -> None:
    description = "Stable 0.1.x maintenance releases are available from PyPI."
    with pytest.raises(CheckError, match="unpinned stable install command"):
        check_metadata(
            _artifact_metadata(description),
            "fixture:METADATA",
            "0.1.0a1",
            f"{description}\n",
        )


def test_artifact_metadata_rejects_mutable_published_patch_claim() -> None:
    description = (
        "Stable 0.1.x maintenance releases are available from PyPI.\n"
        "Latest stable version: `0.1.2`.\n"
        f"{PUBLIC_README_INSTALL_COMMAND}"
    )
    with pytest.raises(
        CheckError,
        match="exact CometAPI patch/recovery version outside immutable release evidence",
    ):
        check_metadata(
            _artifact_metadata(description),
            "fixture:METADATA",
            "0.1.0a1",
            f"{description}\n",
        )


def test_wheel_rejects_mutable_claim_in_long_description(tmp_path: Path) -> None:
    current_version = read_project_version()
    built = tmp_path / "built-wheel"
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(built)],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    source = built / f"cometapi-{current_version}-py3-none-any.whl"
    mutated = tmp_path / source.name
    with zipfile.ZipFile(source) as archive, zipfile.ZipFile(mutated, mode="w") as output:
        for info in archive.infolist():
            content = archive.read(info.filename)
            if info.filename.endswith(".dist-info/METADATA"):
                content = content.replace(
                    b"\n\n",
                    b"\n\nLatest stable version: `0.1.2`.\n",
                    1,
                )
            output.writestr(info, content)

    with pytest.raises(CheckError) as caught:
        check_wheel(
            mutated,
            current_version,
            (PROJECT_ROOT / "README.md").read_text(encoding="utf-8"),
        )

    message = str(caught.value)
    assert ".dist-info/METADATA" in message
    assert "long description does not exactly match source README.md" in message


def test_sdist_rejects_mutable_claim_in_persistent_document(tmp_path: Path) -> None:
    current_version = read_project_version()
    built = tmp_path / "built"
    subprocess.run(
        ["uv", "build", "--sdist", "--out-dir", str(built)],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    source = built / f"cometapi-{current_version}.tar.gz"
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    with tarfile.open(source, mode="r:gz") as archive:
        members = archive.getmembers()
        assert all(
            not Path(member.name).is_absolute()
            and ".." not in Path(member.name).parts
            and not (member.issym() or member.islnk() or member.isdev())
            for member in members
        )
        archive.extractall(extracted)
    root = extracted / f"cometapi-{current_version}"
    with (root / "AGENTS.md").open("a", encoding="utf-8") as stream:
        stream.write("\nThe current PyPI release is `0.1.2`.\n")
    mutated = tmp_path / f"cometapi-{current_version}.tar.gz"
    with tarfile.open(mutated, mode="w:gz") as archive:
        archive.add(root, arcname=root.name)

    with pytest.raises(CheckError) as caught:
        check_sdist(
            mutated,
            current_version,
            (PROJECT_ROOT / "README.md").read_text(encoding="utf-8"),
        )

    message = str(caught.value)
    assert "AGENTS.md:" in message
    assert "exact CometAPI patch/recovery version outside immutable release evidence" in message
    assert EXACT_RELEASE_VERSION_FIX in message


def _mutated_sdist_document(
    tmp_path: Path,
    document: str,
    old: str,
    new: str,
) -> tuple[Path, str]:
    current_version = read_project_version()
    built = tmp_path / "built"
    subprocess.run(
        ["uv", "build", "--sdist", "--out-dir", str(built)],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    source = built / f"cometapi-{current_version}.tar.gz"
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    with tarfile.open(source, mode="r:gz") as archive:
        archive.extractall(extracted, filter="data")
    root = extracted / f"cometapi-{current_version}"
    path = root / document
    original = path.read_text(encoding="utf-8")
    assert old in original
    path.write_text(original.replace(old, new, 1), encoding="utf-8")
    mutated = tmp_path / f"cometapi-{current_version}.tar.gz"
    with tarfile.open(mutated, mode="w:gz") as archive:
        archive.add(root, arcname=root.name)
    return mutated, current_version


def test_sdist_rejects_cross_document_release_evidence_mismatch(tmp_path: Path) -> None:
    mutated, current_version = _mutated_sdist_document(
        tmp_path,
        "RELEASING.md",
        "commit=45429f373bbd11314ec43ba81904fdbb78db2522",
        "commit=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    extracted = tmp_path / "repacked"
    extracted.mkdir()
    with tarfile.open(mutated, mode="r:gz") as archive:
        archive.extractall(extracted, filter="data")
    root = extracted / f"cometapi-{current_version}"
    releasing = root / "RELEASING.md"
    releasing.write_text(
        releasing.read_text(encoding="utf-8").replace(
            "[release run 30550536000]",
            "release commit `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`; [release run 30550536000]",
            1,
        ),
        encoding="utf-8",
    )
    with tarfile.open(mutated, mode="w:gz") as archive:
        archive.add(root, arcname=root.name)

    with pytest.raises(CheckError) as caught:
        check_sdist(
            mutated,
            current_version,
            (PROJECT_ROOT / "README.md").read_text(encoding="utf-8"),
        )

    message = str(caught.value)
    assert "source-distribution document and release-evidence violations" in message
    assert "ROADMAP.md/RELEASING.md" in message
    assert "must match exactly across both historical records" in message


def test_sdist_rejects_release_evidence_date_mismatch_with_changelog(tmp_path: Path) -> None:
    mutated, current_version = _mutated_sdist_document(
        tmp_path,
        "CHANGELOG.md",
        "## [0.1.3] - 2026-07-30",
        "## [0.1.3] - 2026-07-31",
    )

    with pytest.raises(CheckError) as caught:
        check_sdist(
            mutated,
            current_version,
            (PROJECT_ROOT / "README.md").read_text(encoding="utf-8"),
        )

    message = str(caught.value)
    assert "source-distribution document and release-evidence violations" in message
    assert "release-evidence identity date for 0.1.3 is 2026-07-30" in message
    assert "CHANGELOG.md records 2026-07-31" in message


def test_copied_repository_verification_runs_public_document_gate() -> None:
    commands = check_repository_independence.offline_check_commands()

    version_commands = [command for command in commands if "scripts/check_version.py" in command]
    assert version_commands == [
        [
            "uv",
            "run",
            "python",
            "scripts/check_version.py",
            "--require-changelog",
            "--require-releasable-docs",
        ]
    ]


def test_artifact_metadata_must_match_source_readme_exactly() -> None:
    expected = (
        "Stable 0.1.x maintenance releases are available from PyPI.\n"
        f"{PUBLIC_README_INSTALL_COMMAND}"
    )
    changed = expected.replace("Stable 0.1.x", "The stable 0.1.x")

    with pytest.raises(CheckError, match="exactly match source README"):
        check_metadata(
            _artifact_metadata(changed),
            "fixture:METADATA",
            "0.1.0a1",
            f"{expected}\n",
        )


def test_public_preview_documents_reject_non_https_canonical_project_url(
    releasable_documents: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(CANONICAL_PROJECT_URLS, "Support", f"mailto:{CANONICAL_SUPPORT}")

    with pytest.raises(CheckError, match="canonical Project-URL Support must use HTTPS"):
        require_public_preview_docs()


def test_public_preview_documents_reject_codeowners(releasable_documents: Path) -> None:
    codeowners = releasable_documents / ".github/CODEOWNERS"
    codeowners.parent.mkdir(parents=True, exist_ok=True)
    codeowners.write_text("* @placeholder\n", encoding="utf-8")
    with pytest.raises(CheckError, match="CODEOWNERS: must remain absent"):
        require_public_preview_docs()


def test_public_preview_documents_reject_broken_codeowners_symlink(
    releasable_documents: Path,
) -> None:
    codeowners = releasable_documents / ".github/CODEOWNERS"
    codeowners.parent.mkdir(parents=True, exist_ok=True)
    codeowners.symlink_to("missing")
    with pytest.raises(CheckError, match="CODEOWNERS: must remain absent"):
        require_public_preview_docs()


def test_public_preview_documents_report_all_violations_together(
    releasable_documents: Path,
) -> None:
    _change_author(releasable_documents)
    _replace(
        releasable_documents,
        "pyproject.toml",
        CANONICAL_PROJECT_URLS["Homepage"],
        "https://wrong.example.invalid",
    )
    (releasable_documents / "LICENSE").write_text(
        "Copyright (c) 2026 [PENDING OWNER: placeholder]\n", encoding="utf-8"
    )
    _change_security_contact(releasable_documents)
    _change_support_contact(releasable_documents)
    _change_conduct_contact(releasable_documents)
    (releasable_documents / "ROADMAP.md").write_text(
        "# Roadmap\n\nRegistry Alpha ready for owner action.\n", encoding="utf-8"
    )
    (releasable_documents / "ARCHITECTURE.md").write_bytes(b"\xff")
    with (releasable_documents / "README.md").open("a", encoding="utf-8") as stream:
        stream.write("\n/Users/example/outside\n[Missing](MISSING.md)\n")

    with pytest.raises(CheckError) as caught:
        require_public_preview_docs()

    message = str(caught.value)
    for expected in (
        "[project].authors",
        "[project.urls].Homepage",
        "LICENSE: must contain the exact line",
        "LICENSE: contains unresolved public identity information",
        "SECURITY.md: missing canonical public value",
        "SUPPORT.md: missing canonical public value",
        "CODE_OF_CONDUCT.md: missing canonical public value",
        "ROADMAP.md: contains preparation-only handoff state",
        "ARCHITECTURE.md: cannot read required public document",
        "README.md: contains non-standalone machine-specific absolute path",
        "README.md: link target does not exist",
    ):
        assert expected in message


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (_change_author, "authors"),
        (_change_repository_url, "Repository"),
        (_change_copyright, "LICENSE"),
        (_change_security_contact, "SECURITY.md"),
        (_change_support_contact, "SUPPORT.md"),
        (_change_conduct_contact, "CODE_OF_CONDUCT.md"),
    ],
    ids=["author", "repository", "copyright", "security", "support", "conduct"],
)
def test_release_documents_reject_noncanonical_identity(
    releasable_documents: Path,
    mutation: Callable[[Path], None],
    message: str,
) -> None:
    mutation(releasable_documents)

    with pytest.raises(CheckError, match=message):
        require_releasable_docs("0.1.0a1")


def test_public_preview_cli_reports_aggregated_violations_and_fails(
    releasable_documents: Path,
) -> None:
    _change_author(releasable_documents)
    _change_security_contact(releasable_documents)
    result = subprocess.run(
        [sys.executable, str(VERSION_SCRIPT), "--require-public-preview-docs"],
        cwd=releasable_documents,
        text=True,
        check=False,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "[project].authors" in result.stderr
    assert "SECURITY.md: missing canonical public value" in result.stderr


def test_release_version_cli_accepts_current_stable_tag() -> None:
    current_version = read_project_version()
    result = subprocess.run(
        [
            sys.executable,
            str(VERSION_SCRIPT),
            "--tag",
            f"v{current_version}",
            "--require-changelog",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        check=False,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert f"version agreement passed: {current_version}" in result.stdout


def test_release_version_cli_accepts_approved_initial_alpha_recovery_tag(
    releasable_documents: Path,
) -> None:
    version_script = _copy_version_checker(releasable_documents)
    result = subprocess.run(
        [
            sys.executable,
            str(version_script),
            "--tag",
            "v0.1.0-alpha.1+recovery.1",
            "--require-changelog",
        ],
        cwd=releasable_documents,
        text=True,
        check=False,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "version agreement passed: 0.1.0a1" in result.stdout


@pytest.mark.parametrize("tag", ["v0.1.0-alpha.1", "v0.1.0-alpha.1+recovery.2"])
def test_release_version_cli_rejects_unapproved_initial_alpha_tag(
    releasable_documents: Path,
    tag: str,
) -> None:
    version_script = _copy_version_checker(releasable_documents)
    result = subprocess.run(
        [sys.executable, str(version_script), "--tag", tag, "--require-changelog"],
        cwd=releasable_documents,
        text=True,
        check=False,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "release tag must use an approved spelling" in result.stderr
