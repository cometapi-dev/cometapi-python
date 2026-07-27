"""Shared helpers for repository verification scripts."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections.abc import Iterable
from email.message import Message
from pathlib import Path
from typing import cast

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_NAME = "cometapi"
CANONICAL_AUTHOR = "CometAPI"
CANONICAL_COPYRIGHT = "Copyright (c) 2026 CometAPI"
CANONICAL_REPOSITORY = "https://github.com/cometapi-dev/cometapi-python"
CANONICAL_SUPPORT = "support@cometapi.com"
CANONICAL_SECURITY = f"{CANONICAL_REPOSITORY}/security/advisories/new"
CANONICAL_PROJECT_URLS = {
    "Homepage": "https://www.cometapi.com",
    "Documentation": "https://apidoc.cometapi.com/",
    "Repository": CANONICAL_REPOSITORY,
    "Issues": f"{CANONICAL_REPOSITORY}/issues",
    "Support": f"{CANONICAL_REPOSITORY}/blob/main/SUPPORT.md",
    "Security": CANONICAL_SECURITY,
}


class CheckError(RuntimeError):
    """Raised when release-candidate evidence does not satisfy a local gate."""


def read_project_metadata(root: Path = PROJECT_ROOT) -> dict[str, object]:
    """Return the parsed PEP 621 project table."""
    path = root / "pyproject.toml"
    try:
        document = cast(dict[str, object], tomllib.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise CheckError(f"cannot read {path.name}: {exc}") from exc
    project = document.get("project")
    if not isinstance(project, dict):
        raise CheckError("pyproject.toml has no [project] table")
    return cast(dict[str, object], project)


def read_project_version(root: Path = PROJECT_ROOT) -> str:
    """Return the static PEP 621 project version."""
    version = read_project_metadata(root).get("version")
    if not isinstance(version, str):
        raise CheckError("[project].version must be a static string")
    return version


def normalize_version(value: str) -> str:
    """Normalize the supported SemVer/PEP 440 alpha spellings to PEP 440."""
    value = value.strip().removeprefix("v")
    match = re.fullmatch(
        r"(?P<base>\d+\.\d+\.\d+)(?:[-_.]?(?:a|alpha)[-_.]?(?P<alpha>\d+))?",
        value,
        flags=re.IGNORECASE,
    )
    if match is None:
        raise CheckError(f"unsupported release version: {value!r}")
    alpha = match.group("alpha")
    return match.group("base") if alpha is None else f"{match.group('base')}a{int(alpha)}"


def read_release_manifest(root: Path = PROJECT_ROOT) -> str:
    """Read the root package version from the release-please manifest."""
    path = root / ".release-please-manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckError(f"cannot read {path.name}: {exc}") from exc
    version = data.get(".")
    if not isinstance(version, str):
        raise CheckError(".release-please-manifest.json must contain a string version for '.'")
    return version


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_metadata(raw: bytes, source: str) -> Message:
    """Parse package core metadata and require its identity fields."""
    message = Message()
    text = raw.decode("utf-8")
    for line in text.splitlines():
        if not line.strip():
            break
        if line[0].isspace():
            current = message.get_payload()
            message.set_payload(f"{current}\n{line}" if current else line)
            continue
        name, separator, value = line.partition(":")
        if separator:
            message[name] = value.strip()
    if message.get("Name") != DIST_NAME:
        raise CheckError(f"{source}: expected Name: {DIST_NAME!r}")
    if message.get("Version") is None:
        raise CheckError(f"{source}: missing Version metadata")
    return message


def require_equal_versions(items: Iterable[tuple[str, str]]) -> str:
    """Require all named version values to normalize to the same version."""
    normalized = [(name, normalize_version(value)) for name, value in items]
    if not normalized:
        raise CheckError("no versions were supplied for comparison")
    expected = normalized[0][1]
    mismatches = [f"{name}={value}" for name, value in normalized if value != expected]
    if mismatches:
        raise CheckError(
            f"version disagreement; expected {expected}; mismatches: {', '.join(mismatches)}"
        )
    return expected
