"""Shared helpers for repository verification scripts."""

from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import unicodedata
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from email.message import Message
from email.parser import Parser
from html.parser import HTMLParser
from pathlib import Path
from typing import cast
from urllib.parse import quote, unquote

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_NAME = "cometapi"
CANONICAL_ACTIVE_MODEL = "gpt-5.6-sol"
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
EXACT_RELEASE_VERSION_FIX = (
    "replace the exact patch with version-neutral 0.1.x guidance, or move complete "
    "immutable history into a validated release-evidence block in ROADMAP.md or "
    "RELEASING.md; query PyPI when current registry state is required"
)
EXACT_RELEASE_VERSION_CATEGORY = (
    "exact CometAPI patch/recovery version outside immutable release evidence"
)
RELEASE_EVIDENCE_DOCUMENTS = {"ROADMAP.md", "RELEASING.md"}
RELEASE_EVIDENCE_MARKER = re.compile(
    r"(?m)^<!-- cometapi-release-evidence:"
    r"(?P<kind>start|end) version=(?P<version>\S+) date=(?P<date>\d{4}-\d{2}-\d{2}) -->$"
)
RELEASE_EVIDENCE_IDENTITY = re.compile(
    r"^<!-- cometapi-release-identity "
    r"tag=(?P<tag>\S+) "
    r"commit=(?P<commit>[0-9a-f]{40}) "
    r"workflow-run=(?P<run>[1-9]\d*) "
    r"wheel-sha256=(?P<wheel>[0-9a-f]{64}) "
    r"sdist-sha256=(?P<sdist>[0-9a-f]{64}) -->$"
)
_ANY_RELEASE_EVIDENCE_IDENTITY = re.compile(r"(?m)^.*cometapi-release-identity.*$")
_ANY_RELEASE_EVIDENCE_WORKFLOW_REFERENCE = re.compile(
    r"(?m)^.*cometapi-release-workflow-reference.*$"
)
_ANY_RELEASE_EVIDENCE_MARKER = re.compile(r"(?m)^.*cometapi-release-evidence:.*$")
_EXACT_VERSION = (
    r"(?:v\s*)?\d+\s*\.\s*\d+\s*\.\s*\d+"
    r"(?:\s*[-_.]?\s*(?:a|alpha|b|beta|rc)\s*[-_.]?\s*\d+)?"
    r"(?:\s*(?:\+|%2b)\s*[0-9a-z][0-9a-z.-]*)?"
)
_EXACT_VERSION_PATTERN = re.compile(
    rf"(?<![\w.])(?P<version>{_EXACT_VERSION})(?!\w|\s*\.\s*\d)",
    re.IGNORECASE,
)
_THIRD_PARTY_OWNER = (
    r"(?:openai|httpx|ruff|pyright|pytest|python|node(?:\.js)?|twine|uv|actionlint|"
    r"release[\s-]+please|pypi[\s-]+publisher|"
    r"actions[ /-](?:checkout|download-artifact|setup-python|upload-artifact)|"
    r"googleapis/release-please-action|pypa/gh-action-pypi-publish|pypi-attestations)"
)
_THIRD_PARTY_RELEASE_COMPONENT = (
    rf"(?:{_THIRD_PARTY_OWNER}|minimum(?:\s+supported)?(?:\s+openai)?|"
    rf"latest\s+available\s+below|pypi\s+publisher|release\s+please)"
)
_DEPENDENCY_RANGE = re.compile(
    rf"(?i)(?<![\w.-])(?P<owner>[a-z][a-z0-9_.-]*(?:\[[a-z0-9_.-]+\])?)\s*"
    rf"(?P<spec>(?:==|~=|!=|<=|>=|<|>)\s*{_EXACT_VERSION}"
    rf"(?:\s*,\s*(?:==|~=|!=|<=|>=|<|>)\s*{_EXACT_VERSION})*)"
)
_THIRD_PARTY_VERSION_URL = re.compile(
    rf"(?i)(?:"
    rf"https://pypi\.org/project/(?!cometapi/)[^/\s)]+/(?P<pypi>{_EXACT_VERSION})/|"
    rf"https://github\.com/(?!cometapi-dev/cometapi-python/releases/tag/)"
    rf"[^/\s)]+/[^/\s)]+/releases/tag/(?P<github>{_EXACT_VERSION})"
    rf")"
)
_RAW_HTML_MARKUP = re.compile(r"<!--.*?-->|</?[A-Za-z][^>]*>", re.DOTALL)
_DECODED_HTML_TAG = re.compile(r"</?[A-Za-z][^>\n]*>")
_MARKDOWN_LINK = re.compile(
    r"\[(?P<label>(?:\\.|[^\]])*)\]"
    r"\((?P<target>(?:\\.|[^()\s]|\((?:\\.|[^()])*\))*)\)"
)
_FIRST_PARTY_MARKDOWN_TARGET = re.compile(
    rf"(?i)\A<?(?:"
    rf"{re.escape(CANONICAL_REPOSITORY)}|"
    r"https://pypi\.org/project/cometapi|"
    r"https://img\.shields\.io/pypi/v/cometapi"
    r")(?=$|[/?#>])"
)
_HTTP_URL = re.compile(r"https?://[^\s<>)\]]+", re.IGNORECASE)
_RECOVERY_TAGS = {"0.1.0a1": "v0.1.0-alpha.1+recovery.1"}
_FULL_COMMIT = re.compile(r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])", re.IGNORECASE)
_ACTIONS_PREFIX = f"{CANONICAL_REPOSITORY}/actions/runs/"
_ACTIONS_PATH = re.compile(
    r"actions/runs/(?P<run>\d+)(?:/attempts/(?P<attempt>\d+))?",
    re.IGNORECASE,
)
_CANONICAL_ACTIONS_DESTINATION = re.compile(
    rf"{re.escape(_ACTIONS_PREFIX)}(?P<run>[1-9]\d*)"
    r"(?:/attempts/(?P<attempt>[1-9]\d*))?"
)
_BARE_ACTIONS_DESTINATION = re.compile(
    rf"(?P<url>{re.escape(_ACTIONS_PREFIX)}[1-9]\d*(?:/attempts/[1-9]\d*)?)"
)
_WHEEL_DIGEST = re.compile(
    r"\bwheel\s+sha256\b[^0-9a-f]{0,96}(?P<digest>[0-9a-f]{64})(?![0-9a-f])",
    re.IGNORECASE | re.DOTALL,
)
_SDIST_DIGEST = re.compile(
    r"\b(?:source(?:[- ]distribution)?|(?:public\s+)?sdist)\b"
    r"(?:\s+(?:sha256|digest)|\s+has\s+sha256)\b"
    r"[^0-9a-f]{0,96}(?P<digest>[0-9a-f]{64})(?![0-9a-f])",
    re.IGNORECASE | re.DOTALL,
)
_CANONICAL_OWNER = r"(?<![\w.-])cometapi(?:-python)?(?![\w-])"
_CANONICAL_COMPONENT_BINDING = re.compile(
    rf"(?i){_CANONICAL_OWNER}"
    r"(?:[ \t]+(?:python[ \t]+)?(?:sdk|package|project|library|distribution|client))?"
    r"[ \t]+(?:pins|requires|supports|uses)[ \t]+$"
)
_MARKDOWN_FENCE_OPEN = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})")
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


class _ActionsAnchorParser(HTMLParser):
    """Collect canonical destinations from unambiguous raw-HTML anchors."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.destinations: Counter[tuple[str, str | None]] = Counter()
        self.anchor_depth = 0

    def _handle_anchor(
        self,
        attrs: list[tuple[str, str | None]],
        *,
        self_closing: bool,
    ) -> None:
        hrefs = [value for name, value in attrs if name.casefold() == "href"]
        if len(hrefs) == 1 and hrefs[0] is not None:
            destination = _CANONICAL_ACTIONS_DESTINATION.fullmatch(hrefs[0])
            if destination is not None:
                self.destinations[(destination.group("run"), destination.group("attempt"))] += 1
        del self_closing

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "a":
            self._handle_anchor(attrs, self_closing=False)
            self.anchor_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a":
            self.anchor_depth = max(0, self.anchor_depth - 1)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "a":
            self._handle_anchor(attrs, self_closing=True)


def _bare_actions_destinations(text: str) -> Counter[tuple[str, str | None]]:
    """Collect canonical visible URLs with unambiguous prose boundaries."""
    destinations: Counter[tuple[str, str | None]] = Counter()
    for match in _BARE_ACTIONS_DESTINATION.finditer(text):
        line_prefix = text[text.rfind("\n", 0, match.start()) + 1 : match.start()]
        prefix_token = line_prefix.rsplit(maxsplit=1)[-1] if line_prefix.split() else ""
        if re.search(r"(?i)(?:[a-z][a-z0-9+.-]*:|[?#=&])", prefix_token):
            continue
        before = text[match.start() - 1] if match.start() else ""
        after = text[match.end() :]
        if before and not (before.isspace() or before in "([{<"):
            continue
        if before in "([{<" and match.start() > 1:
            before_opener = text[match.start() - 2]
            if not (before_opener.isspace() or before_opener in "([{<"):
                continue
        if after:
            if after[0].isspace() or after[0] in ")]}>\"'":
                pass
            elif after[0] in ".,;:!?" and (len(after) == 1 or after[1].isspace()):
                pass
            else:
                continue
        destination = _CANONICAL_ACTIONS_DESTINATION.fullmatch(match.group("url"))
        assert destination is not None
        destinations[(destination.group("run"), destination.group("attempt"))] += 1
    return destinations


@dataclass(frozen=True)
class ReleaseEvidenceIdentity:
    """Machine-readable identity for one immutable historical release."""

    version: str
    date: str
    tag: str
    commit: str
    workflow_run: str
    wheel_sha256: str
    sdist_sha256: str


def read_project_metadata(root: Path = PROJECT_ROOT) -> dict[str, object]:
    """Return the parsed PEP 621 project table."""
    path = root / "pyproject.toml"
    try:
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib
    except ImportError as exc:
        raise CheckError("TOML parsing requires tomli on Python 3.10") from exc
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


def _preserve_version_characters(match: re.Match[str]) -> str:
    return "".join(
        value if value == "\n" or value.isdigit() or value in ".%" else " "
        for value in match.group()
    )


def _visible_markdown_link_text(match: re.Match[str]) -> str:
    """Keep first-party destinations visible to the exact-version scanner."""
    label = match.group("label")
    target = match.group("target")
    if _FIRST_PARTY_MARKDOWN_TARGET.match(target) is not None:
        return f"{label} {target}"
    return label


def _normalized_document_text(text: str) -> str:
    normalized = unquote(html.unescape(unicodedata.normalize("NFKC", text)))
    while _MARKDOWN_LINK.search(normalized) is not None:
        normalized = _MARKDOWN_LINK.sub(_visible_markdown_link_text, normalized)
    normalized = _RAW_HTML_MARKUP.sub(_preserve_version_characters, normalized)
    normalized = _DECODED_HTML_TAG.sub(_preserve_version_characters, normalized)
    normalized = normalized.replace("<!--", "    ").replace("-->", "   ")
    without_ignorable_formatting = "".join(
        ""
        if unicodedata.category(value) in {"Cf", "Mn"} and not unicodedata.combining(value)
        else value
        for value in normalized
    )
    unescaped = re.sub(r"\\([.`*_~])", r"\1", without_ignorable_formatting)
    return re.sub(r"[*_`~]+", "", unescaped)


def _markdown_fence_spans(text: str) -> list[tuple[int, int]]:
    """Return block-code fence spans while preserving source offsets."""
    spans: list[tuple[int, int]] = []
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
    return spans


def _inside_spans(position: int, spans: Iterable[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in spans)


def _audited_component_version_spans(text: str) -> set[tuple[int, int]]:
    """Return versions directly and unambiguously owned by an audited component."""
    spans: set[tuple[int, int]] = set()
    prefix = re.compile(
        rf"(?i)(?<![\w.-]){_THIRD_PARTY_RELEASE_COMPONENT}(?![\w-]|\.(?=\w))"
        rf"(?:[ \t]+(?:version|release))?[ \t]*[:=@]?[ \t]*"
        rf"(?P<version>{_EXACT_VERSION})"
    )
    for match in prefix.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end("version"))
        if line_end == -1:
            line_end = len(text)
        prefix_clause = text[line_start : match.start()]
        suffix_clause = text[match.end("version") : line_end]
        suffix_canonical = re.search(rf"(?i){_CANONICAL_OWNER}", suffix_clause)
        suffix_sdk = re.search(r"(?i)\b(?:current|latest)\s+python\s+sdk\b", suffix_clause)
        dependabot_row = "| dependabot " in prefix_clause.casefold()
        suffix_binds_version = (suffix_canonical is not None and not dependabot_row) or (
            suffix_sdk is not None
        )
        if suffix_binds_version:
            continue
        canonical_before = re.search(rf"(?i){_CANONICAL_OWNER}", prefix_clause)
        if canonical_before is not None and (
            _CANONICAL_COMPONENT_BINDING.search(prefix_clause) is None
            and "placeholder:" not in prefix_clause.casefold()
            and "| dependabot " not in prefix_clause.casefold()
        ):
            continue
        spans.add(match.span("version"))
        tail = text[match.end("version") : match.end("version") + 64]
        for following in re.finditer(
            rf"(?i)\s+(?:to|through|->)\s*(?P<version>{_EXACT_VERSION})",
            tail,
        ):
            start, end = following.span("version")
            spans.add((match.end("version") + start, match.end("version") + end))

    verb_bound = re.compile(
        rf"(?i)(?:\b(?:pins?|uses?|requires?|supports?)[ \t]+(?:the[ \t]+)?"
        rf"(?:reviewed[ \t]+upstream[ \t]+)?{_THIRD_PARTY_RELEASE_COMPONENT}|"
        rf"{_THIRD_PARTY_RELEASE_COMPONENT}(?![\w-]|\.(?=\w))[ \t]+"
        rf"(?:pins?|uses?|requires?|supports?))[ \t]+(?P<version>{_EXACT_VERSION})"
    )
    for match in verb_bound.finditer(text):
        spans.add(match.span("version"))

    suffix = re.compile(
        rf"(?i)(?P<version>{_EXACT_VERSION})\s*(?:"
        rf"(?:for|of)\s+{_THIRD_PARTY_RELEASE_COMPONENT}(?![\w-]|\.(?=\w))"
        rf"(?:\s+(?:release|version))?|"
        rf"is\s+(?:the\s+)?(?:current\s+|latest\s+|stable\s+)?"
        rf"{_THIRD_PARTY_RELEASE_COMPONENT}(?![\w-]|\.(?=\w))"
        rf"(?:\s+(?:release|version))?"
        rf")"
    )
    for match in suffix.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        if line_end == -1:
            line_end = len(text)
        if (
            re.search(
                rf"(?i){_CANONICAL_OWNER}",
                text[line_start:line_end],
            )
            is None
        ):
            spans.add(match.span("version"))
    return spans


def _third_party_version_spans(text: str) -> set[tuple[int, int]]:
    """Return exact-version spans structurally bound to an audited third party."""
    spans: set[tuple[int, int]] = set()
    for match in _DEPENDENCY_RANGE.finditer(text):
        owner = match.group("owner").casefold()
        bare_owner = owner.split("[", 1)[0]
        if "cometapi" in owner or bare_owner in {
            "client",
            "distribution",
            "library",
            "package",
            "project",
            "release",
            "sdk",
            "version",
        }:
            continue
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        if line_end == -1:
            line_end = len(text)
        owner_prefix = text[line_start : match.start()]
        owner_suffix = text[match.end() : line_end]
        suffix_canonical = re.search(rf"(?i){_CANONICAL_OWNER}", owner_suffix)
        if suffix_canonical is not None and "| dependabot " not in owner_prefix.casefold():
            continue
        if re.fullmatch(_THIRD_PARTY_OWNER, bare_owner, re.IGNORECASE) is None:
            if re.search(rf"(?i){_CANONICAL_OWNER}", owner_prefix):
                continue
        spec_start = match.start("spec")
        for version in _EXACT_VERSION_PATTERN.finditer(match.group("spec")):
            start, end = version.span("version")
            spans.add((spec_start + start, spec_start + end))
    for match in _THIRD_PARTY_VERSION_URL.finditer(text):
        group = "pypi" if match.group("pypi") is not None else "github"
        spans.add(match.span(group))
    spans.update(_audited_component_version_spans(text))
    return spans


def _first_party_version_spans(text: str) -> list[tuple[int, int]]:
    third_party = _third_party_version_spans(text)
    return [
        match.span("version")
        for match in _EXACT_VERSION_PATTERN.finditer(text)
        if match.span("version") not in third_party
        and (match.start("version") + 1, match.end("version")) not in third_party
    ]


def _blank_span(text: str, start: int, end: int) -> str:
    blanked = "".join("\n" if value == "\n" else " " for value in text[start:end])
    return text[:start] + blanked + text[end:]


def _canonical_release_tag(version: str) -> str:
    normalized = normalize_version(version)
    recovery = _RECOVERY_TAGS.get(normalized)
    if recovery is not None:
        return recovery
    alpha = re.fullmatch(r"(?P<base>\d+\.\d+\.\d+)a(?P<number>\d+)", normalized)
    if alpha is not None:
        return f"v{alpha.group('base')}-alpha.{alpha.group('number')}"
    return f"v{normalized}"


def _identity_violations(
    body: str,
    version: str,
    marker_date: str,
    line: int,
    evidence_versions: set[str],
) -> tuple[ReleaseEvidenceIdentity | None, list[tuple[int, str]]]:
    nonempty = [value.strip() for value in body.splitlines() if value.strip()]
    identity_lines = [value for value in nonempty if "cometapi-release-identity" in value]
    if len(identity_lines) != 1 or not nonempty or nonempty[0] != identity_lines[0]:
        return None, [
            (
                line,
                f"release-evidence block for {version} must begin with exactly one "
                "canonical release-identity marker",
            )
        ]
    match = RELEASE_EVIDENCE_IDENTITY.fullmatch(identity_lines[0])
    if match is None:
        return None, [
            (line, f"release-evidence block for {version} has malformed release identity")
        ]
    identity = ReleaseEvidenceIdentity(
        version=version,
        date=marker_date,
        tag=match.group("tag"),
        commit=match.group("commit"),
        workflow_run=match.group("run"),
        wheel_sha256=match.group("wheel"),
        sdist_sha256=match.group("sdist"),
    )
    findings: list[tuple[int, str]] = []
    if _ANY_RELEASE_EVIDENCE_WORKFLOW_REFERENCE.search(body) is not None:
        findings.append(
            (
                line,
                f"release-evidence block for {version} contains an obsolete workflow-reference "
                "marker; remove it and keep preparatory workflow history outside the immutable "
                "evidence block",
            )
        )
    expected_tag = _canonical_release_tag(version)
    if identity.tag != expected_tag:
        findings.append(
            (line, f"release-evidence identity for {version} must use canonical tag {expected_tag}")
        )
    if identity.wheel_sha256 == identity.sdist_sha256:
        findings.append(
            (line, f"release-evidence identity for {version} reuses one artifact digest")
        )

    encoded_tag = quote(identity.tag, safe="v.-")
    exact_requirements = {
        "canonical release tag": re.compile(
            rf"(?<![\w.]){re.escape(identity.tag)}(?![\w.])|{re.escape(encoded_tag)}",
            re.IGNORECASE,
        ),
        "canonical GitHub Release URL": re.compile(
            rf"{re.escape(CANONICAL_REPOSITORY)}/releases/tag/"
            rf"(?:{re.escape(identity.tag)}|{re.escape(encoded_tag)})",
            re.IGNORECASE,
        ),
        "canonical PyPI release URL": re.compile(
            rf"https://pypi\.org/project/cometapi/{re.escape(version)}/",
            re.IGNORECASE,
        ),
        "exact release commit": re.compile(re.escape(identity.commit), re.IGNORECASE),
        "exact wheel SHA256": re.compile(
            rf"\bwheel\s+sha256\b[^0-9a-f]{{0,96}}{identity.wheel_sha256}(?![0-9a-f])",
            re.IGNORECASE | re.DOTALL,
        ),
        "exact source-distribution SHA256": re.compile(
            rf"\b(?:source(?:[- ]distribution)?|sdist)\s+sha256\b"
            rf"[^0-9a-f]{{0,96}}{identity.sdist_sha256}(?![0-9a-f])",
            re.IGNORECASE | re.DOTALL,
        ),
    }
    prose = "\n".join(nonempty[1:])
    for label, pattern in exact_requirements.items():
        if pattern.search(prose) is None:
            findings.append(
                (line, f"release-evidence block for {version} is missing {label} from its identity")
            )

    actions_findings, canonical_workflow_count = _canonical_actions_run_violations(
        body,
        version,
        identity.workflow_run,
        line,
    )
    findings.extend(actions_findings)
    if canonical_workflow_count == 0:
        findings.append(
            (
                line,
                f"release-evidence block for {version} is missing exact release workflow URL "
                "from its identity",
            )
        )

    release_commit_values: set[str] = set()
    for commit in _FULL_COMMIT.finditer(prose):
        line_start = prose.rfind("\n", 0, commit.start()) + 1
        prior_line_start = prose.rfind("\n", 0, max(0, line_start - 1)) + 1
        line_end = prose.find("\n", commit.end())
        if line_end == -1:
            line_end = len(prose)
        context = prose[prior_line_start:line_end]
        before_commit = context[: commit.start() - prior_line_start]
        if re.search(
            r"(?i)\b(?:"
            r"(?:release|publish(?:ed|ing)?|publication|registry)[ -]+(?:commit|sha)"
            r"|exact[ -]+commit"
            r"|tag[ -]+target"
            r")\b[^\n]{0,64}$",
            before_commit,
        ):
            release_commit_values.add(commit.group(0).lower())
    labeled_values = (
        ("release commit", release_commit_values, identity.commit),
        (
            "wheel SHA256",
            {
                match.group("digest").lower()
                for match in re.finditer(
                    r"(?i)\bwheel\s+(?:sha256|digest|checksum|hash)\b[^0-9a-f]{0,96}"
                    r"(?P<digest>[0-9a-f]{64})(?![0-9a-f])",
                    prose,
                    re.DOTALL,
                )
            },
            identity.wheel_sha256,
        ),
        (
            "source-distribution SHA256",
            {
                match.group("digest").lower()
                for match in re.finditer(
                    r"(?i)\b(?:source(?:[- ]distribution)?|(?:public[ -]+)?sdist)\b"
                    r"(?:[ -]+(?:sha256|digest|checksum|hash)|[ -]+has[ -]+sha256)\b"
                    r"[^0-9a-f]{0,96}(?P<digest>[0-9a-f]{64})(?![0-9a-f])",
                    prose,
                    re.DOTALL,
                )
            },
            identity.sdist_sha256,
        ),
    )
    for label, values, expected in labeled_values:
        unexpected = values - {expected.lower()}
        if unexpected:
            findings.append(
                (
                    line,
                    f"release-evidence block for {version} contains {label} values that "
                    "contradict its release-identity marker",
                )
            )
    canonical_identity_urls = (
        re.compile(
            rf"{re.escape(CANONICAL_REPOSITORY)}/releases/tag/(?P<tag>[^\s)]+)",
            re.IGNORECASE,
        ),
        re.compile(
            r"https://pypi\.org/project/cometapi/(?P<tag>[^\s/)]+)/",
            re.IGNORECASE,
        ),
    )
    allowed_url_values = {
        identity.tag.casefold(),
        encoded_tag.casefold(),
        version.casefold(),
    }
    for pattern in canonical_identity_urls:
        for url in pattern.finditer(prose):
            if url.group("tag").casefold() not in allowed_url_values:
                findings.append(
                    (
                        line,
                        f"release-evidence block for {version} contains a canonical release URL "
                        "that contradicts its release-identity marker",
                    )
                )
    expected_versions = {version, identity.tag, quote(identity.tag, safe="v.-")}
    for start, end in _first_party_version_spans(prose):
        value = re.sub(r"\s+", "", prose[start:end]).lower()
        if value not in {item.lower() for item in expected_versions} and not (
            version == "0.1.0"
            and value == "0.1.0a1"
            and "cdn\npropagation" in prose[max(0, start - 96) : end + 96].casefold()
        ):
            findings.append(
                (
                    line,
                    f"release-evidence block for {version} contains unrelated "
                    f"exact version {value!r}",
                )
            )
    return identity, findings


def _canonical_actions_run_violations(
    body: str,
    version: str,
    expected_run: str,
    line: int,
) -> tuple[list[tuple[int, str]], int]:
    """Require every Actions URL in immutable evidence to name one canonical run."""
    findings: list[tuple[int, str]] = []
    structural_control_counts = Counter(character for character in body if character in "\n\r\t")
    encoded_control = re.compile(r"(?i)(?:%0[0-9a-f]|&#(?:x0*[0-9a-f]|0*(?:9|10|11|12|13));?)")

    def has_obfuscated_control(value: str) -> bool:
        controls = Counter(character for character in value if character in "\n\r\t")
        if encoded_control.search(value) is not None or any(
            controls[character] > structural_control_counts[character] for character in "\n\r\t"
        ):
            return True
        return any(
            character == "\ufffd"
            or unicodedata.category(character) in {"Zl", "Zp"}
            or (unicodedata.category(character) == "Mn" and unicodedata.combining(character) == 0)
            or (
                unicodedata.category(character) in {"Cc", "Cf"}
                and character not in {"\n", "\r", "\t"}
            )
            or unicodedata.bidirectional(character)
            in {"LRE", "RLE", "LRO", "RLO", "PDF", "LRI", "RLI", "FSI", "PDI"}
            for character in value
        )

    direct = unicodedata.normalize("NFKC", body)
    variants = [body]
    if direct != body:
        variants.append(direct)
    control_obfuscation = has_obfuscated_control(direct)
    converged = False
    for _ in range(len(direct) + 1):
        previous = variants[-1]
        decoded = unicodedata.normalize("NFKC", html.unescape(previous))
        control_obfuscation = control_obfuscation or has_obfuscated_control(decoded)
        decoded = unicodedata.normalize("NFKC", unquote(decoded))
        control_obfuscation = control_obfuscation or has_obfuscated_control(decoded)
        decoded = re.sub(r"\\([/\\.:?&=%#])", r"\1", decoded)
        decoded = decoded.replace("\t", "")
        decoded = re.sub(
            r"(?i)(https?:[^\s<>)\]]*)\\([^\s<>)\]]*)",
            lambda match: match.group(0).replace("\\", "/"),
            decoded,
        )
        if decoded == previous:
            converged = True
            break
        variants.append(decoded)

    try:
        from markdown_it import MarkdownIt
    except ImportError as exc:
        raise CheckError("release-evidence Markdown validation requires markdown-it-py") from exc

    def rendered_bindings(
        source: str,
    ) -> tuple[list[re.Match[str]], list[tuple[str, str | None]], list[int]]:
        paths = list(_ACTIONS_PATH.finditer(source))
        identities = [(path.group("run"), path.group("attempt")) for path in paths]
        bindings: list[int] = []
        used_sentinels = {path.group("run") for path in paths}
        for index, path in enumerate(paths):
            run_start, run_end = path.span("run")
            width = run_end - run_start
            sentinel_value = 10 ** (width - 1) + index
            sentinel = str(sentinel_value)
            while len(sentinel) == width and sentinel in used_sentinels:
                sentinel_value += 1
                sentinel = str(sentinel_value)
            if len(sentinel) != width:
                raise CheckError("too many Actions URL occurrences to bind unambiguously")
            used_sentinels.add(sentinel)
            mutated = source[:run_start] + sentinel + source[run_end:]
            identity = (sentinel, path.group("attempt") or None)
            destinations: Counter[tuple[str, str | None]] = Counter()
            parser = MarkdownIt("commonmark", {"html": True})
            for token in parser.parse(mutated):
                if token.type == "inline":
                    link_depth = 0
                    html_parser = _ActionsAnchorParser()
                    for child in token.children or []:
                        if child.type == "link_open":
                            link_depth += 1
                            target = child.attrGet("href")
                            if isinstance(target, str):
                                destination = _CANONICAL_ACTIONS_DESTINATION.fullmatch(target)
                                if destination is not None:
                                    destinations[
                                        (destination.group("run"), destination.group("attempt"))
                                    ] += 1
                        elif child.type == "link_close":
                            link_depth = max(0, link_depth - 1)
                        elif child.type == "html_inline":
                            html_parser.feed(child.content)
                        elif (
                            child.type == "text"
                            and link_depth == 0
                            and html_parser.anchor_depth == 0
                        ):
                            destinations.update(_bare_actions_destinations(child.content))
                    html_parser.close()
                    destinations.update(html_parser.destinations)
                elif token.type == "html_block":
                    html_parser = _ActionsAnchorParser()
                    html_parser.feed(token.content)
                    html_parser.close()
                    destinations.update(html_parser.destinations)
            bindings.append(destinations[identity])
        return paths, identities, bindings

    rendered_variants = [rendered_bindings(variant) for variant in variants]
    normalized_paths, normalized_identities, bindings = rendered_variants[-1]

    malformed = control_obfuscation or not converged or any(count != 1 for count in bindings)
    malformed = malformed or any(
        identities != normalized_identities or variant_bindings != bindings
        for _, identities, variant_bindings in rendered_variants[:-1]
    )

    if malformed:
        findings.append(
            (
                line,
                f"release-evidence block for {version} contains a non-canonical Actions URL; "
                "use the exact repository /actions/runs/<positive-id> URL as plain Markdown "
                "text, an autolink, or a link destination without an attempt suffix",
            )
        )
    run_values = {match.group("run") for match in normalized_paths}
    if run_values - {expected_run}:
        findings.append(
            (
                line,
                f"release-evidence block for {version} contains a release workflow run that "
                "contradicts its release-identity marker; keep preparatory workflow history "
                "outside the immutable evidence block",
            )
        )
    matching_base_count = sum(
        count == 1 and path.group("run") == expected_run and path.group("attempt") is None
        for path, count in zip(normalized_paths, bindings, strict=True)
    )
    canonical_workflow_count = (
        1
        if normalized_identities == [(expected_run, None)] and bindings == [1] and not malformed
        else 0
    )
    if len(normalized_paths) != 1 or matching_base_count != 1:
        findings.append(
            (
                line,
                f"release-evidence block for {version} must contain exactly one canonical "
                "release workflow URL without an attempt suffix and no other Actions URL; "
                "record the attempt number as plain provenance text",
            )
        )
    return findings, canonical_workflow_count


def _evidence_block_violations(
    document: str,
    text: str,
) -> tuple[str, list[tuple[int, str]], dict[str, ReleaseEvidenceIdentity]]:
    fenced_spans = _markdown_fence_spans(text)
    markers = [
        marker
        for marker in RELEASE_EVIDENCE_MARKER.finditer(text)
        if not _inside_spans(marker.start(), fenced_spans)
    ]
    evidence_versions: set[str] = set()
    for marker in markers:
        try:
            evidence_versions.add(normalize_version(marker.group("version")))
        except CheckError:
            continue
    malformed_markers = [
        match
        for match in _ANY_RELEASE_EVIDENCE_MARKER.finditer(text)
        if not any(valid.start() == match.start() for valid in markers)
    ]
    findings = [
        (
            text.count("\n", 0, match.start()) + 1,
            "malformed release-evidence marker; use paired start/end markers with "
            "version and ISO date",
        )
        for match in malformed_markers
    ]
    identities: dict[str, ReleaseEvidenceIdentity] = {}
    covered_identity_starts: set[int] = set()
    searchable = text
    open_marker: re.Match[str] | None = None
    for marker in markers:
        kind = marker.group("kind")
        if kind == "start":
            if open_marker is not None:
                findings.append(
                    (
                        text.count("\n", 0, marker.start()) + 1,
                        "nested release-evidence block",
                    )
                )
            open_marker = marker
            continue
        if open_marker is None:
            findings.append(
                (text.count("\n", 0, marker.start()) + 1, "unpaired release-evidence end marker")
            )
            continue

        start_line = text.count("\n", 0, open_marker.start()) + 1
        try:
            version = normalize_version(open_marker.group("version"))
            end_version = normalize_version(marker.group("version"))
        except CheckError:
            findings.append(
                (
                    start_line,
                    "malformed release-evidence marker; version must be a supported exact release",
                )
            )
            searchable = _blank_span(searchable, open_marker.start(), marker.end())
            open_marker = None
            continue
        if end_version != version or marker.group("date") != open_marker.group("date"):
            findings.append(
                (
                    text.count("\n", 0, marker.start()) + 1,
                    "release-evidence end marker must match its start version and date",
                )
            )
        try:
            date.fromisoformat(open_marker.group("date"))
        except ValueError:
            findings.append(
                (
                    start_line,
                    "release-evidence marker date must be a valid ISO date",
                )
            )
        body = text[open_marker.end() : marker.start()]
        covered_identity_starts.update(
            open_marker.end() + match.start()
            for match in _ANY_RELEASE_EVIDENCE_IDENTITY.finditer(body)
        )
        identity, identity_findings = _identity_violations(
            body,
            version,
            open_marker.group("date"),
            start_line,
            evidence_versions,
        )
        findings.extend(identity_findings)
        if identity is not None:
            if version in identities:
                findings.append((start_line, f"duplicate release-evidence block for {version}"))
            else:
                identities[version] = identity
        elif _ANY_RELEASE_EVIDENCE_IDENTITY.search(body) is not None:
            findings.append(
                (start_line, f"release-evidence block for {version} has invalid identity metadata")
            )
        searchable = _blank_span(searchable, open_marker.start(), marker.end())
        open_marker = None
    if open_marker is not None:
        findings.append(
            (text.count("\n", 0, open_marker.start()) + 1, "unpaired release-evidence start marker")
        )
    for identity_marker in _ANY_RELEASE_EVIDENCE_IDENTITY.finditer(text):
        if identity_marker.start() not in covered_identity_starts:
            findings.append(
                (
                    text.count("\n", 0, identity_marker.start()) + 1,
                    "release-identity marker must appear inside one release-evidence block",
                )
            )
    identity_fields = (
        ("release commit", "commit"),
        ("workflow run", "workflow_run"),
        ("wheel SHA256", "wheel_sha256"),
        ("source-distribution SHA256", "sdist_sha256"),
    )
    for label, field in identity_fields:
        owners: dict[str, str] = {}
        for version, identity in identities.items():
            value = cast(str, getattr(identity, field))
            previous = owners.get(value)
            if previous is not None and previous != version:
                findings.append(
                    (
                        1,
                        f"release-evidence identities for {previous} and {version} "
                        f"reuse the same {label}",
                    )
                )
            else:
                owners[value] = version
    return searchable, findings, identities


def exact_release_version_violations(
    document: str,
    text: str,
    project_version: str,
) -> list[tuple[int, str]]:
    """Return deterministic CometAPI exact-version boundary violations."""
    normalized = _normalized_document_text(text)
    normalize_version(project_version)
    findings: list[tuple[int, str]] = []
    searchable = normalized
    if document == "CHANGELOG.md":
        return []
    if document in RELEASE_EVIDENCE_DOCUMENTS:
        searchable, marker_findings, _ = _evidence_block_violations(
            document,
            text,
        )
        normalized_searchable = _normalized_document_text(searchable)
        searchable = normalized_searchable
        findings.extend(marker_findings)
    for start, _ in _first_party_version_spans(searchable):
        findings.append(
            (
                searchable.count("\n", 0, start) + 1,
                EXACT_RELEASE_VERSION_CATEGORY,
            )
        )
    return sorted(set(findings))


def release_evidence_identities(
    document: str,
    text: str,
) -> dict[str, ReleaseEvidenceIdentity]:
    """Return internally validated immutable identities from an evidence document."""
    if document not in RELEASE_EVIDENCE_DOCUMENTS:
        return {}
    _, findings, identities = _evidence_block_violations(document, text)
    if findings:
        rendered = "; ".join(f"{document}:{line}: {label}" for line, label in findings)
        raise CheckError(rendered)
    return identities


def public_readme_release_violations(text: str) -> list[str]:
    """Return transient or version-specific release statements in public README text."""
    violations = [
        label for pattern, label in PUBLIC_README_FORBIDDEN_PATTERNS if re.search(pattern, text)
    ]
    violations.extend(
        label
        for _, label in exact_release_version_violations(
            "README.md",
            text,
            read_project_version(),
        )
    )
    return violations


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
