"""Git-based pack delivery.

After scout writes packs, optionally commit and push them inside whatever
git repo contains the output directory. This lets scout decouple from the
consumer (advocate-agent): scout pushes packs to a companion repo, advocate
pulls.

Failure to push is non-fatal — packs are still on disk, the next successful
delivery will pick up the lagging commits.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DeliveryResult:
    repo_root: Path | None
    committed: bool = False
    pushed: bool = False
    commit_sha: str | None = None
    pack_count: int = 0
    skipped_reason: str | None = None
    warnings: list[str] = field(default_factory=list)


def _git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )


def _find_repo_root(path: Path) -> Path | None:
    r = _git(["rev-parse", "--show-toplevel"], cwd=path)
    if r.returncode != 0:
        return None
    return Path(r.stdout.strip())


def _has_staged_changes(repo_root: Path) -> bool:
    # exit 1 = changes; exit 0 = no changes
    r = _git(["diff", "--cached", "--quiet"], cwd=repo_root)
    return r.returncode != 0


def _has_unstaged_changes_in(path: Path, repo_root: Path) -> bool:
    rel = path.relative_to(repo_root) if path.is_absolute() else path
    r = _git(["status", "--porcelain", "--", str(rel)], cwd=repo_root)
    return bool(r.stdout.strip())


def deliver(
    output_dir: Path,
    *,
    pack_count: int,
    message: str,
    push: bool = True,
) -> DeliveryResult:
    """Commit any new files under output_dir to its enclosing git repo, then push.

    If output_dir is not in a git repo, returns DeliveryResult with skipped_reason
    and no error. If commit/push fails, warnings are populated and the run
    continues (caller decides what to log).

    pack_count is informational only — used in the commit message footer.
    """
    output_dir = output_dir.resolve()
    if not output_dir.is_dir():
        return DeliveryResult(repo_root=None, skipped_reason=f"output_dir does not exist: {output_dir}")

    repo_root = _find_repo_root(output_dir)
    if repo_root is None:
        return DeliveryResult(
            repo_root=None,
            skipped_reason=f"{output_dir} is not inside a git repo",
        )

    result = DeliveryResult(repo_root=repo_root, pack_count=pack_count)

    if not _has_unstaged_changes_in(output_dir, repo_root):
        result.skipped_reason = "no changes under output_dir"
        return result

    rel = output_dir.relative_to(repo_root) if output_dir.is_absolute() else output_dir
    add = _git(["add", "--", str(rel)], cwd=repo_root)
    if add.returncode != 0:
        result.warnings.append(f"git add failed: {add.stderr.strip()}")
        return result

    if not _has_staged_changes(repo_root):
        result.skipped_reason = "nothing staged after add (likely all gitignored)"
        return result

    full_msg = f"{message}\n\npacks: {pack_count}\n\n[scout]"
    commit = _git(["commit", "-m", full_msg], cwd=repo_root)
    if commit.returncode != 0:
        result.warnings.append(f"git commit failed: {commit.stderr.strip()}")
        return result
    result.committed = True

    sha = _git(["rev-parse", "HEAD"], cwd=repo_root)
    if sha.returncode == 0:
        result.commit_sha = sha.stdout.strip()[:12]

    if not push:
        return result

    push_r = _git(["push"], cwd=repo_root)
    if push_r.returncode != 0:
        result.warnings.append(
            f"git push failed (commit retained, will retry next run): "
            f"{push_r.stderr.strip()[:200]}"
        )
        return result
    result.pushed = True
    return result
