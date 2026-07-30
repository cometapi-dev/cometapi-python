"""Shared helpers for repository verification scripts."""

from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import unicodedata
from collections.abc import Iterable
from datetime import date
from email.message import Message
from email.parser import Parser
from itertools import pairwise
from pathlib import Path
from typing import NamedTuple, cast

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
PUBLIC_README_INSTALL_COMMAND = "python -m pip install cometapi"
PERSISTENT_DOCUMENTS = (
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
    "CLAUDE.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
)
SDIST_PUBLIC_DOCUMENTS = tuple(
    name for name in PERSISTENT_DOCUMENTS if not name.startswith(".github/") and name != "CLAUDE.md"
)
MUTABLE_PUBLISHED_VERSION_FIX = (
    "replace the exact patch with version-neutral 0.1.x guidance, query PyPI for current "
    "registry state, and keep exact released versions only in immutable historical evidence"
)
MUTABLE_PUBLISHED_VERSION_CATEGORY = "mutable latest/current published patch version"
_BARE_PATCH_VERSION = r"v?\d+\.\d+\.\d+(?:[-_.]?(?:a|alpha)[-_.]?\d+)?(?:\+[0-9A-Za-z.-]+)?"
_EXACT_PATCH_VERSION = rf"(?<![\w.])(?:cometapi\s*==\s*)?{_BARE_PATCH_VERSION}(?!\w|\.\d)"
_HTTP_URL = re.compile(r"https?://[^\s<>)\]]+", flags=re.IGNORECASE)
_HTML = re.compile(r"<!--.*?-->|<[^>]*>", flags=re.DOTALL)
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\((?:[^()]|\([^()]*\))*\)")
_VERSIONED_RELEASE_URL = re.compile(
    rf"https?://(?:"
    rf"pypi\.org/project/cometapi/(?P<pypi>{_BARE_PATCH_VERSION})"
    rf"|github\.com/cometapi-dev/cometapi-python/releases/tag/(?P<github>{_BARE_PATCH_VERSION})"
    rf")(?=$|[/#?\s<>\"')\]])",
    flags=re.IGNORECASE,
)
_CLAIM_TOKEN = re.compile(
    rf"(?P<version>{_EXACT_PATCH_VERSION})"
    r"|(?P<word>[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*)"
    r"|(?P<boundary>[.!?;](?=\s|$))"
    r"|(?P<separator>[,:|\u2013\u2014])",
    flags=re.IGNORECASE,
)
_CURRENT_WORDS = {"current", "currently", "latest", "newest", "now"}
_RELEASE_IDENTITY_WORDS = {"build", "distribution", "patch", "release", "version"}
_PUBLICATION_STATE_WORDS = {
    "available",
    "hosts",
    "lists",
    "offers",
    "published",
    "publishes",
    "released",
    "serves",
}
_HISTORICAL_ACTION_WORDS = {
    "accepted",
    "completed",
    "created",
    "executed",
    "failed",
    "passed",
    "published",
    "reached",
    "reserved",
    "verified",
}
_PRESENT_WORDS = {"are", "is", "now", "currently", "remains"}
_PAST_WORDS = {"had", "was", "were"}
_ATTRIBUTION_SKIP_WORDS = {
    "a",
    "an",
    "accepted",
    "active",
    "are",
    "as",
    "at",
    "available",
    "build",
    "candidate",
    "client",
    "cometapi",
    "completed",
    "current",
    "currently",
    "distribution",
    "exact",
    "for",
    "from",
    "has",
    "hosts",
    "immutable",
    "install",
    "installed",
    "is",
    "its",
    "latest",
    "library",
    "lists",
    "maintenance",
    "most",
    "newest",
    "now",
    "of",
    "offers",
    "on",
    "our",
    "package",
    "patch",
    "project",
    "public",
    "publicly",
    "published",
    "publishes",
    "recent",
    "registry",
    "release",
    "released",
    "repository",
    "sdk",
    "serves",
    "stable",
    "status",
    "supported",
    "that",
    "the",
    "these",
    "this",
    "those",
    "verified",
    "version",
    "was",
    "were",
}
_IMMUTABLE_CONTEXT_WORDS = {
    "commit",
    "completed",
    "digest",
    "evidence",
    "executed",
    "immutable",
    "recovery",
    "run",
    "tag",
    "workflow",
}
_CANONICAL_ATTRIBUTIONS = {
    "client",
    "cometapi",
    "cometapi-python",
    "library",
    "package",
    "project",
    "repository",
    "sdk",
    "this",
}
_KNOWN_THIRD_PARTY_ATTRIBUTIONS = {
    "httpx",
    "openai",
    "pyright",
    "pytest",
    "ruff",
    "twine",
    "uv",
}
_MUTABLE_LABEL_WORDS = {
    "current",
    "latest",
    "newest",
    "pypi",
}
PUBLIC_README_FORBIDDEN_PATTERNS = (
    (r"(?i)\bpending[\s-]+owner(?:ship|s)?\b", "pending owner identity"),
    (r"(?i)\bapproved\s+for\s+pypi\s+publication\b", "publication approval state"),
    (r"(?i)\b(?:candidate|unreleased|unpublished)\b", "unpublished release state"),
    (r"(?i)\bno\s+pypi\s+publication\b", "missing PyPI publication"),
    (r"(?i)\b(?:has\s+)?not\s+been\s+published\b", "unpublished release state"),
    (
        r"(?i)\bdo\s+not\s+treat\b[^\n]*\bcurrently\s+available\b",
        "temporary availability warning",
    ),
    (r"(?i)\blocal\s+candidate\b", "local-candidate narrative"),
    (r"(?i)\b0\.1\.\d+(?:a\d+)?\s+is\s+(?:available|approved)\b", "versioned release state"),
    (r"(?i)cometapi==\d+\.\d+\.\d+(?:a\d+)?", "version-pinned installation command"),
    (r"https://pypi\.org/project/cometapi/\d", "versioned PyPI release link"),
    (
        r"https://github\.com/cometapi-dev/cometapi-python/releases/tag/v\d",
        "versioned GitHub release link",
    ),
)


class CheckError(RuntimeError):
    """Raised when release-candidate evidence does not satisfy a local gate."""


class _ClaimToken(NamedTuple):
    kind: str
    value: str
    start: int
    end: int


def _visible_release_url_versions(value: str) -> str:
    """Expose release URL versions while preserving offsets and line numbers."""
    replacement = ["\n" if character == "\n" else " " for character in value]
    for match in _VERSIONED_RELEASE_URL.finditer(value):
        group = "pypi" if match.group("pypi") is not None else "github"
        start, end = match.span(group)
        marker = "immutableurl"
        marker_start = max(match.start(), start - len(marker) - 1)
        replacement[marker_start : marker_start + len(marker)] = marker
        replacement[start:end] = value[start:end]
    return "".join(replacement)


def _replace_html(match: re.Match[str]) -> str:
    """Discard markup without shifting line numbers used in diagnostics."""
    value = match.group(0)
    if value.startswith("<!--"):
        return "".join("\n" if character == "\n" else " " for character in value)
    return _visible_release_url_versions(value)


def _replace_markdown_link(match: re.Match[str]) -> str:
    """Keep link labels and exact release URL versions visible to the claim detector."""
    value = match.group(0)
    replacement = list(_visible_release_url_versions(value))
    label = match.group(1)
    label_start = value.find(label)
    label_end = label_start + len(label)
    replacement[label_start:label_end] = label
    return "".join(replacement)


def _claim_analysis_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", html.unescape(text))
    normalized = _HTML.sub(_replace_html, normalized)
    normalized = _MARKDOWN_LINK.sub(_replace_markdown_link, normalized)
    normalized = _VERSIONED_RELEASE_URL.sub(
        lambda match: _visible_release_url_versions(match.group(0)), normalized
    )
    normalized = re.sub(r"\\([`*_{}\[\]()#+.!|~>-])", r"\1", normalized)
    normalized = re.sub(r"[`*_~#\[\]{}]", " ", normalized)
    return normalized


def _claim_tokens(text: str) -> list[_ClaimToken]:
    url_spans = [(match.start(), match.end()) for match in _HTTP_URL.finditer(text)]
    tokens: list[_ClaimToken] = []
    for match in _CLAIM_TOKEN.finditer(text):
        kind = match.lastgroup
        if kind is None:
            continue
        if kind == "version" and any(
            start <= match.start() and match.end() <= end for start, end in url_spans
        ):
            continue
        tokens.append(_ClaimToken(kind, match.group(0).casefold(), match.start(), match.end()))
    return tokens


def _claim_window(tokens: list[_ClaimToken], version_index: int) -> list[_ClaimToken]:
    start = version_index
    words = 0
    while start > 0 and words < 32:
        previous = tokens[start - 1]
        if previous.kind == "boundary" or (
            previous.kind == "separator" and previous.value == "|" and words >= 1
        ):
            break
        start -= 1
        words += previous.kind in {"word", "version"}

    end = version_index + 1
    words = 0
    while end < len(tokens) and words < 32:
        following = tokens[end]
        if following.kind == "boundary" or (
            following.kind == "separator" and following.value == "|" and words >= 1
        ):
            break
        end += 1
        words += following.kind in {"word", "version"}
    return tokens[start:end]


def _word_values(tokens: Iterable[_ClaimToken]) -> list[str]:
    return [token.value for token in tokens if token.kind == "word"]


def _has_current_marker(words: list[str]) -> bool:
    return bool(_CURRENT_WORDS.intersection(words)) or any(
        first == "most" and second == "recent" for first, second in pairwise(words)
    )


def _valid_historical_snapshot(words: list[str]) -> bool:
    if not _has_current_marker(words):
        return False
    dated_indexes: list[int] = []
    for index, value in enumerate(words):
        try:
            date.fromisoformat(value)
        except ValueError:
            continue
        dated_indexes.append(index)
    if not dated_indexes:
        return False

    word_set = set(words)
    if {"historical", "snapshot"}.issubset(word_set):
        return True
    if not _PAST_WORDS.intersection(word_set) or _PRESENT_WORDS.intersection(word_set):
        return False
    if "evidence" in word_set and bool({"publication", "release"}.intersection(word_set)):
        return True
    for index in dated_indexes:
        prefix = words[index - 1] if index else ""
        if prefix in {"at", "on"} or words[max(0, index - 2) : index] == ["as", "of"]:
            return True
    return False


def _explicit_third_party_attribution(
    window: list[_ClaimToken], version_index: int, version_value: str
) -> bool:
    if version_value.startswith("cometapi"):
        return False
    words_before = _word_values(window[:version_index])
    words_after = _word_values(window[version_index + 1 :])

    candidates: list[str] = []
    if words_before and words_before[-1] in _KNOWN_THIRD_PARTY_ATTRIBUTIONS:
        candidates.append(words_before[-1])
    for index, word in enumerate(words_before):
        if word not in _KNOWN_THIRD_PARTY_ATTRIBUTIONS:
            continue
        trailing = words_before[index + 1 :]
        if any(
            value in _RELEASE_IDENTITY_WORDS | _CURRENT_WORDS | {"stable"} for value in trailing
        ):
            candidates.append(word)
    for index, word in enumerate(words_before[:-1]):
        if word in _RELEASE_IDENTITY_WORDS and words_before[index + 1] in {"for", "of"}:
            if index + 2 < len(words_before):
                candidates.append(words_before[index + 2])
    for index, word in enumerate(words_after[:-2]):
        if word in _RELEASE_IDENTITY_WORDS and words_after[index + 1] in {"for", "of"}:
            candidates.append(words_after[index + 2])

    attributed = next(
        (
            candidate
            for candidate in reversed(candidates)
            if candidate not in _ATTRIBUTION_SKIP_WORDS
        ),
        None,
    )
    return attributed is not None and attributed not in _CANONICAL_ATTRIBUTIONS


def _is_mutable_published_version_claim(window: list[_ClaimToken], version_index: int) -> bool:
    words = _word_values(window)
    version_value = window[version_index].value
    if _explicit_third_party_attribution(window, version_index, version_value):
        return False
    if _valid_historical_snapshot(words):
        return False

    word_set = set(words)
    has_identity = bool(_RELEASE_IDENTITY_WORDS.intersection(word_set))
    has_registry = bool({"pypi", "registry"}.intersection(word_set))
    has_publication = bool(_PUBLICATION_STATE_WORDS.intersection(word_set))
    has_current = _has_current_marker(words)
    immutable_release_url = "immutableurl" in word_set
    if (
        immutable_release_url
        and not has_current
        and not {"are", "now", "currently", "remains"}.intersection(word_set)
        and not {"available", "hosts", "lists", "offers", "publishes", "serves"}.intersection(
            word_set
        )
    ):
        return False
    immutable_history = bool(_IMMUTABLE_CONTEXT_WORDS.intersection(word_set)) and bool(
        _HISTORICAL_ACTION_WORDS.intersection(word_set)
    )
    if "status" in word_set and "released" in word_set:
        return True
    if has_current and has_identity:
        return True
    if has_current and ("stable" in word_set or has_registry):
        return True
    if has_current and "cometapi" in word_set:
        return True
    if has_current and has_publication and (has_registry or "cometapi" in word_set):
        return True

    # A dated, past-tense publication event is immutable evidence, not current state.
    publication_index = next(
        (index for index, word in enumerate(words) if word in _PUBLICATION_STATE_WORDS),
        -1,
    )
    past_index = next((index for index, word in enumerate(words) if word in _PAST_WORDS), -1)
    conjunction_after_past = any(
        word in {"and", "but", "so", "therefore"}
        for word in words[past_index + 1 : publication_index]
    )
    if (
        past_index >= 0
        and publication_index >= 0
        and past_index < publication_index
        and not _PRESENT_WORDS.intersection(words[past_index + 1 :])
        and not conjunction_after_past
    ):
        return False

    if immutable_history and not has_current:
        return False
    # Present-state publication forms do not need an explicit latest/current marker.
    if has_identity and has_publication:
        return True
    if has_registry and has_publication:
        return True
    if has_registry and "cometapi" in word_set:
        return True
    if "available" in word_set and "publicly" in word_set:
        return True
    if re.search(r"\b(?:pypi|registry)\s+(?:release|version|distribution)\b", " ".join(words)):
        return True
    return False


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
    try:
        message = Parser().parsestr(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise CheckError(f"{source}: invalid metadata: {exc}") from exc
    if message.get("Name") != DIST_NAME:
        raise CheckError(f"{source}: expected Name: {DIST_NAME!r}")
    if message.get("Version") is None:
        raise CheckError(f"{source}: missing Version metadata")
    return message


def metadata_description(message: Message, source: str) -> str:
    """Return the rendered long description from a distribution metadata message."""
    payload = message.get_payload()
    if not isinstance(payload, str) or not payload.strip():
        raise CheckError(f"{source}: missing long description metadata")
    return payload


def public_readme_release_violations(text: str) -> list[str]:
    """Return transient or version-specific release statements in public README text."""
    violations = [
        label for pattern, label in PUBLIC_README_FORBIDDEN_PATTERNS if re.search(pattern, text)
    ]
    violations.extend(label for _, label in mutable_published_version_claims(text))
    return violations


def mutable_published_version_claims(text: str) -> list[tuple[int, str]]:
    """Return line-numbered mutable exact-patch publication claims."""
    searchable = _claim_analysis_text(text)
    tokens = _claim_tokens(searchable)
    findings: set[tuple[int, str]] = set()
    for index, token in enumerate(tokens):
        if token.kind != "version":
            continue
        window = _claim_window(tokens, index)
        window_index = window.index(token)
        # Markdown tables often put the mutable state in the cell after the
        # version. Include that adjacent cell even though normal claim windows
        # stop at a pipe boundary.
        table_suffix: list[str] = []
        if index + 1 < len(tokens) and tokens[index + 1].kind == "separator":
            if tokens[index + 1].value == "|":
                suffix_end = index + 2
                while suffix_end < len(tokens):
                    following = tokens[suffix_end]
                    if following.kind == "boundary" or (
                        following.kind == "separator" and following.value == "|"
                    ):
                        break
                    suffix_end += 1
                table_suffix = _word_values(tokens[index + 2 : suffix_end])
        colon_label: list[str] = []
        if index > 0 and (
            (tokens[index - 1].kind == "separator" and tokens[index - 1].value == ":")
            or (tokens[index - 1].kind == "separator" and tokens[index - 1].value == "|")
        ):
            label_start = index - 2
            while label_start >= 0 and tokens[label_start].kind != "boundary":
                if tokens[label_start].kind == "separator" and tokens[label_start].value == "|":
                    break
                label_start -= 1
            colon_label = _word_values(tokens[label_start + 1 : index - 1])[-8:]
        prefix = searchable[max(0, token.start - 160) : token.start]
        parenthetical = re.search(r"([^.!?;]{0,100})\(([^()]*)\)\s*:\s*$", prefix)
        if parenthetical is not None:
            colon_label.extend(
                re.findall(
                    r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*",
                    " ".join(parenthetical.groups()).casefold(),
                )[-12:]
            )
        label_words = set(colon_label)
        mutable_label = (
            bool(label_words.intersection(_MUTABLE_LABEL_WORDS))
            or (
                bool(label_words.intersection({"public", "stable"}))
                and bool(label_words.intersection(_RELEASE_IDENTITY_WORDS))
            )
            or bool(label_words.intersection({"released", "published"}))
        )
        mutable_table_suffix = bool(
            set(table_suffix).intersection(
                _CURRENT_WORDS | _PUBLICATION_STATE_WORDS | {"stable", "status"}
            )
        )
        attributed_label = (
            bool(label_words.intersection(_KNOWN_THIRD_PARTY_ATTRIBUTIONS))
            and "cometapi" not in label_words
        )
        window_words = _word_values(window)
        recovery_mapping = (
            "remains" in window_words
            and bool({"artifact", "identity", "recovery"}.intersection(set(window_words)))
            and not _has_current_marker(window_words)
            and "but" not in window_words
        )
        if (
            ((mutable_label or mutable_table_suffix) and not attributed_label)
            or _is_mutable_published_version_claim(window, window_index)
        ) and not recovery_mapping:
            line = searchable.count("\n", 0, token.start) + 1
            findings.add((line, MUTABLE_PUBLISHED_VERSION_CATEGORY))
    return sorted(findings)


def public_readme_has_install_command(text: str) -> bool:
    """Return whether the public README contains the exact unpinned install command."""
    return any(line.strip() == PUBLIC_README_INSTALL_COMMAND for line in text.splitlines())


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
