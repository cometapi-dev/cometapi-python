#!/usr/bin/env python3
"""Inspect wheel and sdist identity, metadata, paths, and package shape."""

from __future__ import annotations

import argparse
import re
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

try:
    from ._checks import (
        CANONICAL_AUTHOR,
        CANONICAL_PROJECT_URLS,
        EXACT_RELEASE_VERSION_FIX,
        PROJECT_ROOT,
        PUBLIC_README_INSTALL_COMMAND,
        SDIST_PUBLIC_DOCUMENTS,
        CheckError,
        ReleaseEvidenceIdentity,
        exact_release_version_violations,
        metadata_description,
        normalize_version,
        parse_metadata,
        public_readme_has_install_command,
        public_readme_release_violations,
        read_project_version,
        release_evidence_identities,
        sha256_file,
    )
    from .check_version import changelog_release_dates
except ImportError:  # Direct execution from the repository root.
    from _checks import (
        CANONICAL_AUTHOR,
        CANONICAL_PROJECT_URLS,
        EXACT_RELEASE_VERSION_FIX,
        PROJECT_ROOT,
        PUBLIC_README_INSTALL_COMMAND,
        SDIST_PUBLIC_DOCUMENTS,
        CheckError,
        ReleaseEvidenceIdentity,
        exact_release_version_violations,
        metadata_description,
        normalize_version,
        parse_metadata,
        public_readme_has_install_command,
        public_readme_release_violations,
        read_project_version,
        release_evidence_identities,
        sha256_file,
    )
    from check_version import changelog_release_dates

REQUIRED_PACKAGE_FILES = {
    "cometapi/__init__.py",
    "cometapi/_config.py",
    "cometapi/client.py",
    "cometapi/py.typed",
}
REQUIRED_SDIST_FILES = {
    "AGENTS.md",
    "ARCHITECTURE.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "COMPATIBILITY.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "RELEASING.md",
    "ROADMAP.md",
    "SECURITY.md",
    "SUPPORT.md",
    "pyproject.toml",
    "scripts/_checks.py",
    "scripts/check_artifacts.py",
    "scripts/check_clean_install.py",
    "scripts/check_repository_independence.py",
    "scripts/check_registry_release.py",
    "scripts/check_secrets.py",
    "scripts/check_version.py",
    "scripts/check_workflows.py",
    "scripts/run_actionlint.py",
    "scripts/verify_release_trust.sh",
    "src/cometapi/__init__.py",
    "src/cometapi/_config.py",
    "src/cometapi/client.py",
    "src/cometapi/py.typed",
    "tests/__init__.py",
    "tests/conftest.py",
    "tests/live/__init__.py",
    "tests/live/test_live_smoke.py",
    "tests/test_client.py",
    "tests/test_clean_install.py",
    "tests/test_changelog_gate.py",
    "tests/test_contract.py",
    "tests/test_live_smoke_validation.py",
    "tests/test_release_documents.py",
    "tests/test_release_workflow.py",
    "tests/test_secrets.py",
    "tests/typing/constructor_contract.py",
}
OPTIONAL_SDIST_FILES = {".gitignore"}
FORBIDDEN_PARTS = {
    ".DS_Store",
    ".env",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
}


def _safe_path(name: str, source: Path) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise CheckError(f"{source.name}: unsafe archive path {name!r}")
    if any(part in FORBIDDEN_PARTS for part in path.parts) or path.suffix == ".pyc":
        raise CheckError(f"{source.name}: forbidden archive path {name!r}")
    return path


def check_metadata(
    raw: bytes,
    source: str,
    expected_version: str,
    expected_description: str,
) -> None:
    metadata = parse_metadata(raw, source)
    actual_version = normalize_version(str(metadata["Version"]))
    if actual_version != expected_version:
        raise CheckError(
            f"{source}: metadata version {actual_version} does not equal {expected_version}"
        )
    requirements = metadata.get_all("Requires-Dist", [])
    openai = [value.replace(" ", "") for value in requirements if value.startswith("openai")]
    if len(openai) != 1 or ">=2.45.0" not in openai[0] or "<3.0.0" not in openai[0]:
        raise CheckError(
            f"{source}: expected one openai>=2.45.0,<3.0.0 runtime requirement; got {requirements}"
        )
    unexpected = [value for value in requirements if not value.startswith("openai")]
    if unexpected:
        raise CheckError(f"{source}: unexpected direct runtime requirements: {unexpected}")
    if metadata.get("Author") != CANONICAL_AUTHOR:
        raise CheckError(f"{source}: expected Author: {CANONICAL_AUTHOR}")
    project_urls: dict[str, str] = {}
    for value in metadata.get_all("Project-URL", []):
        label, separator, url = value.partition(",")
        if separator:
            project_urls[label.strip()] = url.strip()
    for label, expected in CANONICAL_PROJECT_URLS.items():
        if project_urls.get(label) != expected:
            raise CheckError(f"{source}: expected Project-URL {label}, {expected}")
    description = metadata_description(metadata, source)
    if description != expected_description:
        raise CheckError(f"{source}: long description does not exactly match source README.md")
    violations = public_readme_release_violations(description)
    if violations:
        raise CheckError(
            f"{source}: long description contains publication-specific release text: "
            + ", ".join(sorted(set(violations)))
        )
    if not public_readme_has_install_command(description):
        raise CheckError(
            f"{source}: long description must contain the unpinned stable install command "
            f"{PUBLIC_README_INSTALL_COMMAND!r}"
        )


def check_wheel(path: Path, expected_version: str, expected_description: str) -> None:
    expected_fragment = f"cometapi-{expected_version}-"
    if expected_fragment not in path.name:
        raise CheckError(f"{path.name}: filename does not contain {expected_fragment!r}")
    with zipfile.ZipFile(path) as archive:
        paths = [_safe_path(info.filename, path) for info in archive.infolist()]
        names = {item.as_posix() for item in paths}
        if len(names) != len(paths):
            raise CheckError(f"{path.name}: duplicate normalized wheel member path")
        missing = REQUIRED_PACKAGE_FILES - names
        if missing:
            raise CheckError(f"{path.name}: missing package files: {sorted(missing)}")
        package_files = {
            name for name in names if name.startswith("cometapi/") and not name.endswith("/")
        }
        extra_package_files = package_files - REQUIRED_PACKAGE_FILES
        if extra_package_files:
            raise CheckError(
                f"{path.name}: unexpected package files: {sorted(extra_package_files)}"
            )
        unexpected = [
            name for name in names if not (name.startswith("cometapi/") or ".dist-info/" in name)
        ]
        if unexpected:
            raise CheckError(f"{path.name}: unexpected wheel members: {sorted(unexpected)}")
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise CheckError(f"{path.name}: expected exactly one .dist-info/METADATA")
        check_metadata(
            archive.read(metadata_names[0]),
            f"{path.name}:{metadata_names[0]}",
            expected_version,
            expected_description,
        )
        for source_name in ("cometapi/__init__.py", "cometapi/client.py"):
            text = archive.read(source_name).decode("utf-8")
            if re.search(r"\b(?:CometClient|AsyncCometClient)\b", text):
                raise CheckError(f"{path.name}:{source_name}: legacy public client name remains")


def _release_evidence_binding_violations(documents: dict[str, str]) -> list[str]:
    violations: list[str] = []
    evidence: dict[str, dict[str, ReleaseEvidenceIdentity]] = {}
    for name in ("ROADMAP.md", "RELEASING.md"):
        try:
            evidence[name] = release_evidence_identities(name, documents[name])
        except CheckError as exc:
            violations.append(str(exc))

    try:
        changelog_dates = changelog_release_dates(documents["CHANGELOG.md"])
    except CheckError as exc:
        violations.append(str(exc))
        changelog_dates = {}

    for name, identities in evidence.items():
        for version, identity in identities.items():
            changelog_date = changelog_dates.get(version)
            if changelog_date is None:
                violations.append(
                    f"{name}: release-evidence identity for {version} has no matching "
                    "canonical dated CHANGELOG.md release heading"
                )
            elif identity.date != changelog_date:
                violations.append(
                    f"{name}: release-evidence identity date for {version} is {identity.date}, "
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

    return violations


def check_sdist(path: Path, expected_version: str, expected_description: str) -> None:
    expected_root = f"cometapi-{expected_version}"
    if path.name != f"{expected_root}.tar.gz":
        raise CheckError(f"{path.name}: expected sdist filename {expected_root}.tar.gz")
    with tarfile.open(path, mode="r:gz") as archive:
        members = archive.getmembers()
        paths = [_safe_path(member.name, path) for member in members]
        normalized_paths = [item.as_posix() for item in paths]
        if len(set(normalized_paths)) != len(normalized_paths):
            raise CheckError(f"{path.name}: duplicate normalized sdist member path")
        if any(member.issym() or member.islnk() or member.isdev() for member in members):
            raise CheckError(f"{path.name}: links and device members are forbidden")
        if any(item.parts[0] != expected_root for item in paths):
            raise CheckError(f"{path.name}: every member must be below {expected_root}/")
        relative_members = {
            PurePosixPath(*item.parts[1:]).as_posix(): member
            for member, item in zip(members, paths, strict=True)
            if member.isfile()
        }
        relative_files = set(relative_members)
        missing = REQUIRED_SDIST_FILES - relative_files
        if missing:
            raise CheckError(f"{path.name}: missing sdist files: {sorted(missing)}")
        expected_files = REQUIRED_SDIST_FILES | OPTIONAL_SDIST_FILES | {"PKG-INFO"}
        unexpected = sorted(relative_files - expected_files)
        if unexpected:
            raise CheckError(f"{path.name}: unexpected sdist files: {unexpected}")
        parity_violations: list[str] = []
        for name in sorted(REQUIRED_SDIST_FILES):
            stream = archive.extractfile(relative_members[name])
            if stream is None:
                raise CheckError(f"{path.name}:{name}: cannot read required source member")
            try:
                source = (PROJECT_ROOT / name).read_bytes()
            except OSError as exc:
                raise CheckError(f"cannot read source member {name}: {exc}") from exc
            if stream.read() != source:
                parity_violations.append(
                    f"{path.name}:{name}: source-distribution member differs from source tree"
                )
        document_violations: list[str] = []
        documents: dict[str, str] = {}
        for name in SDIST_PUBLIC_DOCUMENTS:
            stream = archive.extractfile(relative_members[name])
            if stream is None:
                raise CheckError(f"{path.name}:{name}: cannot read public document")
            try:
                text = stream.read().decode("utf-8")
            except UnicodeDecodeError as exc:
                raise CheckError(f"{path.name}:{name}: document is not UTF-8: {exc}") from exc
            documents[name] = text
            violations = exact_release_version_violations(name, text, expected_version)
            document_violations.extend(
                f"{path.name}:{name}:{line}: contains {label}; {EXACT_RELEASE_VERSION_FIX}"
                for line, label in violations
            )
        evidence_violations = _release_evidence_binding_violations(documents)
        if parity_violations or document_violations or evidence_violations:
            raise CheckError(
                f"{path.name}: source-distribution source parity, document, and "
                "release-evidence violations:\n"
                + "\n".join(
                    f"- {violation}"
                    for violation in parity_violations + document_violations + evidence_violations
                )
            )
        metadata_members = [
            member for member in members if PurePosixPath(member.name).name == "PKG-INFO"
        ]
        if len(metadata_members) != 1:
            raise CheckError(f"{path.name}: expected exactly one PKG-INFO")
        stream = archive.extractfile(metadata_members[0])
        if stream is None:
            raise CheckError(f"{path.name}: cannot read PKG-INFO")
        check_metadata(
            stream.read(),
            f"{path.name}:PKG-INFO",
            expected_version,
            expected_description,
        )


def _artifacts(arguments: list[str]) -> list[Path]:
    paths = [Path(value).resolve() for value in arguments]
    if not paths:
        paths = sorted(Path("dist").glob("cometapi-*.whl")) + sorted(
            Path("dist").glob("cometapi-*.tar.gz")
        )
    if not paths or any(not path.is_file() for path in paths):
        raise CheckError("artifact arguments must name existing files")
    wheels = [path for path in paths if path.suffix == ".whl"]
    sdists = [path for path in paths if path.name.endswith(".tar.gz")]
    if len(wheels) != 1 or len(sdists) != 1 or len(paths) != 2:
        raise CheckError("expected exactly one wheel and one .tar.gz source distribution")
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs="*", help="wheel and sdist (defaults to dist/)")
    parser.add_argument("--expected-version", default=read_project_version())
    args = parser.parse_args()
    expected_version = normalize_version(args.expected_version)
    try:
        expected_description = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CheckError(f"cannot read source README.md: {exc}") from exc
    paths = _artifacts(args.artifacts)
    for path in paths:
        if path.suffix == ".whl":
            check_wheel(path, expected_version, expected_description)
        else:
            check_sdist(path, expected_version, expected_description)
        print(f"{sha256_file(path)}  {path}")
    print(f"artifact checks passed for cometapi {expected_version}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckError as error:
        raise SystemExit(f"artifact check failed: {error}") from error
