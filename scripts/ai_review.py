#!/usr/bin/env python3
"""Run an AI code review over a git diff.

The script is intentionally dependency-free so it can run locally, in Git hooks,
and in GitHub Actions without installing a package.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_MODEL = "gpt-4.1"
MAX_DIFF_CHARS = 120_000


SYSTEM_PROMPT = """You are reviewing a Python repository.
Take a strict code-review stance. Prioritize bugs, behavioral regressions,
security issues, and missing tests. Lead with findings, ordered by severity.
For each finding include file/line references when the diff contains them.
If no material issues are found, say so clearly and mention residual test risk.
Write the review in Korean unless the diff content requires exact English terms.
Do not spend space praising the code.
"""


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


def has_ref(ref: str) -> bool:
    safe_directory = Path.cwd().as_posix()
    proc = subprocess.run(
        ["git", "-c", f"safe.directory={safe_directory}", "rev-parse", "--verify", "--quiet", ref],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def default_branch_ref() -> str:
    for ref in ("origin/main", "origin/master", "main", "master"):
        if has_ref(ref):
            return ref
    return "HEAD~1"


def diff_for_mode(mode: str, base: str | None) -> str:
    if mode == "staged":
        return run_git(["diff", "--cached", "--unified=80"])
    if mode == "working":
        staged = run_git(["diff", "--cached", "--unified=80"])
        unstaged = run_git(["diff", "--unified=80"])
        untracked = diff_untracked_files()
        return "\n".join(part for part in (staged, unstaged, untracked) if part.strip())
    if mode == "branch":
        base_ref = base or default_branch_ref()
        return run_git(["diff", f"{base_ref}...HEAD", "--unified=80"])
    raise ValueError(f"Unsupported mode: {mode}")


def diff_untracked_files() -> str:
    out = run_git(["ls-files", "--others", "--exclude-standard"])
    paths = [line.strip() for line in out.splitlines() if line.strip()]
    hunks: list[str] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            hunks.append(
                f"diff --git a/{raw_path} b/{raw_path}\n"
                "new file mode 100644\n"
                "--- /dev/null\n"
                f"+++ b/{raw_path}\n"
                "@@ -0,0 +1 @@\n"
                "+[binary or non-UTF-8 file omitted from AI review]\n"
            )
            continue
        lines = content.splitlines()
        hunk = [
            f"diff --git a/{raw_path} b/{raw_path}",
            "new file mode 100644",
            "--- /dev/null",
            f"+++ b/{raw_path}",
            f"@@ -0,0 +1,{len(lines)} @@",
        ]
        hunk.extend(f"+{line}" for line in lines)
        if content.endswith("\n"):
            hunk.append("")
        hunks.append("\n".join(hunk))
    return "\n".join(hunks)


def read_diff(args: argparse.Namespace) -> str:
    if args.diff_file:
        return Path(args.diff_file).read_text(encoding="utf-8", errors="replace")
    return diff_for_mode(args.mode, args.base)


def trim_diff(diff: str) -> tuple[str, bool]:
    if len(diff) <= MAX_DIFF_CHARS:
        return diff, False
    return diff[:MAX_DIFF_CHARS], True


def build_prompt(diff: str, trimmed: bool) -> str:
    notice = ""
    if trimmed:
        notice = (
            "The diff was truncated because it exceeded the local review limit. "
            "Call out that the review is partial.\n\n"
        )
    return f"{notice}Review this git diff:\n\n```diff\n{diff}\n```"


def review_with_openai(prompt: str, model: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    payload = {
        "model": model,
        "input": [
            {"role": "developer", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_output_tokens": int(os.environ.get("AI_REVIEW_MAX_OUTPUT_TOKENS", "2500")),
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API request failed: {exc.code} {detail}") from exc

    text = body.get("output_text")
    if text:
        return text

    chunks: list[str] = []
    for item in body.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(content["text"])
    if chunks:
        return "\n".join(chunks)
    raise RuntimeError("OpenAI API response did not include review text")


def review_with_codex(prompt: str) -> str:
    codex = shutil.which("codex")
    if not codex:
        raise RuntimeError("codex CLI was not found on PATH")
    proc = subprocess.run(
        [codex, "exec", "--skip-git-repo-check", "-"],
        input=prompt,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "codex CLI review failed")
    return proc.stdout.strip()


def run_review(prompt: str, provider: str, model: str) -> str:
    if provider == "openai":
        return review_with_openai(prompt, model)
    if provider == "codex":
        return review_with_codex(prompt)

    errors: list[str] = []
    if os.environ.get("OPENAI_API_KEY"):
        try:
            return review_with_openai(prompt, model)
        except Exception as exc:  # pragma: no cover - fallback path
            errors.append(f"openai: {exc}")
    if shutil.which("codex"):
        try:
            return review_with_codex(prompt)
        except Exception as exc:  # pragma: no cover - fallback path
            errors.append(f"codex: {exc}")
    detail = "; ".join(errors) if errors else "no provider configured"
    raise RuntimeError(
        "AI review provider is unavailable. Set OPENAI_API_KEY or install Codex CLI. "
        f"Details: {detail}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AI review over a git diff.")
    parser.add_argument(
        "--mode",
        choices=("working", "staged", "branch"),
        default="working",
        help="Which local diff to review when --diff-file is not provided.",
    )
    parser.add_argument("--base", help="Base ref for --mode branch, e.g. origin/main.")
    parser.add_argument("--diff-file", help="Review a diff file instead of running git diff.")
    parser.add_argument("--output", help="Write review text to this file.")
    parser.add_argument(
        "--provider",
        choices=("auto", "openai", "codex"),
        default=os.environ.get("AI_REVIEW_PROVIDER", "auto"),
    )
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", DEFAULT_MODEL))
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Exit successfully when there is no diff.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        diff = read_diff(args)
        if not diff.strip():
            message = "No diff to review."
            if args.allow_empty:
                print(message)
                return 0
            print(message, file=sys.stderr)
            return 1

        trimmed_diff, trimmed = trim_diff(diff)
        review = run_review(build_prompt(trimmed_diff, trimmed), args.provider, args.model)
        if args.output:
            Path(args.output).write_text(review + "\n", encoding="utf-8")
        print(review)
        return 0
    except Exception as exc:
        print(f"AI review failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
