from __future__ import annotations

from pathlib import Path

import pytest

from scripts._checks import CheckError, read_project_version
from scripts.check_version import changelog_release_dates


def _history(*headings: str, preamble: str = "") -> str:
    sections = ["# Changelog", preamble]
    sections.extend(f"{heading}\n\n- Historical release." for heading in headings)
    return "\n\n".join(part for part in sections if part != "") + "\n"


def test_changelog_parser_accepts_canonical_legacy_history() -> None:
    text = _history(
        "## [0.1.3] - 2026-07-30",
        "## [0.1.2] - 2026-07-30",
        "## [0.1.1] - 2026-07-29",
    )

    assert changelog_release_dates(text) == {
        "0.1.3": "2026-07-30",
        "0.1.2": "2026-07-30",
        "0.1.1": "2026-07-29",
    }


def test_changelog_parser_accepts_exact_release_please_layout() -> None:
    text = _history(
        "## [0.1.4](https://github.com/cometapi-dev/cometapi-python/compare/"
        "v0.1.3...v0.1.4) (2026-07-31)",
        "## [0.1.3] - 2026-07-30",
    )

    assert changelog_release_dates(text) == {
        "0.1.4": "2026-07-31",
        "0.1.3": "2026-07-30",
    }


def test_changelog_parser_rejects_mutable_exact_claim_in_preamble() -> None:
    text = _history(
        "## [0.1.3] - 2026-07-30",
        preamble="The current CometAPI PyPI release is 0.1.2.",
    )

    with pytest.raises(CheckError) as caught:
        changelog_release_dates(text)

    message = str(caught.value)
    assert "CHANGELOG.md:" in message
    assert "in changelog preamble" in message
    assert "version-neutral 0.1.x guidance" in message


@pytest.mark.parametrize(
    "claim",
    [
        "The current release is **0**.**1**.**4**.",
        "The current release is `0`.`1`.`4`.",
        "The current release is 0.\n1.4.",
        "The current release is 0.\u200b1.\u034f4.",
        "The current release is 0%2E1%2E4.",
        "The current release is [0](https://example.invalid)."
        "[1](https://example.invalid).[4](https://example.invalid).",
    ],
)
def test_changelog_parser_rejects_obfuscated_mutable_versions(claim: str) -> None:
    text = _history("## [0.1.3] - 2026-07-30", preamble=claim)

    with pytest.raises(CheckError, match="in changelog preamble"):
        changelog_release_dates(text)


@pytest.mark.parametrize(
    "heading",
    [
        "## [Unreleased]",
        "## Unreleased",
        "## [unreleased]",
        "## [ Unreleased ]",
        "## [Unreleased] - pending",
        "  ## [Unreleased]",
        "   ## **Unreleased**",
        "## [Un\u200breleased]",
    ],
)
@pytest.mark.parametrize("position", ["before", "between", "after"])
def test_changelog_parser_rejects_unmanaged_unreleased_heading(
    heading: str,
    position: str,
) -> None:
    newest = "## [0.1.4] - 2026-07-31\n\n- Newest release."
    previous = "## [0.1.3] - 2026-07-30\n\n- Previous release."
    parts = {
        "before": [heading, newest, previous],
        "between": [newest, heading, previous],
        "after": [newest, previous, heading],
    }[position]
    text = "# Changelog\n\n" + "\n\n".join(parts) + "\n"

    with pytest.raises(CheckError) as caught:
        changelog_release_dates(text)

    message = str(caught.value)
    assert "CHANGELOG.md:" in message
    assert "unmanaged Unreleased heading is forbidden" in message
    assert "remove it" in message
    assert "Release Please" in message


@pytest.mark.parametrize(
    ("headings", "message"),
    [
        (
            (
                "## [0.1.3] - 2026-07-30",
                "## [0.1.3] - 2026-07-29",
            ),
            "duplicates",
        ),
        (
            (
                "## [0.1.2] - 2026-07-29",
                "## [0.1.3] - 2026-07-28",
            ),
            "strictly descending version order",
        ),
        (
            (
                "## [0.1.3] - 2026-07-29",
                "## [0.1.2] - 2026-07-30",
            ),
            "dates must be non-increasing",
        ),
        (
            (
                "## [0.1.3] - 2026-02-30",
                "## [0.1.2] - 2026-01-30",
            ),
            "valid ISO date",
        ),
    ],
)
def test_changelog_parser_rejects_invalid_order_duplicates_and_dates(
    headings: tuple[str, ...],
    message: str,
) -> None:
    with pytest.raises(CheckError, match=message):
        changelog_release_dates(_history(*headings))


def test_changelog_parser_rejects_native_heading_with_nonadjacent_predecessor() -> None:
    text = _history(
        "## [0.1.3](https://github.com/cometapi-dev/cometapi-python/compare/"
        "v0.1.1...v0.1.3) (2026-07-30)",
        "## [0.1.2] - 2026-07-29",
        "## [0.1.1] - 2026-07-28",
    )

    with pytest.raises(CheckError, match=r"next historical version as its predecessor"):
        changelog_release_dates(text)


def test_changelog_parser_validates_reference_link_predecessor() -> None:
    text = _history(
        "## [0.1.3] - 2026-07-30",
        "## [0.1.2] - 2026-07-29",
    )
    text += "\n[0.1.3]: https://github.com/cometapi-dev/cometapi-python/compare/v0.1.1...v0.1.3\n"

    with pytest.raises(CheckError, match=r"compare-link definition.*v0\.1\.2\.\.\.v0\.1\.3"):
        changelog_release_dates(text)


def test_changelog_parser_accepts_initial_recovery_predecessor() -> None:
    text = _history(
        "## [0.1.0](https://github.com/cometapi-dev/cometapi-python/compare/"
        "v0.1.0-alpha.1%2Brecovery.1...v0.1.0) (2026-07-28)",
        "## [0.1.0a1] - 2026-07-27",
    )

    assert changelog_release_dates(text) == {
        "0.1.0": "2026-07-28",
        "0.1.0a1": "2026-07-27",
    }


def test_changelog_parser_accepts_canonical_compare_link_definitions() -> None:
    text = _history(
        "## [0.1.1] - 2026-07-29",
        "## [0.1.0] - 2026-07-28",
        "## [0.1.0a1] - 2026-07-27",
    )
    text += (
        "\n[0.1.0]: https://github.com/cometapi-dev/cometapi-python/compare/"
        "v0.1.0-alpha.1%2Brecovery.1...v0.1.0\n"
        "[0.1.1]: https://github.com/cometapi-dev/cometapi-python/compare/"
        "v0.1.0...v0.1.1\n"
    )

    assert list(changelog_release_dates(text)) == ["0.1.1", "0.1.0", "0.1.0a1"]


def test_changelog_parser_rejects_reference_without_release_heading() -> None:
    text = _history("## [0.1.3] - 2026-07-30", "## [0.1.2] - 2026-07-29")
    text += "\n[0.1.4]: https://github.com/cometapi-dev/cometapi-python/compare/v0.1.3...v0.1.4\n"

    with pytest.raises(CheckError, match="has no canonical dated release heading"):
        changelog_release_dates(text)


@pytest.mark.parametrize(
    "example",
    [
        "```markdown\n## [9.9.9] - 2026-07-31\n```",
        "<!--\n## [9.9.9] - 2026-07-31\n-->",
    ],
)
def test_changelog_parser_ignores_nonprose_heading_examples(example: str) -> None:
    text = _history("## [0.1.3] - 2026-07-30") + "\n" + example + "\n"

    assert changelog_release_dates(text) == {"0.1.3": "2026-07-30"}


def test_repository_changelog_is_canonical() -> None:
    dates = changelog_release_dates(Path("CHANGELOG.md").read_text(encoding="utf-8"))

    assert next(iter(dates)) == read_project_version()
