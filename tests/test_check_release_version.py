from pathlib import Path
import runpy

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_release_version.py"
_default_github_tag = runpy.run_path(str(SCRIPT))["_default_github_tag"]


def test_default_github_tag_ignores_branch_refs(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_REF_TYPE", "branch")
    monkeypatch.setenv("GITHUB_REF_NAME", "master")

    assert _default_github_tag() == ""


def test_default_github_tag_reads_tag_refs(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_REF_TYPE", "tag")
    monkeypatch.setenv("GITHUB_REF_NAME", "v1.130.1")

    assert _default_github_tag() == "v1.130.1"
