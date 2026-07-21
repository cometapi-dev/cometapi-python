#!/usr/bin/env python3
"""Install exact artifacts or a registry requirement and run mocked-call smoke tests."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from _checks import CheckError, normalize_version, read_project_version

SMOKE_TEST = r"""
import asyncio
from importlib.metadata import version

import httpx
from cometapi import AsyncCometAPI, CometAPI

EXPECTED_VERSION = __EXPECTED_VERSION__
assert version("cometapi") == EXPECTED_VERSION
import cometapi
assert not hasattr(cometapi, "CometClient")
assert not hasattr(cometapi, "AsyncCometClient")

seen = []

def response_for(request):
    assert request.headers["authorization"] == "Bearer package-smoke-key"
    seen.append((request.method, request.url.path))
    if request.url.path == "/v1/chat/completions":
        return httpx.Response(200, json={
            "id": "chatcmpl-package-smoke",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-5.4",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "ok"},
                "finish_reason": "stop",
            }],
        })
    if request.url.path == "/v1/responses":
        return httpx.Response(200, json={
            "id": "resp_package_smoke",
            "object": "response",
            "created_at": 0,
            "status": "completed",
            "model": "gpt-5.4",
            "output": [],
        })
    if request.url.path == "/v1/models":
        return httpx.Response(200, json={
            "object": "list",
            "data": [{"id": "gpt-5.4", "object": "model", "created": 0, "owned_by": "cometapi"}],
        })
    return httpx.Response(404, json={
        "error": {"message": "unexpected route", "type": "invalid_request_error"}
    })

with httpx.Client(transport=httpx.MockTransport(response_for)) as http_client:
    with CometAPI(
        api_key="package-smoke-key",
        base_url="https://package-smoke.invalid/v1",
        http_client=http_client,
    ) as client:
        chat = client.chat.completions.create(
            model="gpt-5.4", messages=[{"role": "user", "content": "ping"}]
        )
        assert chat.choices[0].message.content == "ok"
        result = client.responses.create(model="gpt-5.4", input="ping")
        assert result.id == "resp_package_smoke"
        models = client.models.list()
        assert models.data[0].id == "gpt-5.4"

async def async_smoke():
    async def async_response_for(request):
        return response_for(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(async_response_for)) as http_client:
        async with AsyncCometAPI(
            api_key="package-smoke-key",
            base_url="https://package-smoke.invalid/v1",
            http_client=http_client,
        ) as client:
            models = await client.models.list()
            assert models.data[0].id == "gpt-5.4"

asyncio.run(async_smoke())
assert set(seen) == {
    ("POST", "/v1/chat/completions"),
    ("POST", "/v1/responses"),
    ("GET", "/v1/models"),
}
"""


def _venv_python(directory: Path) -> Path:
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _clean_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in (
        "COMETAPI_ACCESS_TOKEN",
        "COMETAPI_API_ROOT",
        "COMETAPI_BASE_URL",
        "COMETAPI_KEY",
        "OPENAI_API_KEY",
        "PIP_BUILD_CONSTRAINT",
        "PIP_CONSTRAINT",
        "PIP_EXTRA_INDEX_URL",
        "PIP_FIND_LINKS",
        "PIP_INDEX_URL",
        "PIP_NO_INDEX",
        "PIP_REQUIREMENT",
        "PYTHONPATH",
    ):
        environment.pop(name, None)
    environment.update(
        {
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INPUT": "1",
        }
    )
    return environment


def _install_and_smoke(
    specification: str,
    expected_version: str,
    attempts: int,
    delay: float,
    index_url: str | None,
) -> None:
    last_error: subprocess.SubprocessError | None = None
    for attempt in range(1, attempts + 1):
        with tempfile.TemporaryDirectory(prefix="cometapi-clean-install-") as temporary:
            root = Path(temporary)
            subprocess.run([sys.executable, "-m", "venv", str(root / "venv")], check=True)
            python = _venv_python(root / "venv")
            try:
                install_command = [
                    str(python),
                    "-m",
                    "pip",
                    "--isolated",
                    "install",
                    "--no-cache-dir",
                    "--no-input",
                ]
                if index_url is not None:
                    install_command.extend(["--index-url", index_url])
                install_command.append(specification)
                subprocess.run(
                    install_command,
                    cwd=root,
                    env=_clean_environment(),
                    check=True,
                    timeout=300,
                )
                smoke = SMOKE_TEST.replace("__EXPECTED_VERSION__", repr(expected_version))
                subprocess.run(
                    [str(python), "-I", "-c", smoke],
                    cwd=root,
                    env=_clean_environment(),
                    check=True,
                    timeout=120,
                )
                print(f"clean-install smoke passed: {specification}")
                return
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                last_error = error
        if attempt < attempts:
            print(f"install attempt {attempt}/{attempts} failed; retrying in {delay:g}s")
            time.sleep(delay)
    raise CheckError(f"clean install failed after {attempts} attempt(s): {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs="*", help="exact local wheel/sdist paths")
    parser.add_argument("--requirement", help="registry requirement, e.g. cometapi==0.1.0a1")
    parser.add_argument("--index-url", help="explicit registry URL; valid only with --requirement")
    parser.add_argument("--expected-version", default=read_project_version())
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--retry-delay", type=float, default=10.0)
    args = parser.parse_args()
    artifacts = list(args.artifacts)
    if not artifacts and not args.requirement:
        artifacts = [
            *sorted(str(path) for path in Path("dist").glob("cometapi-*.whl")),
            *sorted(str(path) for path in Path("dist").glob("cometapi-*.tar.gz")),
        ]
    if bool(artifacts) == bool(args.requirement):
        raise CheckError("provide local artifacts or --requirement, but not both")
    if args.index_url and not args.requirement:
        raise CheckError("--index-url is valid only with --requirement")
    if args.attempts < 1 or args.retry_delay < 0:
        raise CheckError("--attempts must be positive and --retry-delay must not be negative")
    expected = normalize_version(args.expected_version)
    specifications = [args.requirement] if args.requirement else artifacts
    for value in specifications:
        if args.requirement:
            specification = str(value)
        else:
            path = Path(str(value)).resolve()
            if not path.is_file():
                raise CheckError(f"artifact does not exist: {path}")
            specification = str(path)
        _install_and_smoke(
            specification,
            expected,
            args.attempts,
            args.retry_delay,
            args.index_url,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckError as error:
        raise SystemExit(f"clean-install check failed: {error}") from error
