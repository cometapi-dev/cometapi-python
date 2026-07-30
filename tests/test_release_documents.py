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
    MUTABLE_PUBLISHED_VERSION_FIX,
    PUBLIC_README_INSTALL_COMMAND,
    CheckError,
    mutable_published_version_claims,
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
    assert "mutable " in result.stderr
    assert "patch" in result.stderr
    assert MUTABLE_PUBLISHED_VERSION_FIX in result.stderr


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
    assert "mutable latest/current published patch version" in result.stderr
    assert MUTABLE_PUBLISHED_VERSION_FIX in result.stderr


def test_public_preview_documents_allow_immutable_release_evidence(
    releasable_documents: Path,
) -> None:
    evidence = """\
## Completed 0.1.2 maintenance release evidence

- Release `v0.1.2` at commit `710c56491d9ef5f47cccff3ce837ab7e799455b0`
  completed workflow run 30515861246 on 2026-07-30.
- https://pypi.org/project/cometapi/0.1.2/
- https://github.com/cometapi-dev/cometapi-python/releases/tag/v0.1.2
- Wheel SHA256: 3f12c26ae1ae7a1de5ac19d8ef27a784b2bf592143c716493f1b0f35ec19daca
"""
    for name in ("CHANGELOG.md", "ROADMAP.md", "RELEASING.md"):
        with (releasable_documents / name).open("a", encoding="utf-8") as stream:
            stream.write(evidence)

    require_public_preview_docs()


@pytest.mark.parametrize(
    "statement",
    [
        "Current stable release of Ruff: 0.12.0.",
        "Latest stable version of httpx is 0.28.1.",
        "Current PyPI release of openai: 2.50.0.",
        "Latest stable OpenAI release: 2.50.0.",
        "As of 2026-07-30, the current PyPI release was 0.1.2.",
        "## Release evidence — 2026-07-30\n\nAt publication, 0.1.2 was the current PyPI release.",
        "Release v0.1.2 is the latest stable version in the historical 2026-07-30 snapshot.",
        "Release 0.1.2 was published on 2026-07-30.",
        "The immutable v0.1.2 tag resolves to release commit 710c5649.",
        "PyPI version remains 0.1.0a1 in recovery identity evidence.",
        "https://pypi.org/project/cometapi/0.1.2/",
        "[PyPI 0.1.2](https://pypi.org/project/cometapi/0.1.2/)",
        "The exact [PyPI release](https://pypi.org/project/cometapi/0.1.2/) is public.",
    ],
)
def test_mutable_claim_detector_allows_attributed_or_historical_evidence(
    statement: str,
) -> None:
    assert mutable_published_version_claims(statement) == []


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
    with (releasable_documents / "CHANGELOG.md").open("a", encoding="utf-8") as stream:
        stream.write("\n## [0.1.3] - 2026-07-30\n\nPatch maintenance.\n")

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
    with (releasable_documents / "CHANGELOG.md").open("a", encoding="utf-8") as stream:
        stream.write("\n## [0.1.4] - 2026-08-01\n\nPatch maintenance.\n")

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

    with pytest.raises(CheckError, match=r"publication-neutral release guidance|unpinned stable"):
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
        match="mutable latest/current published patch version",
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
    assert "mutable latest/current published patch version" in message
    assert MUTABLE_PUBLISHED_VERSION_FIX in message


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
            "--require-public-preview-docs",
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
