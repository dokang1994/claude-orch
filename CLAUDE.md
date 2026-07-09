# CLAUDE.md

Operating notes for Claude Code in this repository.

## Project Snapshot

- Project name: orchestrator-lab
- Purpose: personal practice project for learning AI/agent orchestration concepts (task queue, decider, durable workflow state, LLM + tool-call loops, multi-agent fan-out) by re-implementing a small slice of them.
- Primary domain: local learning tool, not a product. No production users, no customer data.
- Production risk level: LOW — everything runs locally against a local SQLite file (`data/orchestrator.db`, gitignored).
- Primary runtime: Python 3.10+, standard library only (see `pyproject.toml`; `anthropic` is an optional extra used by one exercise).
- Primary datastore: SQLite.
- Design reference: `docs/references/conductor-agent-orchestration-summary.ko.md` — a summary of how `conductor-oss/conductor` implements workflow/task/decider/worker and agent orchestration. This repo intentionally mirrors that model at toy scale; see the mapping table in `README.md`.

## Operating Principles

- Keep changes scoped and readable — this is a teaching codebase, so clarity beats cleverness. Match the existing style in `src/orchestrator/`.
- Respect the module boundaries: `db.py` (persistence) → `decider.py` (pure decision logic over persisted state, no side effects except the SWITCH inline-completion write) → `engine.py` (the only place that mutates `executions`/`tasks`) → `workers.py` (executes leaf tasks) → `cli.py` (entry point). Don't blur these.
- `decider.walk()` is intentionally a stateless recompute-from-persisted-state function, mirroring Conductor's real `decide()`. Don't introduce in-memory-only execution state that isn't derivable from the `tasks` table — that would break the durability/resume story that's the whole point of this project.
- `expr.py`'s evaluator is a deliberately restricted `ast`-based sandbox (no calls, no attribute access, no imports). Keep it that way; don't swap in bare `eval`/`exec` even though this is a local single-user tool.
- `tasks.md` is the practice backlog. Pick items from there rather than inventing new scope, unless the user asks for something specific.
- Out of scope by design: CI/CD, Docker, cloud infra, auth, multi-user concerns. This is a local CLI learning tool.

## Testing

- Run: `python -m unittest discover -s tests` from the repo root. Stdlib only — no install required; tests add `src/` to `sys.path` themselves.
- Extend `tests/test_engine.py` or `tests/test_bundled_workflows.py` when changing `decider.py` or `engine.py` — that's where the actual orchestration logic lives, and regressions there are easy to introduce silently (e.g. DO_WHILE iteration bookkeeping, FORK_JOIN parallel scheduling).
- If you add or change a bundled workflow under `workflows/`, add a case to `test_bundled_workflows.py` that runs it to completion.
- `tests/e2e/webui_e2e_test.py` drives the read-only web UI (`webui.py`) with Playwright. It's deliberately named `*_e2e_test.py` (not `test_*.py`) so `unittest discover` skips it and the core suite stays dependency-free; run it with `pytest tests/e2e` after `pip install -e ".[test]"` and `playwright install chromium`.

## Local Development

- Quickstart: `python -m orchestrator.cli demo` (needs `src` on `PYTHONPATH`, or `pip install -e .` first — see README for both paths).
- Inspect state directly any time with `sqlite3 data/orchestrator.db` if the CLI's `status`/`list` commands aren't enough.

## Known Constraints (by design, not bugs — see tasks.md for the exercises that lift these)

- No real task queue or network hop — the "queue" is a `status='SCHEDULED'` filter on the `tasks` table, polled in-process by `engine.claim_next_task`.
- No retries, no timeouts (P1-001, P1-003).
- `FORK_JOIN` always does an implicit join; there's no explicit `JOIN` task with `joinOn` (P2-001).
- `DO_WHILE` cannot nest inside another `DO_WHILE` (P2-002).
- `LLM_CHAT_COMPLETE` uses a scripted mock (`llm.MockLLMProvider`) by default; `AnthropicLLMProvider` is a stub that raises `NotImplementedError` (P1-002).
- `CALL_MCP_TOOL` calls a hardcoded dict of fake tools in `tools.py`, not a real MCP server (P2-004).
