from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts._checks import CheckError
from scripts.check_clean_install import (
    README_EXAMPLE_BOOTSTRAP,
    README_EXAMPLE_NAMES,
    read_readme_examples,
    readme_example_server,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_current_readme_exposes_the_reviewed_executable_examples() -> None:
    examples = read_readme_examples()

    assert tuple(name for name, _code in examples) == README_EXAMPLE_NAMES
    assert all(code.strip() for _name, code in examples)


def _mutated_readme(tmp_path: Path, old: str, new: str) -> Path:
    source = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    assert old in source
    readme = tmp_path / "README.md"
    readme.write_text(source.replace(old, new, 1), encoding="utf-8")
    return readme


def test_readme_examples_require_the_canonical_active_model(tmp_path: Path) -> None:
    readme = _mutated_readme(
        tmp_path,
        'model="gpt-5.6-sol",\n        messages',
        'model="gpt-5.6",\n        messages',
    )

    with pytest.raises(CheckError, match=r"must use canonical active model 'gpt-5\.6-sol'"):
        read_readme_examples(readme)


def test_readme_examples_reject_unknown_markers(tmp_path: Path) -> None:
    readme = _mutated_readme(
        tmp_path,
        "<!-- cometapi-readme-example: sync-chat -->",
        "<!-- cometapi-readme-example: unexpected -->",
    )

    with pytest.raises(CheckError, match="unknown README example marker"):
        read_readme_examples(readme)


def test_readme_examples_reject_duplicate_markers(tmp_path: Path) -> None:
    readme = _mutated_readme(
        tmp_path,
        "<!-- cometapi-readme-example: sync-chat-stream -->",
        "<!-- cometapi-readme-example: sync-chat -->",
    )

    with pytest.raises(CheckError, match="duplicate README example marker"):
        read_readme_examples(readme)


def test_readme_examples_reject_reordered_markers(tmp_path: Path) -> None:
    readme = _mutated_readme(
        tmp_path,
        "<!-- cometapi-readme-example: sync-chat -->",
        "<!-- cometapi-readme-example: sync-chat-stream -->",
    )

    with pytest.raises(CheckError, match="out of order"):
        read_readme_examples(readme)


def test_readme_examples_require_an_adjacent_python_block(tmp_path: Path) -> None:
    readme = _mutated_readme(
        tmp_path,
        "<!-- cometapi-readme-example: sync-chat -->\n```python",
        "<!-- cometapi-readme-example: sync-chat -->\n\n```python",
    )

    with pytest.raises(CheckError, match="followed immediately by a Python code block"):
        read_readme_examples(readme)


def test_readme_examples_require_a_python_fence(tmp_path: Path) -> None:
    readme = _mutated_readme(
        tmp_path,
        "<!-- cometapi-readme-example: sync-chat -->\n```python",
        "<!-- cometapi-readme-example: sync-chat -->\n```py",
    )

    with pytest.raises(CheckError, match="followed immediately by a Python code block"):
        read_readme_examples(readme)


def test_readme_examples_reject_unterminated_fence(tmp_path: Path) -> None:
    examples = read_readme_examples()
    source = "".join(
        f"<!-- cometapi-readme-example: {name} -->\n```python\n{code}"
        + ("```\n" if name != README_EXAMPLE_NAMES[-1] else "")
        for name, code in examples
    )
    readme = tmp_path / "README.md"
    readme.write_text(source, encoding="utf-8")

    with pytest.raises(CheckError, match="is unterminated"):
        read_readme_examples(readme)


def test_readme_examples_reject_invalid_python(tmp_path: Path) -> None:
    readme = _mutated_readme(
        tmp_path,
        "from cometapi import CometAPI\n\nwith CometAPI() as client:",
        "from cometapi import CometAPI\n\nthis is not valid Python\nwith CometAPI() as client:",
    )

    with pytest.raises(CheckError, match="is not valid Python"):
        read_readme_examples(readme)


def test_readme_examples_do_not_select_unmarked_direct_openai_block() -> None:
    examples = read_readme_examples()

    assert all("from openai import OpenAI" not in code for _name, code in examples)


def test_readme_example_server_records_sse_and_rejects_extra_routes() -> None:
    with readme_example_server() as (server, base_url):
        environment = os.environ.copy()
        environment.update(
            {
                "COMETAPI_BASE_URL": base_url,
                "COMETAPI_KEY": "readme-example-key",
                "NO_PROXY": "127.0.0.1,localhost",
            }
        )
        source = """
import json
import os
import urllib.request

request = urllib.request.Request(
    os.environ["COMETAPI_BASE_URL"] + "/chat/completions",
    data=json.dumps({"model": "gpt-5.6-sol", "messages": [], "stream": True}).encode(),
    headers={"Authorization": "Bearer readme-example-key", "Content-Type": "application/json"},
)
with urllib.request.urlopen(request) as response:
    payload = response.read().decode()
assert response.headers["Content-Type"] == "text/event-stream"
assert "data: [DONE]" in payload
"""
        subprocess.run(
            [sys.executable, "-I", "-c", README_EXAMPLE_BOOTSTRAP, "fixture-sse", source],
            env=environment,
            check=True,
            timeout=10,
        )
        import urllib.error
        import urllib.request

        request = urllib.request.Request(
            base_url + "/models?unexpected=1",
            headers={"Authorization": "Bearer readme-example-key"},
        )
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request, timeout=5)
        assert error.value.code == 500

    assert server.requests == [
        (
            "POST",
            "/v1/chat/completions",
            {"model": "gpt-5.6-sol", "messages": [], "stream": True},
        )
    ]
    assert server.errors == ["README example requests must not include a query string"]


def test_readme_example_bootstrap_rejects_non_loopback_network() -> None:
    source = """
import socket

socket.create_connection(("192.0.2.1", 80), timeout=0.1)
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", README_EXAMPLE_BOOTSTRAP, "network", source],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode != 0
    assert "README examples may connect only to the loopback fixture" in result.stderr


def test_fixture_payloads_are_json_serializable() -> None:
    from scripts.check_clean_install import CHAT_CHUNK, RESPONSE

    assert json.loads(json.dumps(CHAT_CHUNK))["object"] == "chat.completion.chunk"
    assert json.loads(json.dumps(RESPONSE))["object"] == "response"
