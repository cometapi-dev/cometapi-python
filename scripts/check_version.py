#!/usr/bin/env python3
"""Verify project, release manifest, changelog, tag, and artifact versions agree."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import cast
from urllib.parse import unquote, urlsplit

try:
    from ._checks import (
        CANONICAL_AUTHOR,
        CANONICAL_COPYRIGHT,
        CANONICAL_PROJECT_URLS,
        CANONICAL_REPOSITORY,
        CANONICAL_SECURITY,
        CANONICAL_SUPPORT,
        DIST_NAME,
        CheckError,
        normalize_version,
        read_project_metadata,
        read_project_version,
        read_release_manifest,
        require_equal_versions,
    )
except ImportError:  # Direct execution from the repository root.
    from _checks import (
        CANONICAL_AUTHOR,
        CANONICAL_COPYRIGHT,
        CANONICAL_PROJECT_URLS,
        CANONICAL_REPOSITORY,
        CANONICAL_SECURITY,
        CANONICAL_SUPPORT,
        DIST_NAME,
        CheckError,
        normalize_version,
        read_project_metadata,
        read_project_version,
        read_release_manifest,
        require_equal_versions,
    )


def _changelog_versions(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    candidates = re.findall(
        r"(?mi)^##\s+(?:\[)?(\d+\.\d+\.\d+(?:[-_.]?(?:a|alpha)[-_.]?\d+)?)(?:\])?(?:\s|$)",
        text,
    )
    return candidates


def _artifact_version(path: Path) -> str:
    match = re.fullmatch(
        r"cometapi-(\d+\.\d+\.\d+(?:a\d+)?)(?:-[^-]+-[^-]+-[^.]+\.whl|\.tar\.gz)",
        path.name,
    )
    if match is None:
        raise CheckError(f"cannot derive a cometapi version from {path.name}")
    return match.group(1)


APPROVED_RECOVERY_TAGS = {
    "0.1.0a1": "v0.1.0-alpha.1+recovery.1",
}


def require_canonical_tag(tag: str, project_version: str) -> str:
    normalized = normalize_version(project_version)
    alpha = re.fullmatch(r"(?P<base>\d+\.\d+\.\d+)a(?P<number>\d+)", normalized)
    expected = (
        f"v{alpha.group('base')}-alpha.{alpha.group('number')}"
        if alpha is not None
        else f"v{normalized}"
    )
    recovery = APPROVED_RECOVERY_TAGS.get(normalized)
    allowed = {recovery} if recovery is not None else {expected}
    if tag not in allowed:
        raise CheckError(
            f"release tag must use an approved spelling {sorted(allowed)!r}, got {tag!r}"
        )
    return normalized


PUBLIC_DOCUMENTS = (
    "README.md",
    "ROADMAP.md",
    "CHANGELOG.md",
    "AGENTS.md",
    "RELEASING.md",
    "COMPATIBILITY.md",
    "ARCHITECTURE.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "SUPPORT.md",
    "CODE_OF_CONDUCT.md",
)

FORBIDDEN_PUBLIC_PATTERNS = {
    r"(?i)registry alpha ready for owner action": "handoff state",
    r"(?i)pending owner action": "owner-action placeholder",
    r"(?i)implementation agent": "implementation-agent narrative",
    r"(?i)handoff report": "handoff narrative",
    r"(?i)local evidence snapshot": "machine-local evidence snapshot",
    r"(?i)(?:internal|planning|parent) workspace": "workspace narrative",
    r"(?i)former parent workspace": "workspace history",
    r"(?i)local candidate": "local-candidate narrative",
    r"(?i)SDK_PRD\.md": "planning-file reference",
    r"(?i)cometapi-worksapce": "workspace-name reference",
    r"(?i)\b(?:Claude|Codex)\b": "tool-session reference",
}


def _read_public_documents(violations: list[str]) -> dict[str, str]:
    documents: dict[str, str] = {}
    for name in PUBLIC_DOCUMENTS:
        try:
            documents[name] = Path(name).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            violations.append(f"{name}: cannot read required public document: {exc}")
    return documents


def _check_project_identity(violations: list[str]) -> None:
    try:
        project = read_project_metadata(Path("."))
    except CheckError as exc:
        violations.append(str(exc))
        return

    if project.get("name") != DIST_NAME:
        violations.append(f"pyproject.toml: [project].name must be {DIST_NAME!r}")
    if project.get("authors") != [{"name": CANONICAL_AUTHOR}]:
        violations.append(
            f"pyproject.toml: [project].authors must equal [{{ name = {CANONICAL_AUTHOR!r} }}]"
        )

    urls = project.get("urls")
    url_values = cast(dict[str, object], urls) if isinstance(urls, dict) else {}
    for label, expected in CANONICAL_PROJECT_URLS.items():
        parsed = urlsplit(expected)
        if parsed.scheme != "https" or not parsed.netloc:
            violations.append(f"canonical Project-URL {label} must use HTTPS: {expected!r}")
        actual = url_values.get(label)
        if actual != expected:
            violations.append(f"pyproject.toml: [project.urls].{label} must equal {expected!r}")


def _check_standalone_links(documents: dict[str, str], violations: list[str]) -> None:
    root = Path(".").resolve()
    for name, text in documents.items():
        for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
            raw_target = match.group(1).strip().strip("<>")
            parsed = urlsplit(raw_target)
            if parsed.scheme or raw_target.startswith("#"):
                continue
            relative = unquote(parsed.path)
            target = (Path(name).parent / relative).resolve()
            if not target.is_relative_to(root):
                violations.append(f"{name}: link escapes the repository root: {raw_target!r}")
            elif not target.is_file():
                violations.append(f"{name}: link target does not exist: {raw_target!r}")


def require_public_preview_docs() -> None:
    """Collect every violation, then fail closed until public content is suitable."""

    violations: list[str] = []
    documents = _read_public_documents(violations)
    _check_project_identity(violations)

    codeowners = Path(".github/CODEOWNERS")
    if codeowners.exists() or codeowners.is_symlink():
        violations.append(
            ".github/CODEOWNERS: must remain absent until a real multi-maintainer model exists"
        )

    try:
        license_text = Path("LICENSE").read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        violations.append(f"LICENSE: cannot read required public document: {exc}")
    else:
        if CANONICAL_COPYRIGHT not in license_text.splitlines():
            violations.append(f"LICENSE: must contain the exact line {CANONICAL_COPYRIGHT!r}")
        if re.search(r"(?i)pending owner|placeholder|tbd|todo|your name", license_text):
            violations.append("LICENSE: contains unresolved public identity information")

    required_values = {
        "README.md": (
            CANONICAL_PROJECT_URLS["Homepage"],
            CANONICAL_PROJECT_URLS["Documentation"],
            CANONICAL_REPOSITORY,
            CANONICAL_PROJECT_URLS["Issues"],
            CANONICAL_SUPPORT,
            CANONICAL_SECURITY,
        ),
        "SECURITY.md": (CANONICAL_SECURITY, CANONICAL_SUPPORT),
        "SUPPORT.md": (CANONICAL_PROJECT_URLS["Issues"], CANONICAL_SUPPORT),
        "CODE_OF_CONDUCT.md": (CANONICAL_SUPPORT,),
    }
    for name, values in required_values.items():
        text = documents.get(name, "")
        for value in values:
            if value not in text:
                violations.append(f"{name}: missing canonical public value {value!r}")

    for name, text in documents.items():
        for pattern, label in FORBIDDEN_PUBLIC_PATTERNS.items():
            if re.search(pattern, text):
                violations.append(f"{name}: contains preparation-only {label}")
        for needle, label in (
            (".." + "/", "parent-relative dependency"),
            ("/" + "Users/", "machine-specific absolute path"),
            ("/home/" + "runner/work/", "runner-specific absolute path"),
        ):
            if needle in text:
                violations.append(f"{name}: contains non-standalone {label}")

    _check_standalone_links(documents, violations)
    if violations:
        raise CheckError(
            "public preview document violations:\n"
            + "\n".join(f"- {violation}" for violation in violations)
        )


def require_releasable_docs(project_version: str) -> None:
    require_public_preview_docs()

    readme = Path("README.md").read_text(encoding="utf-8")
    if "pending owner" in readme.casefold():
        raise CheckError("README.md still contains pending owner identity or contact metadata")
    readme_status = " ".join(re.sub(r"[^\w.]+", " ", readme).split())
    unpublished_patterns = (
        r"\bcandidate\b",
        r"\bno\s+pypi\s+publication\b",
        r"\b(?:has\s+)?not\s+been\s+published\b",
        r"\bdo\s+not\s+treat\b[^\n]*\bcurrently\s+available\b",
        r"\blocal\s+0\.1\.0a1\s+registry\s+alpha\s+candidate\b",
        r"\blocal\s+candidate\b",
    )
    present = [
        pattern
        for pattern in unpublished_patterns
        if re.search(pattern, readme_status, flags=re.IGNORECASE)
    ]
    if present:
        raise CheckError(
            "README.md still describes the release as local or unpublished; "
            "remove every stale status statement before tagging"
        )
    if (
        re.search(
            rf"\b{re.escape(normalize_version(project_version))}\s+is\s+approved\s+for\s+"
            r"pypi\s+publication\b",
            readme_status,
            flags=re.IGNORECASE,
        )
        is None
    ):
        raise CheckError(
            "README.md must explicitly state '<version> is approved for PyPI publication' "
            "before tagging"
        )

    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    normalized = normalize_version(project_version)
    heading = re.search(
        rf"(?mi)^##\s+\[?{re.escape(normalized)}\]?\s+-\s+(.+?)\s*$",
        changelog,
    )
    if heading is None:
        raise CheckError(f"CHANGELOG.md has no dated heading for {normalized}")
    release_state = heading.group(1).strip()
    if (
        release_state.casefold() == "unreleased"
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}", release_state) is None
    ):
        raise CheckError(f"CHANGELOG.md release heading for {normalized} must contain an ISO date")
    release_section = changelog[heading.end() :]
    next_heading = re.search(r"(?m)^##\s+", release_section)
    if next_heading is not None:
        release_section = release_section[: next_heading.start()]
    release_status = " ".join(re.sub(r"[^\w.]+", " ", release_section).split())
    if re.search(
        r"(?i)\b(?:candidate|unreleased|unpublished|not\s+been\s+published|"
        r"local\s+registry\s+alpha\s+candidate)\b",
        release_status,
    ):
        raise CheckError(
            f"CHANGELOG.md section for {normalized} still describes the release as unpublished"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs="*", help="optional wheel and sdist paths")
    parser.add_argument("--expected")
    parser.add_argument("--tag")
    parser.add_argument("--require-changelog", action="store_true")
    parser.add_argument("--require-public-preview-docs", action="store_true")
    parser.add_argument("--require-releasable-docs", action="store_true")
    parser.add_argument("--print-version", action="store_true")
    args = parser.parse_args()

    project = read_project_version()
    versions = [("pyproject", project), ("release-please manifest", read_release_manifest())]
    if args.expected:
        versions.append(("expected", args.expected))
    if args.tag:
        versions.append(("tag", require_canonical_tag(args.tag, project)))
    for value in args.artifacts:
        path = Path(value)
        if not path.is_file():
            raise CheckError(f"artifact does not exist: {path}")
        versions.append((path.name, _artifact_version(path)))

    changelog = Path("CHANGELOG.md")
    headings = _changelog_versions(changelog) if changelog.is_file() else []
    normalized_project = normalize_version(project)
    if args.require_changelog:
        if not headings:
            raise CheckError("CHANGELOG.md has no release-version heading")
        if normalized_project not in {normalize_version(value) for value in headings}:
            raise CheckError(f"CHANGELOG.md has no heading for {normalized_project}")
        versions.append(("changelog", normalized_project))
    if args.require_releasable_docs:
        require_releasable_docs(project)
    if args.require_public_preview_docs:
        require_public_preview_docs()

    agreed = require_equal_versions(versions)
    if args.print_version:
        print(agreed)
    else:
        print(f"version agreement passed: {agreed}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckError as error:
        raise SystemExit(f"version check failed: {error}") from error
