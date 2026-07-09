#!/usr/bin/env python3
"""Check that meaningful changes include AI handoff/backlog documentation."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
from pathlib import PurePosixPath


HANDOFF_FILES = {"CLAUDE.md", "tasks.md", "docs/handoff.md"}
IGNORED_PREFIXES = {
    "docs/",
}
IGNORED_FILES = {
    "README.md",
}


def run_git(args: list[str]) -> str:
    safe_directory = Path.cwd().as_posix()
    proc = subprocess.run(
        ["git", "-c", f"safe.directory={safe_directory}", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def default_base() -> str:
    safe_directory = Path.cwd().as_posix()
    for ref in ("origin/main", "origin/master", "main", "master", "HEAD~1"):
        proc = subprocess.run(
            ["git", "-c", f"safe.directory={safe_directory}", "rev-parse", "--verify", "--quiet", ref],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if proc.returncode == 0:
            return ref
    return "HEAD"


def changed_files(base: str) -> set[str]:
    out = run_git(["diff", "--name-only", f"{base}...HEAD"])
    files = {line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()}
    staged = run_git(["diff", "--cached", "--name-only"])
    files.update(line.strip().replace("\\", "/") for line in staged.splitlines() if line.strip())
    unstaged = run_git(["diff", "--name-only"])
    files.update(line.strip().replace("\\", "/") for line in unstaged.splitlines() if line.strip())
    return files


def is_meaningful(path: str) -> bool:
    if path in HANDOFF_FILES:
        return False
    if path in IGNORED_FILES:
        return False
    if any(path.startswith(prefix) for prefix in IGNORED_PREFIXES):
        return False
    suffix = PurePosixPath(path).suffix.lower()
    return suffix in {".py", ".json", ".yml", ".yaml", ".ps1", ".sh", ".toml"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Require handoff docs for meaningful changes.")
    parser.add_argument("--base", default=None, help="Base ref. Defaults to origin/main/main.")
    parser.add_argument("--allow-missing", action="store_true", help="Warn instead of failing.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    files = changed_files(args.base or default_base())
    meaningful = sorted(path for path in files if is_meaningful(path))
    handoff_touched = bool(files & HANDOFF_FILES)
    if not meaningful or handoff_touched:
        print("Handoff check passed.")
        return 0

    print("Handoff check failed: meaningful changes were found without updating handoff docs.", file=sys.stderr)
    print("Update at least one of: CLAUDE.md, tasks.md, docs/handoff.md", file=sys.stderr)
    print("Meaningful changed files:", file=sys.stderr)
    for path in meaningful:
        print(f"  - {path}", file=sys.stderr)
    if args.allow_missing:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
