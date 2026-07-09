# AI Handoff Log

This document is the first place a future AI coding session should read after `CLAUDE.md`.
Keep it short, factual, and current.

## How To Update This File

Update this file before every commit that changes behavior, workflow, tests, or project
operations. Prefer appending a dated entry over rewriting history.

Each entry should answer:

- What changed?
- Why was it changed?
- Which files matter most?
- What was verified?
- What remains risky or unfinished?
- What should the next AI session do first?

## Current State

- Core engine is a dependency-free Python workflow runner backed by SQLite.
- CLI supports registering, starting, running, listing, and inspecting executions.
- Read-only web UI exists via `orchestrator serve --port 8765`.
- AI review automation exists for local diffs, pre-push review, and GitHub PR comments.
- Main backlog is `tasks.md`; completed backlog items move to the Done table.

## Documentation Rules

- `CLAUDE.md`: stable operating guide for Claude and other AI coding agents.
- `tasks.md`: backlog, task status, and Done history with verification commands.
- `docs/handoff.md`: short chronological handoff log for context continuity.
- Commit messages: summarize the same change set reflected in `tasks.md` and this file.

Automation:

- Use `scripts/update_handoff.py` or `scripts/update-handoff.ps1` to append structured entries.
- The pre-push hook runs `scripts/check_handoff.py`.
- Meaningful code/config changes should touch at least one of `CLAUDE.md`, `tasks.md`, or `docs/handoff.md`.

## 2026-07-09 - AI Review Automation And Project Docs

Changed:

- Added local AI review script and PowerShell wrappers.
- Added pre-push hook wiring.
- Added GitHub Actions PR review workflow.
- Filled `CLAUDE.md` with project-specific operating, testing, and environment guidance.
- Refreshed `tasks.md` while preserving its backlog format.
- Added development, architecture, AI review, and handoff documentation.

Important files:

- `scripts/ai_review.py`
- `scripts/ai-review.ps1`
- `scripts/install-ai-review-hook.ps1`
- `.githooks/pre-push`
- `.github/workflows/ai-review.yml`
- `CLAUDE.md`
- `tasks.md`
- `docs/ai-review.md`
- `docs/development.md`
- `docs/architecture.md`
- `docs/handoff.md`

Verification:

- `python -m py_compile scripts\ai_review.py`
- `python -m unittest discover -s tests`

Review notes:

- Initial pre-push review identified that the PR workflow should not execute reviewer code
  from the PR checkout while holding `OPENAI_API_KEY`.
- The workflow was adjusted to run reviewer code from the trusted base checkout and treat
  PR contents as diff data.
- The PR comment step now updates a sticky bot comment instead of creating a new comment
  every synchronize event.

Next recommended work:

- Add a short README section linking to `docs/development.md`, `docs/architecture.md`, and
  `docs/handoff.md`.
- Start P1-001 retry policy when continuing engine behavior work.

## 2026-07-09 - Handoff Automation

Changed:

- Added helper scripts for structured handoff updates
- Added pre-push handoff documentation check

Important files:

- scripts/update_handoff.py
- scripts/check_handoff.py
- .githooks/pre-push
- docs/handoff.md

Verification:

- python scripts\\check_handoff.py --allow-missing

Risks or unfinished work:

- None recorded

Next recommended work:

- Use the helper before committing meaningful behavior changes

## 2026-07-09 - AI Review Follow-up Fixes

Changed:

- Allowed PR checkout to work for forked pull requests
- Included untracked UTF-8 files in manual working-mode AI review

Important files:

- .github/workflows/ai-review.yml
- scripts/ai_review.py
- docs/handoff.md

Verification:

- python -m py_compile scripts\\ai_review.py scripts\\check_handoff.py scripts\\update_handoff.py
- python -m unittest discover -s tests

Risks or unfinished work:

- None recorded

Next recommended work:

- Validate GitHub Actions AI review with a real pull request
