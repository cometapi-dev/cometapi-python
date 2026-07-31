from __future__ import annotations

from pathlib import Path

import pytest

from scripts._checks import CheckError
from scripts.check_version import changelog_release_dates


def _history(*headings: str, preamble: str = "", unreleased: str = "") -> str:
    sections = ["# Changelog", preamble, "## [Unreleased]", unreleased]
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


def test_changelog_parser_accepts_release_please_native_heading() -> None:
    text = _history(
        "## [0.1.3](https://github.com/cometapi-dev/cometapi-python/compare/"
        "v0.1.2...v0.1.3) (2026-07-30)",
        "## [0.1.2] - 2026-07-29",
    )

    assert changelog_release_dates(text)["0.1.3"] == "2026-07-30"


@pytest.mark.parametrize("region", ["preamble", "unreleased"])
def test_changelog_parser_rejects_mutable_exact_claim_outside_history(region: str) -> None:
    kwargs = {region: "The current CometAPI PyPI release is 0.1.2."}
    text = _history("## [0.1.3] - 2026-07-30", **kwargs)

    with pytest.raises(CheckError) as caught:
        changelog_release_dates(text)

    message = str(caught.value)
    assert "CHANGELOG.md:" in message
    assert "preamble or Unreleased prose" in message
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
    text = _history("## [0.1.3] - 2026-07-30", unreleased=claim)

    with pytest.raises(CheckError, match="preamble or Unreleased prose"):
        changelog_release_dates(text)


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

    assert dates["0.1.3"] == "2026-07-30"
