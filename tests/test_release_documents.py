from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts._checks import (
    CANONICAL_AUTHOR,
    CANONICAL_COPYRIGHT,
    CANONICAL_PROJECT_URLS,
    CANONICAL_SECURITY,
    CANONICAL_SUPPORT,
    CheckError,
)
from scripts.check_version import require_public_preview_docs, require_releasable_docs

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSION_SCRIPT = PROJECT_ROOT / "scripts" / "check_version.py"


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
            "0.1.0a1 is approved for PyPI publication.\n"
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


def test_public_preview_documents_reject_codeowners(releasable_documents: Path) -> None:
    codeowners = releasable_documents / ".github/CODEOWNERS"
    codeowners.parent.mkdir(parents=True, exist_ok=True)
    codeowners.write_text("* @placeholder\n", encoding="utf-8")
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
