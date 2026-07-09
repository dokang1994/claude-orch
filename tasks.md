# tasks.md - orchestrator-lab practice backlog

Practice exercises for extending the toy orchestration engine, roughly ordered by how much
they teach about durable agent orchestration. Pick one, implement it, and add or extend a
test in `tests/` that proves it works.

## Status legend

`Todo` / `In Progress` / `Done`

---

## P1 - Core orchestration concepts

### P1-001 - Retry policy for FAILED tasks

Status: Todo
Where: `src/orchestrator/engine.py` (`update_task`), `src/orchestrator/decider.py` (leaf-status handling in `walk`)

Today a `FAILED` leaf task immediately fails the whole execution. Real workflow engines
usually retry a task a configured number of times before giving up.

- [ ] A workflow step can set `"retryCount": 3`.
- [ ] On `FAILED`, `update_task` re-schedules the same task reference instead of failing
      the execution while retry attempts remain.
- [ ] The existing `retry_count` column is incremented and persisted.
- [ ] Once retry attempts are exhausted, the execution becomes `FAILED`.
- [ ] Test: a worker handler that fails twice then succeeds ends with the execution
      `COMPLETED` and `retry_count == 2` on the final task row.

### P1-002 - Real Anthropic-backed think step

Status: Todo
Where: `src/orchestrator/llm.py` (`AnthropicLLMProvider`), `src/orchestrator/cli.py` (provider selection), `pyproject.toml`, `README.md`

`MockLLMProvider` replays a scripted plan. Add a real Claude-backed option so the `think`
step can reason from workflow input and prior tool observations.

- [ ] `AnthropicLLMProvider.chat(task, ctx)` calls the Anthropic API.
- [ ] The model is configurable from the CLI or an environment variable.
- [ ] The API key is read from `ANTHROPIC_API_KEY`.
- [ ] The provider passes the workflow question and prior tool-call outputs as context.
- [ ] The provider returns the same shape as the mock provider:
      `{"done": bool, "action"/"answer": ...}`.
- [ ] `cli.py run --provider anthropic` and `demo --provider anthropic` wire it in.
- [ ] Document the required environment variable in `README.md`.
- [ ] Import `anthropic` lazily so the core project still runs with zero dependencies.

### P1-003 - TIMED_OUT status

Status: Todo
Where: `src/orchestrator/engine.py`, `src/orchestrator/cli.py`

A task stuck `IN_PROGRESS` forever currently blocks the workflow forever. Add timeout
detection while keeping task state durable in SQLite.

- [ ] A workflow step can set `"timeoutSeconds": N`.
- [ ] A new `orchestrator sweep <execution_id>` CLI command, or equivalent engine function,
      marks expired `IN_PROGRESS` tasks as `TIMED_OUT`.
- [ ] `TIMED_OUT` is treated like `FAILED`, including retry handling once P1-001 exists.
- [ ] Test covering both timeout-exceeded and not-yet-exceeded cases.

---

## P2 - Engine features

### P2-001 - Explicit JOIN task with `joinOn`

Status: Todo
Where: `src/orchestrator/decider.py` (`FORK_JOIN` handling), `workflows/`, `tests/`

Join is currently implicit: a fork completes when every branch is done. Real Conductor
has a separate `JOIN` task type with a `joinOn` ref list, letting a workflow join on a
subset of branches. Add that as an alternative to the implicit join.

- [ ] Add `JOIN` task parsing in the decider.
- [ ] Support `joinOn` with a list of task reference names.
- [ ] Add a bundled workflow or focused test workflow that joins on a subset of branches.
- [ ] Preserve existing implicit `FORK_JOIN` behavior.

### P2-002 - Nested DO_WHILE

Status: Todo
Where: `src/orchestrator/decider.py` (`_leaf_ref_names`, `_current_iteration`)

`_leaf_ref_names` currently does not recurse into a nested `DO_WHILE`. Make iteration
bookkeeping correct when a loop contains another loop.

- [ ] Make leaf discovery recurse through nested loop bodies.
- [ ] Ensure inner and outer loop task iterations do not collide.
- [ ] Add a test with a nested loop that completes deterministically.

### P2-003 - DYNAMIC_FORK

Status: Todo
Where: `src/orchestrator/decider.py`, plus a new workflow under `workflows/`

`FORK_JOIN` branch count is fixed in JSON. Add `DYNAMIC_FORK`, where the branch list and
task templates are computed from a prior task output.

- [ ] Define the JSON shape for `DYNAMIC_FORK`.
- [ ] Resolve branch inputs from prior task output.
- [ ] Schedule one branch per item.
- [ ] Add a workflow and test that prove dynamic fan-out and join behavior.

### P2-004 - Real MCP tool worker

Status: Todo
Where: `src/orchestrator/tools.py`, `src/orchestrator/workers.py`

`tools.invoke()` is a hardcoded dict of fake tools. Point `CALL_MCP_TOOL` at a real local
MCP server using an MCP client library or a small stdio client.

- [ ] Decide the supported transport: stdio first unless there is a reason to add HTTP.
- [ ] Add configuration for tool server commands without hardcoding local machine paths.
- [ ] Keep fake tools available for tests and offline demos.
- [ ] Add tests that do not require a real external MCP server.

---

## P3 - Nice to have

### P3-001 - `status --watch`

Status: Todo

Live-updating terminal view of an execution's task table. Poll `engine.list_tasks` on an
interval and redraw until the execution reaches a terminal state.

### P3-003 - Documentation examples

Status: Todo

Add walkthrough documentation for registering, starting, pausing, resuming, and inspecting
workflow executions.

---

## Done

_(move finished items here with the date and what test proves it)_

| Date | ID | Task | Verification |
| --- | --- | --- | --- |
| 2026-07-09 | P3-002 | Minimal read-only web UI (`webui.py`, `orchestrator serve`) + Playwright E2E tests | `pytest tests/e2e` (3 tests, real Chromium) |
