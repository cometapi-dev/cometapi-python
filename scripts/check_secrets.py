#!/usr/bin/env python3
"""Scan repository content for committed credentials and workflow-scope mistakes."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

try:
    from scripts._checks import PROJECT_ROOT, CheckError
except ModuleNotFoundError:  # Support direct execution from the repository root.
    from _checks import PROJECT_ROOT, CheckError

EXCLUDED_PARTS = {
    ".cache",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
}
SENSITIVE_FILENAMES = {
    ".netrc",
    ".npmrc",
    ".pypirc",
    "credentials.json",
    "id_ed25519",
    "id_rsa",
    "service-account.json",
}
SENSITIVE_SUFFIXES = {".key", ".p12", ".pem", ".pfx"}
TOKEN_PATTERNS = {
    "GitHub token": re.compile(r"\b(?:gh[opsu]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "npm token": re.compile(r"\bnpm_[A-Za-z0-9]{30,}\b"),
    "PyPI token": re.compile(r"\bpypi-[A-Za-z0-9_-]{40,}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
ASSIGNMENT = re.compile(
    r"(?im)^\s*(?:export\s+)?(?:AWS_SECRET_ACCESS_KEY|COMETAPI_ACCESS_TOKEN|COMETAPI_KEY|"
    r"GH_TOKEN|GITHUB_TOKEN|NPM_TOKEN|OPENAI_API_KEY|PYPI_API_TOKEN|TWINE_PASSWORD)"
    r"\s*[:=]\s*[\"']?([^\s\"']+)"
)
SAFE_VALUE_MARKERS = ("${{", "${", "<", "example", "fake", "placeholder", "test", "your-")


def _files(root: Path) -> list[Path]:
    result: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or any(
            part in EXCLUDED_PARTS for part in path.relative_to(root).parts
        ):
            continue
        result.append(path)
    return sorted(result)


def _scan_content(root: Path) -> list[str]:
    findings: list[str] = []
    for path in _files(root):
        relative = path.relative_to(root)
        if (
            path.name == ".env"
            or path.name.startswith(".env.")
            or path.name in SENSITIVE_FILENAMES
            or path.suffix.casefold() in SENSITIVE_SUFFIXES
        ):
            findings.append(f"{relative}: sensitive credential filename must not be committed")
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in TOKEN_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{relative}: possible {label}")
        for match in ASSIGNMENT.finditer(text):
            value = match.group(1).lower()
            if len(value) >= 16 and not any(marker in value for marker in SAFE_VALUE_MARKERS):
                findings.append(
                    f"{relative}:{text.count(chr(10), 0, match.start()) + 1}: credential-like value"
                )
        for match in re.finditer(
            r"(?i)model\s*[:=]\s*[\"'](gpt-4o|gpt-4|claude-3-sonnet)[\"']", text
        ):
            findings.append(
                f"{relative}:{text.count(chr(10), 0, match.start()) + 1}: outdated model in example"
            )
        if path.suffix == ".md" and re.search(
            r"(?i)from\s+cometapi\s+import[^\n]*(?:CometClient|AsyncCometClient)", text
        ):
            findings.append(f"{relative}: documentation imports a removed legacy client")
    return findings


def scan_workflow_scope(root: Path) -> list[str]:
    findings: list[str] = []
    workflow_root = root / ".github" / "workflows"
    if not workflow_root.is_dir():
        return findings
    ci = workflow_root / "ci.yml"
    if ci.is_file() and re.search(
        r"\$\{\{\s*secrets\.", ci.read_text(encoding="utf-8"), flags=re.IGNORECASE
    ):
        findings.append(".github/workflows/ci.yml: offline CI must not reference secrets")
    publish = workflow_root / "publish.yml"
    if publish.is_file():
        text = publish.read_text(encoding="utf-8")
        if re.search(r"(?i)(?:password|api-token|registry-token)\s*:", text):
            findings.append(
                ".github/workflows/publish.yml: registry tokens are forbidden; use OIDC"
            )
        if text.count("id-token: write") != 1:
            findings.append(
                ".github/workflows/publish.yml: exactly one job must receive id-token: write"
            )
    allowed_id_token_counts = {
        "publish.yml": 1,
        "release-please.yml": 1,
        "release-recovery.yml": 1,
    }
    for path in sorted(
        candidate
        for candidate in workflow_root.iterdir()
        if candidate.is_file() and candidate.suffix in {".yaml", ".yml"}
    ):
        text = path.read_text(encoding="utf-8")
        expected_count = allowed_id_token_counts.get(path.name, 0)
        if text.count("id-token: write") != expected_count:
            findings.append(
                f"{path.relative_to(root)}: id-token: write must match the reviewed "
                f"publication chain count ({expected_count})"
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    findings = _scan_content(root) + scan_workflow_scope(root)
    if findings:
        raise CheckError("\n".join(findings))
    print(f"secret and scope scans passed: {root}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckError as error:
        raise SystemExit(f"secret/scope scan failed:\n{error}") from error
