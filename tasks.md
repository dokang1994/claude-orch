# tasks.md — orchestrator-lab practice backlog

Practice exercises for extending the toy orchestration engine, roughly ordered by how much
they teach about durable agent orchestration. Pick one, implement it, and add or extend a
test in `tests/` that proves it works.

## Status legend

`Todo` / `In Progress` / `Done`

---

## P1 — Core orchestration concepts

### P1-001 — Retry policy for FAILED tasks

Status: Todo
Where: `engine.py` (`update_task`), `decider.py` (leaf-status handling in `walk`)

Today a FAILED leaf task immediately fails the whole execution. Real Conductor retries a
task N times (optionally with backoff) before giving up.

- [ ] A workflow step can set `"retryCount": 3`.
- [ ] On FAILED, `update_task` re-schedules the same ref (incrementing the existing
      `retry_count` column, which exists but is currently unused) instead of failing the
      execution, until `retryCount` is exhausted.
- [ ] Test: a worker handler that fails twice then succeeds ends with the execution
      COMPLETED and `retry_count == 2` on the final task row.

### P1-002 — Real Anthropic-backed think step

Status: Todo
Where: `llm.py` (`AnthropicLLMProvider`), `cli.py` (provider selection)

`MockLLMProvider` replays a scripted plan. Replace it for one workflow with a real Claude
call so `think` actually reasons about `tool_call` outputs instead of following a script.

- [ ] `AnthropicLLMProvider.chat(task, ctx)` calls the Anthropic API (model configurable,
      API key from `ANTHROPIC_API_KEY`), passing `ctx['input']['question']` and the history
      of prior `tool_call` outputs, and returns the same
      `{"done": bool, "action"/"answer": ...}` shape the mock returns.
- [ ] `cli.py run --provider anthropic` and `demo --provider anthropic` wire it in.
- [ ] Document the required env var in `README.md`.
- [ ] Add `anthropic` to the `[project.optional-dependencies]` group already stubbed in
      `pyproject.toml` and import it lazily so the rest of the project still runs with zero
      dependencies installed.

### P1-003 — TIMED_OUT status

Status: Todo
Where: `engine.py`

A task stuck IN_PROGRESS forever currently blocks the workflow forever — there's no
timeout detection at all.

- [ ] A workflow step can set `"timeoutSeconds": N`.
- [ ] A new `orchestrator sweep <execution_id>` CLI command (or a check inside `decide()`)
      marks tasks IN_PROGRESS past their timeout as TIMED_OUT, treated the same as FAILED.
- [ ] Test covering both the timeout-exceeded and not-yet-exceeded cases.

---

## P2 — Engine features

### P2-001 — Explicit JOIN task with `joinOn`

Status: Todo
Where: `decider.py` (`FORK_JOIN` handling)

Join is currently implicit: a fork completes when every branch is done. Real Conductor
has a separate `JOIN` task type with a `joinOn` ref list, letting a workflow join on a
subset of branches. Add that as an alternative to the implicit join.

### P2-002 — Nested DO_WHILE

Status: Todo
Where: `decider.py` (`_leaf_ref_names`, `_current_iteration`)

`_leaf_ref_names` currently does not recurse into a nested `DO_WHILE` (see the comment in
`decider.py`). Make iteration bookkeeping correct when a loop contains another loop.

### P2-003 — DYNAMIC_FORK

Status: Todo
Where: `decider.py`, plus a new workflow under `workflows/`

`FORK_JOIN`'s branch count is fixed in the JSON. Add `DYNAMIC_FORK`, where the branch list
(and its task templates) is computed from a prior task's output — e.g. one branch per
hotel found by `get_hotel_options`.

### P2-004 — Real MCP tool worker

Status: Todo
Where: `tools.py`

`tools.invoke()` is a hardcoded dict of fake tools. Point `CALL_MCP_TOOL` at a real local
MCP server (stdio or HTTP transport) using an MCP client library instead.

---

## P3 — Nice to have

### P3-001 — `status --watch`

Live-updating terminal view of an execution's task table (poll `engine.list_tasks` on an
interval).

---

## Done

_(move finished items here with the date and what test proves it)_

| Date | ID | Task | Verification |
| --- | --- | --- | --- |
| 2026-07-09 | P3-002 | Minimal read-only web UI (`webui.py`, `orchestrator serve`) + Playwright E2E tests | `pytest tests/e2e` (3 tests, real Chromium) |
