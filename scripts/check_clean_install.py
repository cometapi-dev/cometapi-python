#!/usr/bin/env python3
"""Install exact artifacts and run package plus documented-example smoke tests."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

try:
    from scripts._checks import PROJECT_ROOT, CheckError, normalize_version, read_project_version
except ModuleNotFoundError:  # Support direct execution from the repository root.
    from _checks import PROJECT_ROOT, CheckError, normalize_version, read_project_version

README_EXAMPLE_NAMES = (
    "sync-chat",
    "sync-chat-stream",
    "sync-responses-models",
    "async-response",
)
README_EXAMPLE_MARKER = re.compile(r"<!-- cometapi-readme-example: (?P<name>[a-z0-9-]+) -->")
README_EXAMPLE_MARKER_PREFIX = "<!-- cometapi-readme-example:"

README_EXAMPLE_BOOTSTRAP = r"""
import ipaddress
import sys

def reject_non_loopback_connect(event, arguments):
    if event != "socket.connect":
        return
    address = arguments[1]
    if not isinstance(address, tuple) or not address:
        raise RuntimeError("README examples may connect only to the loopback fixture")
    host = address[0]
    try:
        is_loopback = ipaddress.ip_address(host).is_loopback
    except (TypeError, ValueError):
        is_loopback = False
    if not is_loopback:
        raise RuntimeError("README examples may connect only to the loopback fixture")

sys.addaudithook(reject_non_loopback_connect)
source = sys.argv[2]
exec(compile(source, f"README.md:{sys.argv[1]}", "exec"), {"__name__": "__main__"})
"""

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

CHAT_COMPLETION: dict[str, object] = {
    "id": "chatcmpl-readme",
    "object": "chat.completion",
    "created": 1,
    "model": "gpt-5.4",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "OK"},
            "finish_reason": "stop",
        }
    ],
}
CHAT_CHUNK: dict[str, object] = {
    "id": "chatcmpl-readme",
    "object": "chat.completion.chunk",
    "created": 1,
    "model": "gpt-5.4",
    "choices": [
        {
            "index": 0,
            "delta": {"content": "OK"},
            "finish_reason": None,
        }
    ],
}
RESPONSE: dict[str, object] = {
    "id": "resp-readme",
    "object": "response",
    "created_at": 1,
    "status": "completed",
    "model": "gpt-5.4",
    "output": [
        {
            "id": "msg-readme",
            "type": "message",
            "status": "completed",
            "role": "assistant",
            "content": [
                {
                    "type": "output_text",
                    "text": "OK",
                    "annotations": [],
                }
            ],
        }
    ],
    "parallel_tool_calls": True,
    "tool_choice": "auto",
    "tools": [],
}
MODEL_LIST: dict[str, object] = {
    "object": "list",
    "data": [
        {
            "id": "gpt-5.4",
            "object": "model",
            "created": 1,
            "owned_by": "cometapi",
        }
    ],
}


def read_readme_examples(path: Path = PROJECT_ROOT / "README.md") -> list[tuple[str, str]]:
    """Return the exact, ordered Python examples selected for artifact execution."""

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    examples: list[tuple[str, str]] = []
    marker_names: list[str] = []
    line_index = 0
    while line_index < len(lines):
        line = lines[line_index].rstrip("\r\n")
        if README_EXAMPLE_MARKER_PREFIX not in line:
            line_index += 1
            continue
        marker = README_EXAMPLE_MARKER.fullmatch(line)
        if marker is None:
            raise CheckError(f"malformed README example marker on line {line_index + 1}")
        name = marker["name"]
        marker_names.append(name)
        if name not in README_EXAMPLE_NAMES:
            raise CheckError(f"unknown README example marker {name!r} on line {line_index + 1}")
        if marker_names.count(name) > 1:
            raise CheckError(f"duplicate README example marker {name!r} on line {line_index + 1}")
        expected_name = README_EXAMPLE_NAMES[len(examples)]
        if name != expected_name:
            raise CheckError(
                f"README example marker {name!r} on line {line_index + 1} is out of order; "
                f"expected {expected_name!r}"
            )
        fence_index = line_index + 1
        if fence_index >= len(lines) or lines[fence_index].rstrip("\r\n") != "```python":
            raise CheckError(
                f"README example marker {name!r} on line {line_index + 1} must be followed "
                "immediately by a Python code block"
            )
        code_start = fence_index + 1
        fence_end = code_start
        while fence_end < len(lines) and lines[fence_end].rstrip("\r\n") != "```":
            fence_end += 1
        if fence_end == len(lines):
            raise CheckError(
                f"README example {name!r} opened on line {fence_index + 1} is unterminated"
            )
        code = "".join(lines[code_start:fence_end])
        if not code.strip():
            raise CheckError(f"README example {name!r} must not be empty")
        try:
            compile(code, f"{path.name}:{code_start + 1}", "exec")
        except SyntaxError as error:
            raise CheckError(
                f"README example {name!r} starting on line {code_start + 1} "
                f"is not valid Python: {error}"
            ) from error
        examples.append((name, code))
        line_index = fence_end + 1
    if tuple(marker_names) != README_EXAMPLE_NAMES:
        raise CheckError(
            "README example markers must appear exactly once in the reviewed order; "
            f"expected {list(README_EXAMPLE_NAMES)}, got {marker_names}"
        )
    return examples


class _ReadmeExampleServer(ThreadingHTTPServer):
    requests: list[tuple[str, str, dict[str, object]]]
    errors: list[str]
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _ReadmeExampleHandler)
        self.requests = []
        self.errors = []


class _ReadmeExampleHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        del format, args

    @property
    def fixture_server(self) -> _ReadmeExampleServer:
        return cast(_ReadmeExampleServer, self.server)

    def _send(self, status: int, content_type: str, payload: bytes) -> None:
        self.send_response(status)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _request_body(self) -> dict[str, object]:
        length = int(self.headers.get("content-length", "0"))
        if length == 0:
            return {}
        value = cast(object, json.loads(self.rfile.read(length)))
        if not isinstance(value, dict):
            raise ValueError("request JSON must be an object")
        return cast(dict[str, object], value)

    def _handle(self) -> None:
        try:
            if self.headers.get("authorization") != "Bearer readme-example-key":
                raise ValueError("README example did not send the configured authorization")
            target = urlsplit(self.path)
            if target.query:
                raise ValueError("README example requests must not include a query string")
            if target.path != self.path:
                raise ValueError("README example request target must be an exact absolute path")
            body = self._request_body()
            self.fixture_server.requests.append((self.command, self.path, body))
            if self.command == "POST" and self.path == "/v1/chat/completions":
                if body.get("stream") is True:
                    payload = f"data: {json.dumps(CHAT_CHUNK)}\n\ndata: [DONE]\n\n".encode()
                    self._send(200, "text/event-stream", payload)
                else:
                    self._send(200, "application/json", json.dumps(CHAT_COMPLETION).encode())
                return
            if self.command == "POST" and self.path == "/v1/responses":
                self._send(200, "application/json", json.dumps(RESPONSE).encode())
                return
            if self.command == "GET" and self.path == "/v1/models":
                self._send(200, "application/json", json.dumps(MODEL_LIST).encode())
                return
            raise ValueError(f"unexpected README example route: {self.command} {self.path}")
        except (ValueError, json.JSONDecodeError) as error:
            self.fixture_server.errors.append(str(error))
            payload = json.dumps(
                {"error": {"message": "README example fixture rejected request"}}
            ).encode()
            self._send(
                500,
                "application/json",
                payload,
            )

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()


@contextmanager
def readme_example_server() -> Generator[tuple[_ReadmeExampleServer, str], None, None]:
    server = _ReadmeExampleServer()
    host, port = cast(tuple[str, int], server.server_address)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://{host}:{port}/v1"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _run_readme_examples(
    python: Path,
    root: Path,
    examples: list[tuple[str, str]],
) -> None:
    with readme_example_server() as (server, base_url):
        environment = _clean_environment()
        environment.update(
            {
                "COMETAPI_BASE_URL": base_url,
                "COMETAPI_KEY": "readme-example-key",
                "NO_PROXY": "127.0.0.1,localhost",
                "no_proxy": "127.0.0.1,localhost",
            }
        )
        for name, code in examples:
            subprocess.run(
                [str(python), "-I", "-c", README_EXAMPLE_BOOTSTRAP, name, code],
                cwd=root,
                env=environment,
                check=True,
                timeout=120,
            )
            print(f"README example passed: {name}")

    expected_requests: list[tuple[str, str, dict[str, object]]] = [
        (
            "POST",
            "/v1/chat/completions",
            {
                "messages": [{"role": "user", "content": "Hello!"}],
                "model": "gpt-5.4",
            },
        ),
        (
            "POST",
            "/v1/chat/completions",
            {
                "messages": [{"role": "user", "content": "Write one sentence."}],
                "model": "gpt-5.4",
                "stream": True,
            },
        ),
        (
            "POST",
            "/v1/responses",
            {
                "input": "Explain API compatibility in one sentence.",
                "model": "gpt-5.4",
            },
        ),
        ("GET", "/v1/models", {}),
        (
            "POST",
            "/v1/responses",
            {"input": "Say hello.", "model": "gpt-5.4"},
        ),
    ]
    if server.errors:
        raise CheckError("README example server rejected a request: " + "; ".join(server.errors))
    if server.requests != expected_requests:
        raise CheckError(
            "README examples did not preserve the reviewed request contract; "
            f"expected {expected_requests!r}, got {server.requests!r}"
        )


def _venv_python(directory: Path) -> Path:
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _clean_environment() -> dict[str, str]:
    environment = os.environ.copy()
    proxy_variables = {"ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"}
    for name in tuple(environment):
        if name.upper() in proxy_variables:
            environment.pop(name)
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
    examples: list[tuple[str, str]],
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
                _run_readme_examples(python, root, examples)
                print(f"clean-install and README example smoke passed: {specification}")
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
    parser.add_argument("--requirement", help="exact registry requirement, e.g. cometapi==VERSION")
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
    examples = read_readme_examples()
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
            examples,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckError as error:
        raise SystemExit(f"clean-install check failed: {error}") from error
