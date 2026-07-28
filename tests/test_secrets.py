from __future__ import annotations

from pathlib import Path

from scripts.check_secrets import scan_workflow_scope

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_current_workflows_retain_reviewed_oidc_scope() -> None:
    assert scan_workflow_scope(PROJECT_ROOT) == []


def test_scope_scan_rejects_oidc_on_an_unreviewed_workflow(tmp_path: Path) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    for name in ("ci.yml", "publish.yml"):
        (workflows / name).write_text(
            (PROJECT_ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    (workflows / "live-smoke.yml").write_text(
        "permissions:\n  id-token: write\n",
        encoding="utf-8",
    )

    assert scan_workflow_scope(tmp_path) == [
        ".github/workflows/live-smoke.yml: id-token: write must match the reviewed "
        "publication chain count (0)"
    ]


def test_scope_scan_rejects_missing_top_level_publisher_oidc(tmp_path: Path) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    for name in ("ci.yml", "publish.yml"):
        text = (PROJECT_ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        if name == "publish.yml":
            text = text.replace("      id-token: write\n", "", 1)
        (workflows / name).write_text(text, encoding="utf-8")

    assert scan_workflow_scope(tmp_path) == [
        ".github/workflows/publish.yml: exactly one job must receive id-token: write",
        ".github/workflows/publish.yml: id-token: write must match the reviewed "
        "publication chain count (1)",
    ]
