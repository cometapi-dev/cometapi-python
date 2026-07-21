#!/usr/bin/env python3
"""Download checksum-pinned actionlint v1.7.12 and validate all workflows."""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import platform
import subprocess
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from _checks import PROJECT_ROOT, CheckError

VERSION = "1.7.12"
BASE_URL = f"https://github.com/rhysd/actionlint/releases/download/v{VERSION}"
CHECKSUMS = {
    "darwin_amd64.tar.gz": "5b44c3bc2255115c9b69e30efc0fecdf498fdb63c5d58e17084fd5f16324c644",
    "darwin_arm64.tar.gz": "aba9ced2dee8d27fecca3dc7feb1a7f9a52caefa1eb46f3271ea66b6e0e6953f",
    "linux_amd64.tar.gz": "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8",
    "linux_arm64.tar.gz": "325e971b6ba9bfa504672e29be93c24981eeb1c07576d730e9f7c8805afff0c6",
    "windows_amd64.zip": "6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9",
    "windows_arm64.zip": "cadcf7ea4efe3a68728893813643cebe1185e5b1d4be5b96245f65c9a4d5ea41",
}


def _target() -> tuple[str, str]:
    system = platform.system().lower()
    systems = {"darwin": "darwin", "linux": "linux", "windows": "windows"}
    machine = platform.machine().lower()
    machines = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}
    if system not in systems or machine not in machines:
        raise CheckError(f"unsupported actionlint platform: {system}/{machine}")
    extension = "zip" if system == "windows" else "tar.gz"
    key = f"{systems[system]}_{machines[machine]}.{extension}"
    return key, "actionlint.exe" if system == "windows" else "actionlint"


def _download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "cometapi-actionlint-runner"})
    last_error: OSError | None = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except OSError as error:
            last_error = error
            if attempt < 3:
                time.sleep(attempt)
    raise CheckError(f"cannot download {url} after 3 attempts: {last_error}")


def _extract(data: bytes, archive_key: str, binary_name: str) -> bytes:
    if archive_key.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return archive.read(binary_name)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        member = archive.getmember(binary_name)
        if not member.isfile():
            raise CheckError(f"{binary_name} is not a regular file in the actionlint archive")
        stream = archive.extractfile(member)
        if stream is None:
            raise CheckError(f"cannot read {binary_name} from the actionlint archive")
        return stream.read()


def _binary(offline: bool) -> Path:
    archive_key, binary_name = _target()
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", PROJECT_ROOT / ".cache"))
    destination = cache_home / "cometapi" / "actionlint" / VERSION / archive_key / binary_name
    filename = f"actionlint_{VERSION}_{archive_key}"
    archive_path = destination.parent / filename
    if archive_path.is_file():
        data = archive_path.read_bytes()
    else:
        if offline:
            raise CheckError(f"verified actionlint archive is not cached at {archive_path}")
        data = _download(f"{BASE_URL}/{filename}")
    actual = hashlib.sha256(data).hexdigest()
    expected = CHECKSUMS[archive_key]
    if actual != expected:
        raise CheckError(f"actionlint archive checksum mismatch: expected {expected}, got {actual}")
    payload = _extract(data, archive_key, binary_name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not archive_path.is_file():
        archive_temporary = archive_path.with_suffix(archive_path.suffix + ".tmp")
        archive_temporary.write_bytes(data)
        os.replace(archive_temporary, archive_path)
    payload_digest = hashlib.sha256(payload).digest()
    installed_digest = (
        hashlib.sha256(destination.read_bytes()).digest() if destination.is_file() else b""
    )
    if installed_digest != payload_digest:
        temporary = destination.with_suffix(".tmp")
        temporary.write_bytes(payload)
        temporary.chmod(0o755)
        os.replace(temporary, destination)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline", action="store_true", help="require an already verified cache entry"
    )
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument(
        "arguments", nargs=argparse.REMAINDER, help="arguments passed to actionlint"
    )
    args = parser.parse_args()
    binary = _binary(args.offline)
    if args.download_only:
        print(binary)
        return 0
    version = subprocess.run(
        [str(binary), "-version"], check=True, text=True, capture_output=True
    ).stdout.strip()
    if VERSION not in version:
        raise CheckError(f"expected actionlint {VERSION}, got {version!r}")
    print(version)
    if args.arguments:
        command = [str(binary), *args.arguments]
    else:
        workflows = sorted((PROJECT_ROOT / ".github" / "workflows").glob("*.y*ml"))
        if not workflows:
            raise CheckError("no GitHub Actions workflow files found")
        command = [str(binary), *(str(path) for path in workflows)]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CheckError, OSError, urllib.error.URLError) as error:
        raise SystemExit(f"actionlint runner failed: {error}") from error
