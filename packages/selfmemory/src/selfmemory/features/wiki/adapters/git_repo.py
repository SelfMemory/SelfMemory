"""Each wiki scope is its own git repository.

One repository per scope rather than one per organization: a single repo would
give anyone who could read its history every scope's history, which defeats
the point of scoping.

Commits happen once per completed operation (an ingest, an edit), not per file
write, so a run that crashes leaves no commit and no half-written history.
Serialising writers is not this module's job -- callers hold a scope lease.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "GitError",
    "ensure_repo",
    "write_excludes",
    "commit_scope",
    "head_sha",
    "history",
    "Commit",
    "commit_files",
    "tree_files",
    "show_file",
]

AUTHOR_NAME = "SelfMemory"
AUTHOR_EMAIL = "wiki@selfmemory.local"


class GitError(RuntimeError):
    pass


def _git(cwd: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    # A repository's own config can name commands git runs (fsmonitor, hooks,
    # filter drivers). Agents cannot reach .git (it is masked in the sandbox)
    # and the API refuses dot-paths, but the server never trusts it either.
    hardening = [
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "protocol.allow=never",
    ]
    proc = subprocess.run(
        ["git", *hardening, *args],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "HOME": str(cwd),
        },
    )
    if check and proc.returncode != 0:
        raise GitError(f"git {args[0]} failed: {proc.stderr.strip() or proc.stdout}")
    return proc


def is_repo(scope: Path) -> bool:
    return (scope / ".git").exists()


def ensure_repo(scope: Path) -> None:
    scope.mkdir(parents=True, exist_ok=True)
    if is_repo(scope):
        return
    _git(scope, "init", "-q", "-b", "main", check=True)
    _git(scope, "config", "user.name", AUTHOR_NAME, check=True)
    _git(scope, "config", "user.email", AUTHOR_EMAIL, check=True)
    _git(scope, "config", "commit.gpgsign", "false", check=True)


def write_excludes(scope: Path, nested: list[str] | tuple[str, ...]) -> None:
    """Keep sub-project directories out of their parent's repository.

    A sub-project lives inside its parent's directory but is its own scope and
    its own repository; without this, ``git add -A`` in the parent would record
    it as an embedded repository and its history would leak into the parent's.
    """
    info = scope / ".git" / "info"
    info.mkdir(parents=True, exist_ok=True)
    lines = ["# sub-projects are separate scopes (managed by selfmemory)"]
    lines += [f"/{name}/" for name in sorted(nested)]
    (info / "exclude").write_text("\n".join(lines) + "\n", encoding="utf-8")


def commit_scope(
    scope: Path, message: str, nested: list[str] | tuple[str, ...] = ()
) -> str | None:
    """Commit everything in the scope. Returns the short sha, or ``None`` when
    nothing changed (an ingest that found the page already current)."""
    ensure_repo(scope)
    write_excludes(scope, nested)
    _git(scope, "add", "-A", check=True)
    status = _git(scope, "status", "--porcelain", check=True)
    if not status.stdout.strip():
        return None
    _git(scope, "commit", "-q", "-m", message, check=True)
    return head_sha(scope, short=True)


def head_sha(scope: Path, short: bool = False) -> str | None:
    if not is_repo(scope):
        return None
    args = ["rev-parse", "--short", "HEAD"] if short else ["rev-parse", "HEAD"]
    proc = _git(scope, *args)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


@dataclass(frozen=True)
class Commit:
    sha: str
    date: str  # ISO-8601
    message: str


def history(scope: Path, limit: int = 80, oldest_first: bool = False) -> list[Commit]:
    if not is_repo(scope):
        return []
    args = ["log", f"-{limit}", "--pretty=format:%H%x09%aI%x09%s"]
    if oldest_first:
        args.insert(2, "--reverse")
    proc = _git(scope, *args)
    if proc.returncode != 0:
        return []
    out = []
    for line in proc.stdout.splitlines():
        sha, _, rest = line.partition("\t")
        date, _, message = rest.partition("\t")
        if sha:
            out.append(Commit(sha=sha, date=date, message=message))
    return out


def commit_files(scope: Path, sha: str) -> list[str]:
    """Paths a commit touched (relative to the scope)."""
    proc = _git(
        scope, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", sha
    )
    return [f.strip() for f in proc.stdout.splitlines() if f.strip()]


def tree_files(scope: Path, sha: str) -> list[str]:
    proc = _git(scope, "ls-tree", "-r", "--name-only", sha)
    return [f.strip() for f in proc.stdout.splitlines() if f.strip()]


def show_file(scope: Path, sha: str, rel: str) -> str:
    proc = _git(scope, "show", f"{sha}:{rel}")
    return proc.stdout if proc.returncode == 0 else ""
