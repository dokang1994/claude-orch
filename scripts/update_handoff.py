#!/usr/bin/env python3
"""Append a structured AI handoff entry and optional tasks.md Done row."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "docs" / "handoff.md"
TASKS = ROOT / "tasks.md"


def bullet_lines(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values)


def append_handoff(args: argparse.Namespace) -> None:
    entry_date = args.date or date.today().isoformat()
    entry = [
        "",
        f"## {entry_date} - {args.title}",
        "",
        "Changed:",
        "",
        bullet_lines(args.changed),
        "",
        "Important files:",
        "",
        bullet_lines(args.files),
        "",
        "Verification:",
        "",
        bullet_lines(args.verified or ["Not run"]),
        "",
        "Risks or unfinished work:",
        "",
        bullet_lines(args.risks or ["None recorded"]),
        "",
        "Next recommended work:",
        "",
        bullet_lines(args.next or ["Pick the next item from tasks.md"]),
        "",
    ]
    HANDOFF.parent.mkdir(parents=True, exist_ok=True)
    with HANDOFF.open("a", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(entry))


def append_done_row(args: argparse.Namespace) -> None:
    if not args.done_id:
        return
    text = TASKS.read_text(encoding="utf-8")
    row = f"| {args.date or date.today().isoformat()} | {args.done_id} | {args.done_task} | {args.done_verification} |"
    if row in text:
        return
    TASKS.write_text(text.rstrip() + "\n" + row + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update AI handoff and optional tasks.md Done history.")
    parser.add_argument("--title", required=True, help="Short entry title.")
    parser.add_argument("--date", help="Entry date in YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--changed", action="append", required=True, help="What changed. Repeatable.")
    parser.add_argument("--files", action="append", required=True, help="Important file path. Repeatable.")
    parser.add_argument("--verified", action="append", help="Verification command/result. Repeatable.")
    parser.add_argument("--risks", action="append", help="Risk or unfinished work. Repeatable.")
    parser.add_argument("--next", action="append", help="Next recommended work. Repeatable.")
    parser.add_argument("--done-id", help="Optional tasks.md Done item id, e.g. P1-001.")
    parser.add_argument("--done-task", default="", help="Done table task summary.")
    parser.add_argument("--done-verification", default="", help="Done table verification.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    append_handoff(args)
    append_done_row(args)
    print(f"Updated {HANDOFF.relative_to(ROOT)}")
    if args.done_id:
        print(f"Updated {TASKS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
