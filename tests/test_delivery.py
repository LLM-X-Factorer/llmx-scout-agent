"""End-to-end tests against a real temp git repo. We don't mock subprocess
because the whole point of this module is correctly orchestrating git itself.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scout.delivery.git import deliver


def _run(args: list[str], *, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A bare 'remote' + a working clone, so we can verify push end-to-end."""
    remote = tmp_path / "remote.git"
    _run(["git", "init", "--bare", "--initial-branch=main", str(remote)], cwd=tmp_path)

    work = tmp_path / "work"
    _run(["git", "clone", str(remote), str(work)], cwd=tmp_path)
    _run(["git", "config", "user.email", "test@example.com"], cwd=work)
    _run(["git", "config", "user.name", "Test"], cwd=work)
    # Need an initial commit to push from; otherwise "git push" fails on an empty repo
    (work / ".gitkeep").write_text("")
    _run(["git", "add", ".gitkeep"], cwd=work)
    _run(["git", "commit", "-m", "init"], cwd=work)
    _run(["git", "push"], cwd=work)
    return work


def test_skips_if_output_dir_missing(tmp_path: Path):
    r = deliver(tmp_path / "no_such", pack_count=0, message="x")
    assert r.skipped_reason and "does not exist" in r.skipped_reason
    assert not r.committed and not r.pushed


def test_skips_if_not_in_git_repo(tmp_path: Path):
    out = tmp_path / "out"
    out.mkdir()
    r = deliver(out, pack_count=1, message="x")
    assert r.skipped_reason and "not inside a git repo" in r.skipped_reason


def test_skips_if_no_changes(repo: Path):
    out = repo / "packs"
    out.mkdir()
    r = deliver(out, pack_count=0, message="empty run")
    assert r.skipped_reason == "no changes under output_dir"
    assert not r.committed


def test_commits_and_pushes_new_files(repo: Path):
    out = repo / "packs"
    out.mkdir()
    (out / "a.md").write_text("---\nfoo: 1\n---\nhello\n")

    r = deliver(out, pack_count=1, message="scout: 1 pack(s)")
    assert r.committed, r.warnings
    assert r.pushed, r.warnings
    assert r.commit_sha is not None
    assert len(r.warnings) == 0

    # Verify by inspecting git log
    log = subprocess.run(
        ["git", "log", "-1", "--pretty=%s%n%b"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout
    assert "scout: 1 pack(s)" in log
    assert "packs: 1" in log


def test_push_can_be_disabled(repo: Path):
    out = repo / "packs"
    out.mkdir()
    (out / "a.md").write_text("hi")
    r = deliver(out, pack_count=1, message="local only", push=False)
    assert r.committed
    assert not r.pushed
    assert r.commit_sha is not None


def test_push_failure_keeps_commit_and_records_warning(repo: Path, tmp_path: Path):
    """If the remote is unreachable, the local commit must still land."""
    out = repo / "packs"
    out.mkdir()
    (out / "a.md").write_text("hi")
    # Break the remote by pointing it at nowhere
    subprocess.run(
        ["git", "remote", "set-url", "origin", str(tmp_path / "no_such_remote.git")],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    r = deliver(out, pack_count=1, message="should not push")
    assert r.committed, "local commit must succeed even when push fails"
    assert not r.pushed
    assert any("push failed" in w for w in r.warnings)


def test_skips_when_only_gitignored_files_change(repo: Path):
    # Set up a gitignored output dir
    (repo / ".gitignore").write_text("packs/\n")
    _run(["git", "add", ".gitignore"], cwd=repo)
    _run(["git", "commit", "-m", "ignore packs"], cwd=repo)
    out = repo / "packs"
    out.mkdir()
    (out / "a.md").write_text("hi")

    r = deliver(out, pack_count=1, message="should be a no-op")
    # The path itself is ignored, so `git status` shows nothing under it.
    assert r.skipped_reason == "no changes under output_dir"
    assert not r.committed
