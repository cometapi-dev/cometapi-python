#!/usr/bin/env python3
"""Verify project, release manifest, changelog, tag, and artifact versions agree."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
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
        EXACT_RELEASE_VERSION_FIX,
        PERSISTENT_DOCUMENTS,
        PUBLIC_README_INSTALL_COMMAND,
        CheckError,
        exact_release_version_violations,
        normalize_version,
        public_readme_has_install_command,
        public_readme_release_violations,
        read_project_metadata,
        read_project_version,
        read_release_manifest,
        release_evidence_identities,
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
        EXACT_RELEASE_VERSION_FIX,
        PERSISTENT_DOCUMENTS,
        PUBLIC_README_INSTALL_COMMAND,
        CheckError,
        exact_release_version_violations,
        normalize_version,
        public_readme_has_install_command,
        public_readme_release_violations,
        read_project_metadata,
        read_project_version,
        read_release_manifest,
        release_evidence_identities,
        require_equal_versions,
    )


_CHANGELOG_VERSION = r"\d+\.\d+\.\d+(?:[-_.]?(?:a|alpha)[-_.]?\d+)?"
_CHANGELOG_LEGACY_HEADING = re.compile(
    rf"^##[ \t]+\[(?P<version>{_CHANGELOG_VERSION})\][ \t]+-[ \t]+"
    r"(?P<date>\d{4}-\d{2}-\d{2})[ \t]*$",
    re.IGNORECASE,
)
_CHANGELOG_NATIVE_HEADING = re.compile(
    rf"^##[ \t]+\[(?P<version>{_CHANGELOG_VERSION})\]"
    rf"\((?P<url>{re.escape(CANONICAL_REPOSITORY)}/compare/[^\s)]+)\)[ \t]+"
    r"\((?P<date>\d{4}-\d{2}-\d{2})\)[ \t]*$",
    re.IGNORECASE,
)
_CHANGELOG_VERSION_HEADING_CANDIDATE = re.compile(
    rf"^##[ \t]+\[?(?P<version>{_CHANGELOG_VERSION})(?:\]|[ \t])",
    re.IGNORECASE,
)
_CHANGELOG_UNRELEASED_HEADING = re.compile(r"^##[ \t]+\[Unreleased\][ \t]*$")
_CHANGELOG_UNRELEASED_CANDIDATE = re.compile(
    r"^##[ \t]+\[?Unreleased(?:\]|[ \t])",
    re.IGNORECASE,
)
_CHANGELOG_REFERENCE_CANDIDATE = re.compile(
    rf"^\[(?P<version>{_CHANGELOG_VERSION})\]:[ \t]*(?P<url>\S+)[ \t]*$",
    re.IGNORECASE,
)
_CHANGELOG_ANY_REFERENCE = re.compile(r"^\[[^]]+\]:[ \t]*\S+[ \t]*$")
_MARKDOWN_FENCE_OPEN = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})")
APPROVED_RECOVERY_TAGS = {
    "0.1.0a1": "v0.1.0-alpha.1+recovery.1",
}


@dataclass(frozen=True)
class _ChangelogRelease:
    version: str
    release_date: str
    line: int
    start: int
    end: int
    compare_url: str | None


def _mask_nonprose_changelog_regions(text: str) -> str:
    """Blank fenced code and HTML comments without shifting line offsets."""

    masked = list(text)
    spans = [(match.start(), match.end()) for match in re.finditer(r"<!--.*?-->", text, re.DOTALL)]
    open_start: int | None = None
    fence_character = ""
    minimum_length = 0
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        if open_start is None:
            match = _MARKDOWN_FENCE_OPEN.match(line)
            if match is not None:
                fence = match.group("fence")
                open_start = offset
                fence_character = fence[0]
                minimum_length = len(fence)
        elif re.fullmatch(
            rf" {{0,3}}{re.escape(fence_character)}{{{minimum_length},}}[ \t]*",
            line,
        ):
            spans.append((open_start, offset + len(raw_line)))
            open_start = None
            fence_character = ""
            minimum_length = 0
        offset += len(raw_line)
    if open_start is not None:
        spans.append((open_start, len(text)))
    for start, end in spans:
        masked[start:end] = ["\n" if value == "\n" else " " for value in text[start:end]]
    return "".join(masked)


def _changelog_version_key(version: str) -> tuple[int, int, int, int, int]:
    normalized = normalize_version(version)
    match = re.fullmatch(
        r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
        r"(?:a(?P<alpha>\d+))?",
        normalized,
    )
    if match is None:  # normalize_version already validates this grammar.
        raise CheckError(f"unsupported changelog release version: {version!r}")
    alpha = match.group("alpha")
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        1 if alpha is None else 0,
        0 if alpha is None else int(alpha),
    )


def _changelog_tag(version: str, *, as_predecessor: bool = False) -> str:
    normalized = normalize_version(version)
    if as_predecessor and normalized in APPROVED_RECOVERY_TAGS:
        return APPROVED_RECOVERY_TAGS[normalized]
    alpha = re.fullmatch(r"(?P<base>\d+\.\d+\.\d+)a(?P<number>\d+)", normalized)
    if alpha is not None:
        return f"v{alpha.group('base')}-alpha.{alpha.group('number')}"
    return f"v{normalized}"


def _compare_tags(url: str) -> tuple[str, str] | None:
    prefix = f"{CANONICAL_REPOSITORY}/compare/"
    if not url.startswith(prefix):
        return None
    comparison = unquote(url.removeprefix(prefix))
    if comparison.count("...") != 1:
        return None
    before, after = comparison.split("...", 1)
    return before, after


def _changelog_preamble_end(text: str) -> int:
    heading = re.search(r"(?m)^##[ \t]+.*$", text)
    return heading.start() if heading is not None else len(text)


def _changelog_unreleased_regions(text: str) -> list[tuple[int, int]]:
    level_two = list(re.finditer(r"(?m)^##[ \t]+.*$", text))
    regions: list[tuple[int, int]] = []
    for index, heading in enumerate(level_two):
        if _CHANGELOG_UNRELEASED_HEADING.fullmatch(heading.group(0)) is None:
            continue
        end = level_two[index + 1].start() if index + 1 < len(level_two) else len(text)
        regions.append((heading.start(), end))
    return regions


def _changelog_mutable_region_violations(
    text: str,
) -> list[str]:
    regions = [(0, _changelog_preamble_end(text)), *_changelog_unreleased_regions(text)]
    findings: list[str] = []
    seen: set[tuple[int, str]] = set()
    for start, end in regions:
        region = text[start:end]
        base_line = text.count("\n", 0, start)
        for relative_line, label in exact_release_version_violations(
            "CHANGELOG-Unreleased.md",
            region,
            "0.1.0",
        ):
            finding = (
                base_line + relative_line,
                label,
            )
            if finding in seen:
                continue
            seen.add(finding)
            findings.append(
                f"CHANGELOG.md:{finding[0]}: {finding[1]} in preamble or Unreleased prose; "
                f"{EXACT_RELEASE_VERSION_FIX}"
            )
    return findings


def _parse_changelog_releases(text: str) -> list[_ChangelogRelease]:
    text = _mask_nonprose_changelog_regions(text)
    releases: list[_ChangelogRelease] = []
    violations: list[str] = []
    unreleased_lines: list[int] = []
    offset = 0
    for line_number, raw_line in enumerate(text.splitlines(keepends=True), start=1):
        line = raw_line.rstrip("\r\n")
        legacy = _CHANGELOG_LEGACY_HEADING.fullmatch(line)
        native = _CHANGELOG_NATIVE_HEADING.fullmatch(line)
        match = legacy if legacy is not None else native
        if match is not None:
            try:
                normalized = normalize_version(match.group("version"))
                date.fromisoformat(match.group("date"))
            except CheckError as exc:
                violations.append(f"CHANGELOG.md:{line_number}: {exc}")
            except ValueError:
                violations.append(
                    f"CHANGELOG.md:{line_number}: canonical dated heading must contain a "
                    "valid ISO date"
                )
            else:
                releases.append(
                    _ChangelogRelease(
                        version=normalized,
                        release_date=match.group("date"),
                        line=line_number,
                        start=offset,
                        end=offset + len(raw_line),
                        compare_url=match.group("url") if native is not None else None,
                    )
                )
        elif _CHANGELOG_VERSION_HEADING_CANDIDATE.match(line) is not None:
            violations.append(
                f"CHANGELOG.md:{line_number}: release heading must use a canonical dated "
                "heading: '## [version] - YYYY-MM-DD' or Release Please's canonical "
                "compare-link form"
            )
        elif _CHANGELOG_UNRELEASED_HEADING.fullmatch(line) is not None:
            unreleased_lines.append(line_number)
        elif _CHANGELOG_UNRELEASED_CANDIDATE.match(line) is not None:
            violations.append(
                f"CHANGELOG.md:{line_number}: Unreleased heading must be exactly '## [Unreleased]'"
            )
        offset += len(raw_line)

    if not releases:
        violations.append("CHANGELOG.md: has no canonical dated release heading")
    if len(unreleased_lines) > 1:
        violations.append("CHANGELOG.md: must contain at most one '## [Unreleased]' heading")
    if unreleased_lines and releases and unreleased_lines[0] > releases[0].line:
        violations.append("CHANGELOG.md: '## [Unreleased]' must precede every dated release")

    seen_versions: dict[str, int] = {}
    for release in releases:
        previous_line = seen_versions.get(release.version)
        if previous_line is not None:
            violations.append(
                f"CHANGELOG.md:{release.line}: canonical dated heading version "
                f"{release.version} duplicates line {previous_line}"
            )
        else:
            seen_versions[release.version] = release.line

    for current, previous in pairwise(releases):
        if _changelog_version_key(current.version) <= _changelog_version_key(previous.version):
            violations.append(
                f"CHANGELOG.md:{previous.line}: canonical dated headings must be in strictly "
                f"descending version order; {previous.version} follows {current.version}"
            )
        if date.fromisoformat(current.release_date) < date.fromisoformat(previous.release_date):
            violations.append(
                f"CHANGELOG.md:{previous.line}: canonical dated heading dates must be "
                f"non-increasing; {previous.release_date} follows {current.release_date}"
            )

    for index, release in enumerate(releases):
        if release.compare_url is None:
            continue
        tags = _compare_tags(release.compare_url)
        if index + 1 >= len(releases):
            violations.append(
                f"CHANGELOG.md:{release.line}: Release Please canonical dated heading for "
                f"{release.version} has no next historical version to use as its predecessor"
            )
            continue
        expected_before = _changelog_tag(releases[index + 1].version, as_predecessor=True)
        expected_after = _changelog_tag(release.version)
        if tags != (expected_before, expected_after):
            violations.append(
                f"CHANGELOG.md:{release.line}: Release Please canonical dated heading for "
                f"{release.version} must compare {expected_before}...{expected_after}, using "
                "the next historical version as its predecessor"
            )

    reference_versions: dict[str, int] = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        reference = _CHANGELOG_REFERENCE_CANDIDATE.fullmatch(line)
        if reference is None:
            if _CHANGELOG_ANY_REFERENCE.fullmatch(line) is not None:
                violations.append(
                    f"CHANGELOG.md:{line_number}: compare-link definitions must use a "
                    "canonical exact release version label and repository compare URL"
                )
            continue
        try:
            version = normalize_version(reference.group("version"))
        except CheckError as exc:
            violations.append(f"CHANGELOG.md:{line_number}: {exc}")
            continue
        if version in reference_versions:
            violations.append(
                f"CHANGELOG.md:{line_number}: duplicate compare-link definition for {version}"
            )
            continue
        reference_versions[version] = line_number
        try:
            index = next(
                index for index, release in enumerate(releases) if release.version == version
            )
        except StopIteration:
            violations.append(
                f"CHANGELOG.md:{line_number}: compare-link definition for {version} has no "
                "canonical dated release heading"
            )
            continue
        if index + 1 >= len(releases):
            violations.append(
                f"CHANGELOG.md:{line_number}: compare-link definition for {version} has no "
                "next historical version to use as its predecessor"
            )
            continue
        expected_before = _changelog_tag(releases[index + 1].version, as_predecessor=True)
        expected_after = _changelog_tag(version)
        tags = _compare_tags(reference.group("url"))
        if tags != (expected_before, expected_after):
            violations.append(
                f"CHANGELOG.md:{line_number}: compare-link definition for {version} must "
                f"compare {expected_before}...{expected_after}, using the next historical "
                "version as its predecessor"
            )

    violations.extend(_changelog_mutable_region_violations(text))
    if violations:
        raise CheckError(
            "CHANGELOG.md canonical release-history violations:\n"
            + "\n".join(f"- {violation}" for violation in violations)
        )
    return releases


def changelog_release_dates(text: str) -> dict[str, str]:
    """Return canonical release dates keyed by normalized version, newest first."""
    return {release.version: release.release_date for release in _parse_changelog_releases(text)}


def _changelog_versions(path: Path) -> list[str]:
    return list(changelog_release_dates(path.read_text(encoding="utf-8")))


def _artifact_version(path: Path) -> str:
    match = re.fullmatch(
        r"cometapi-(\d+\.\d+\.\d+(?:a\d+)?)(?:-[^-]+-[^-]+-[^.]+\.whl|\.tar\.gz)",
        path.name,
    )
    if match is None:
        raise CheckError(f"cannot derive a cometapi version from {path.name}")
    return match.group(1)


def _require_canonical_tag(tag: str, project_version: str) -> str:
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
    for name in PERSISTENT_DOCUMENTS:
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


def _check_release_version_boundaries(
    documents: dict[str, str],
    project_version: str,
    violations: list[str],
) -> None:
    for name, text in documents.items():
        for line, label in exact_release_version_violations(name, text, project_version):
            violation = f"{name}:{line}: contains {label}; {EXACT_RELEASE_VERSION_FIX}"
            if violation not in violations:
                violations.append(violation)

    evidence = {
        name: identities
        for name in ("ROADMAP.md", "RELEASING.md")
        if name in documents
        for identities in [_safe_release_evidence_identities(name, documents[name], violations)]
    }
    changelog_dates: dict[str, str] = {}
    changelog = documents.get("CHANGELOG.md")
    if changelog is not None:
        try:
            changelog_dates = changelog_release_dates(changelog)
        except CheckError as exc:
            violations.append(str(exc))
    for name, identities in evidence.items():
        for version, identity in identities.items():
            identity_date = getattr(identity, "date", None)
            changelog_date = changelog_dates.get(version)
            if changelog_date is None:
                violations.append(
                    f"{name}: release-evidence identity for {version} has no matching canonical "
                    "dated CHANGELOG.md release heading"
                )
            elif identity_date != changelog_date:
                violations.append(
                    f"{name}: release-evidence identity date for {version} is {identity_date}, "
                    f"but CHANGELOG.md records {changelog_date}"
                )
    if set(evidence) == {"ROADMAP.md", "RELEASING.md"}:
        roadmap = evidence["ROADMAP.md"]
        releasing = evidence["RELEASING.md"]
        for version in sorted(set(roadmap) | set(releasing)):
            if roadmap.get(version) != releasing.get(version):
                violations.append(
                    f"ROADMAP.md/RELEASING.md: release-evidence identity for {version} "
                    "must match exactly across both historical records"
                )


def _safe_release_evidence_identities(
    name: str,
    text: str,
    violations: list[str],
) -> dict[str, object]:
    try:
        return cast(dict[str, object], release_evidence_identities(name, text))
    except CheckError as exc:
        message = str(exc)
        if message not in "\n".join(violations):
            violations.append(message)
        return {}


def require_public_preview_docs(project_version: str | None = None) -> None:
    """Collect every violation, then fail closed until public content is suitable."""

    violations: list[str] = []
    documents = _read_public_documents(violations)
    _check_project_identity(violations)
    if project_version is None:
        try:
            project_version = read_project_version()
        except CheckError as exc:
            violations.append(str(exc))
            project_version = "0.1.0"

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

    _check_release_version_boundaries(documents, project_version, violations)
    _check_standalone_links(documents, violations)
    if violations:
        raise CheckError(
            "public preview document violations:\n"
            + "\n".join(f"- {violation}" for violation in violations)
        )


def require_releasable_docs(project_version: str) -> None:
    require_public_preview_docs(project_version)

    readme = Path("README.md").read_text(encoding="utf-8")
    violations = public_readme_release_violations(readme)
    if violations:
        raise CheckError(
            "README.md must use publication-neutral release guidance; found: "
            + ", ".join(sorted(set(violations)))
        )
    if not public_readme_has_install_command(readme):
        raise CheckError(
            "README.md must contain the unpinned stable install command "
            f"{PUBLIC_README_INSTALL_COMMAND!r}"
        )

    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    normalized = normalize_version(project_version)
    releases = _parse_changelog_releases(changelog)
    release = next((item for item in releases if item.version == normalized), None)
    if release is None or releases[0].version != normalized:
        raise CheckError(
            f"CHANGELOG.md has no newest canonical dated heading for {normalized}; use either "
            "the legacy '[version] - YYYY-MM-DD' historical form or Release Please's exact "
            "canonical compare-link '(YYYY-MM-DD)' form"
        )
    release_section = changelog[release.end :]
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
        versions.append(("tag", _require_canonical_tag(args.tag, project)))
    for value in args.artifacts:
        path = Path(value)
        if not path.is_file():
            raise CheckError(f"artifact does not exist: {path}")
        versions.append((path.name, _artifact_version(path)))

    changelog = Path("CHANGELOG.md")
    headings: list[str] = []
    if changelog.is_file() and (
        args.require_changelog or args.require_public_preview_docs or args.require_releasable_docs
    ):
        headings = _changelog_versions(changelog)
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
