#!/usr/bin/env python3
"""Copy the repository into an empty parent and verify it is self-contained."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from _checks import PROJECT_ROOT, CheckError

IGNORED_NAMES = {
    ".cache",
    ".DS_Store",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
}
FORBIDDEN_REFERENCES = {
    ".." + "/": "parent-relative path",
    "/" + "Users/": "machine-specific absolute path",
    "/home/" + "runner/work/": "runner-specific absolute path",
    "cometapi-" + "node": "sibling Node.js SDK",
    "cometapi-" + "cli": "sibling CLI",
    "cometapi-" + "go": "sibling Go SDK",
    "references" + "/": "outside-root references tree",
}


def _ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORED_NAMES or name.endswith((".pyc", ".pyo"))}


def _scan(root: Path) -> None:
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "tests" in path.relative_to(root).parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for needle, label in FORBIDDEN_REFERENCES.items():
            if needle in text:
                findings.append(f"{path.relative_to(root)}: {label} ({needle!r})")
    if findings:
        raise CheckError("standalone-reference scan failed:\n" + "\n".join(findings))


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in (
        "COMETAPI_ACCESS_TOKEN",
        "COMETAPI_API_ROOT",
        "COMETAPI_BASE_URL",
        "COMETAPI_KEY",
        "OPENAI_API_KEY",
        "PYTHONPATH",
        "VIRTUAL_ENV",
    ):
        environment.pop(name, None)
    return environment


def _run(root: Path, command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=root, env=_environment(), check=True, timeout=1200)


def _offline_checks(root: Path) -> None:
    commands = [
        ["uv", "lock", "--check"],
        ["uv", "sync", "--locked"],
        ["uv", "run", "ruff", "check", "src", "tests", "scripts"],
        ["uv", "run", "ruff", "format", "--check", "src", "tests", "scripts"],
        ["uv", "run", "pyright"],
        ["uv", "run", "pytest", "-m", "not live"],
        ["uv", "run", "python", "scripts/check_secrets.py"],
        ["uv", "run", "python", "scripts/check_version.py", "--require-changelog"],
        [
            "uv",
            "run",
            "python",
            "scripts/check_version.py",
            "--require-public-preview-docs",
        ],
        ["uv", "run", "python", "scripts/check_workflows.py"],
        ["uv", "run", "python", "scripts/run_actionlint.py"],
        ["uv", "build"],
        ["uv", "run", "twine", "check", "dist/*"],
        ["uv", "run", "python", "scripts/check_artifacts.py"],
    ]
    for command in commands:
        if command[-1] == "dist/*":
            artifacts = _distribution_paths(root)
            command = command[:-1] + artifacts
        _run(root, command)
    artifacts = _distribution_paths(root)
    _run(root, ["uv", "run", "python", "scripts/check_clean_install.py", *artifacts])


def _distribution_paths(root: Path) -> list[str]:
    dist = root / "dist"
    paths = sorted(
        str(path)
        for path in dist.iterdir()
        if path.suffix == ".whl" or path.name.endswith(".tar.gz")
    )
    if len(paths) != 2:
        raise CheckError(f"expected one wheel and one sdist in {dist}; found {paths}")
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-only", action="store_true", help="copy and scan without commands")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cometapi-standalone-parent-") as temporary:
        candidate = Path(temporary) / "repository"
        shutil.copytree(PROJECT_ROOT, candidate, ignore=_ignore)
        _scan(candidate)
        if not args.scan_only:
            _offline_checks(candidate)
    print("standalone copied-checkout verification passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CheckError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise SystemExit(f"repository-independence check failed: {error}") from error
