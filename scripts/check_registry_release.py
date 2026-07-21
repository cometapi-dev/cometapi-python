#!/usr/bin/env python3
"""Verify public PyPI artifacts, digests, and trusted-publisher provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import cast

from _checks import CheckError, normalize_version

PYPI_JSON_URL = "https://pypi.org/pypi/cometapi/{version}/json"


def _expected_digests(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, separator, source = line.partition("  ")
        filename = Path(source).name
        if (
            not separator
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or not filename
            or filename in result
        ):
            raise CheckError(f"invalid sha256 manifest line: {line!r}")
        result[filename] = digest
    if (
        len(result) != 2
        or sum(name.endswith(".whl") for name in result) != 1
        or sum(name.endswith(".tar.gz") for name in result) != 1
    ):
        raise CheckError("digest manifest must contain exactly one wheel and one sdist")
    return result


def _load_registry_metadata(version: str, attempts: int, delay: float) -> dict[str, object]:
    url = PYPI_JSON_URL.format(version=version)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                value = cast(object, json.load(response))
            if not isinstance(value, dict):
                raise CheckError("PyPI JSON response is not an object")
            return cast(dict[str, object], value)
        except (OSError, ValueError, urllib.error.URLError) as error:
            last_error = error
            if attempt < attempts:
                print(f"PyPI metadata attempt {attempt}/{attempts} failed; retrying in {delay:g}s")
                time.sleep(delay)
    raise CheckError(f"cannot load public PyPI metadata after {attempts} attempts: {last_error}")


def _registry_files(metadata: dict[str, object]) -> dict[str, dict[str, object]]:
    raw_urls = metadata.get("urls")
    if not isinstance(raw_urls, list):
        raise CheckError("PyPI JSON response has no artifact list")
    result: dict[str, dict[str, object]] = {}
    for raw in cast(list[object], raw_urls):
        if not isinstance(raw, dict):
            raise CheckError("PyPI JSON contains an invalid artifact record")
        record = cast(dict[str, object], raw)
        filename = record.get("filename")
        if not isinstance(filename, str):
            raise CheckError("PyPI JSON contains an invalid artifact filename")
        if filename in result:
            raise CheckError(f"PyPI JSON contains duplicate artifact {filename}")
        result[filename] = record
    return result


def _download_and_verify(
    records: dict[str, dict[str, object]], expected: dict[str, str], directory: Path
) -> list[str]:
    if set(records) != set(expected):
        raise CheckError(
            "public PyPI artifact names differ from the verified release bundle: "
            f"public={sorted(records)}, expected={sorted(expected)}"
        )
    directory.mkdir(parents=True, exist_ok=True)
    urls: list[str] = []
    for filename, digest in sorted(expected.items()):
        record = records[filename]
        url = record.get("url")
        digests = record.get("digests")
        if not isinstance(digests, dict):
            raise CheckError(f"PyPI supplied no digests for {filename}")
        registry_digest = cast(dict[str, object], digests).get("sha256")
        if not isinstance(url, str) or not url.startswith("https://files.pythonhosted.org/"):
            raise CheckError(f"PyPI supplied an unexpected artifact URL for {filename}: {url!r}")
        if registry_digest != digest:
            raise CheckError(
                f"public PyPI digest differs for {filename}: {registry_digest!r} != {digest}"
            )
        with urllib.request.urlopen(url, timeout=60) as response:
            payload = response.read()
        downloaded_digest = hashlib.sha256(payload).hexdigest()
        if downloaded_digest != digest:
            raise CheckError(
                f"downloaded digest differs for {filename}: {downloaded_digest} != {digest}"
            )
        (directory / filename).write_bytes(payload)
        urls.append(url)
        print(f"public artifact digest passed: {filename}")
    return urls


def _verify_provenance(urls: list[str], repository: str) -> None:
    for url in urls:
        try:
            subprocess.run(
                [
                    "pypi-attestations",
                    "verify",
                    "pypi",
                    "--repository",
                    repository,
                    url,
                ],
                check=True,
                timeout=120,
            )
        except (
            FileNotFoundError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ) as error:
            raise CheckError(f"provenance verification failed for {url}: {error}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument(
        "--repository", required=True, help="canonical https://github.com/owner/repo"
    )
    parser.add_argument("--digest-file", type=Path, required=True)
    parser.add_argument("--download-directory", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=12)
    parser.add_argument("--retry-delay", type=float, default=10.0)
    args = parser.parse_args()
    if args.attempts < 1 or args.retry_delay < 0:
        raise CheckError("--attempts must be positive and --retry-delay must not be negative")
    if not args.repository.startswith("https://github.com/"):
        raise CheckError("--repository must be a canonical GitHub HTTPS URL")
    version = normalize_version(args.version)
    expected = _expected_digests(args.digest_file)
    metadata = _load_registry_metadata(version, args.attempts, args.retry_delay)
    info = metadata.get("info")
    if not isinstance(info, dict):
        raise CheckError("PyPI JSON response has no project metadata")
    actual_version = normalize_version(str(cast(dict[str, object], info).get("version", "")))
    if actual_version != version:
        raise CheckError(f"public PyPI version differs: {actual_version!r} != {version}")
    urls = _download_and_verify(_registry_files(metadata), expected, args.download_directory)
    _verify_provenance(urls, args.repository)
    print(f"public PyPI digests and provenance passed for cometapi {version}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckError as error:
        raise SystemExit(f"registry release check failed: {error}") from error
