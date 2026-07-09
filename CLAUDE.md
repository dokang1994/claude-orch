# CLAUDE.md

Operating notes for Claude Code in this repository.

## Project Snapshot

- Project name: orchestrator-lab
- Repository name: claude-orch
- Purpose: a local practice project for learning durable workflow and agent orchestration by implementing a small Python workflow engine.
- Primary domain: local CLI learning tool for workflow execution, task scheduling, durable state, LLM-style think/action loops, fork/join orchestration, and read-only execution inspection.
- Production risk level: LOW. The project runs locally, stores state in SQLite, and does not handle production traffic or customer data.
- Primary runtime: Python 3.10+.
- Core dependencies: Python standard library only.
- Optional dependencies: `anthropic>=0.40` for the planned real Anthropic-backed LLM provider exercise; `pytest`, `playwright`, and `pytest-playwright` are test-only dependencies for E2E web UI tests.
- Primary datastore: SQLite. The default local database is `data/orchestrator.db`, which is gitignored.
- Main interface: CLI through `orchestrator` after editable install, or `python -m orchestrator.cli` with `PYTHONPATH=src`.
- Read-only web UI: `orchestrator serve --port 8765`, implemented in `src/orchestrator/webui.py`.
- Workflow definitions: JSON files under `workflows/`.
- Tests: core `unittest` tests under `tests/`; Playwright E2E tests under `tests/e2e/`.
- AI review automation: local scripts under `scripts/`, a pre-push hook under `.githooks/`, and a GitHub Actions workflow under `.github/workflows/ai-review.yml`.
- Handoff log: `docs/handoff.md` keeps the current state, recent decisions, verification, and next recommended work for future AI sessions.
- Design reference: `docs/references/conductor-agent-orchestration-summary.ko.md` describes the Conductor concepts this toy engine mirrors at small scale.

## Operating Principles

- Keep changes scoped and readable. This repository is primarily for learning, so explicit code and focused tests are preferred over clever abstractions.
- Preserve the durable execution model. Workflow progress should be derived from persisted SQLite rows, not from process-local memory.
- Respect the module boundaries:
  - `db.py`: schema and SQLite connection setup.
  - `engine.py`: workflow registration, execution lifecycle, scheduling, claiming, and task updates. This is the primary mutation layer.
  - `decider.py`: recomputes next actions from persisted execution/task state.
  - `workers.py`: executes leaf tasks.
  - `llm.py`: mock LLM provider and future Anthropic provider.
  - `tools.py`: fake local tool registry for `CALL_MCP_TOOL`.
  - `expr.py`: restricted expression evaluator.
  - `cli.py`: command-line entry point.
  - `webui.py`: dependency-free read-only HTTP UI for inspecting executions and tasks.
- Do not replace `expr.py` with unrestricted `eval` or `exec`. The expression evaluator is intentionally constrained.
- Do not introduce Docker, cloud infrastructure, background services, production web frameworks, or persistent daemons unless the user asks for them.
- Prefer the standard library unless a backlog item explicitly requires an integration dependency.
- Treat `tasks.md` as the project backlog. Pick work from there unless the user gives a more specific task.
- Keep bundled workflow JSON and tests in sync. If a bundled workflow changes, add or update a test that runs it.
- Keep the web UI read-only unless a task explicitly asks for mutation from the browser.
- Update handoff documentation before finishing meaningful work:
  - move completed backlog items in `tasks.md` to Done with date and verification;
  - update `docs/handoff.md` with what changed, decisions made, tests run, and next recommended steps;
  - keep commit messages aligned with the same change summary.
- Do not commit local runtime state such as `data/orchestrator.db`, virtual environments, build output, browser binaries, or API keys.
- For Claude-generated changes, run the AI review tooling before pushing when practical.

## Testing

- Run the core test suite from the repository root:

```powershell
python -m unittest discover -s tests
```

- Current core tests use `unittest` and manually add `src/` to `sys.path`, so installing the package is not required for the core suite.
- Add or update `tests/test_engine.py` when changing scheduling, execution status, retries, timeouts, decider behavior, worker updates, or failure handling.
- Add or update `tests/test_bundled_workflows.py` when changing files under `workflows/`.
- `tests/e2e/webui_e2e_test.py` drives the read-only web UI with Playwright. It is deliberately named `*_e2e_test.py`, not `test_*.py`, so `unittest discover` skips it and the core suite stays dependency-free.
- Run web UI E2E tests after installing the test extra and browser:

```powershell
python -m pip install -e ".[test]"
playwright install chromium
pytest tests/e2e
```

- Important behavior to test directly:
  - only the expected next task is scheduled;
  - completing a task advances the workflow;
  - failed tasks fail or retry according to the intended policy;
  - `SWITCH`, `DO_WHILE`, and `FORK_JOIN` produce stable persisted task histories;
  - an execution can resume from persisted state after partial progress;
  - the read-only web UI lists executions and task states without mutating data.
- Before finishing a code change, run the relevant test command. If AI review automation is relevant, run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/ai-review.ps1 -Mode working
```

## Local Development

- Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

- Install the package in editable mode:

```powershell
python -m pip install -e .
```

- Run the demo through the installed CLI:

```powershell
orchestrator demo
```

- Run without installing:

```powershell
$env:PYTHONPATH = "src"
python -m orchestrator.cli demo
```

- Register and run a workflow manually:

```powershell
orchestrator register workflows/hello_world.json
orchestrator start hello_world --input "{}"
orchestrator run <execution-id>
orchestrator status <execution-id>
```

- Serve the read-only web UI:

```powershell
orchestrator serve --port 8765
```

- Use a custom database path when you want isolated test data:

```powershell
orchestrator --db .tmp/demo.db demo
orchestrator --db .tmp/demo.db serve --port 8765
```

- Inspect or reset local runtime state by working with `data/orchestrator.db`. The `data/` directory is ignored by git.
- Optional Anthropic setup for the future provider exercise:

```powershell
python -m pip install -e ".[anthropic]"
$env:ANTHROPIC_API_KEY = "..."
```

- OpenAI-backed AI review setup:

```powershell
$env:OPENAI_API_KEY = "..."
powershell -ExecutionPolicy Bypass -File scripts/ai-review.ps1 -Mode working
```

- Install the local pre-push review hook:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-ai-review-hook.ps1
```

## Known Constraints (by design, not bugs - see tasks.md for the exercises that lift these)

- No retry policy yet. A failed leaf task currently fails the execution immediately.
- No timeout handling yet. A task stuck in `IN_PROGRESS` can block the workflow indefinitely.
- `FORK_JOIN` uses implicit join semantics only. There is no explicit `JOIN` task with `joinOn`.
- Nested `DO_WHILE` is not supported because loop iteration discovery does not recurse into nested loops.
- `LLM_CHAT_COMPLETE` uses `MockLLMProvider`; `AnthropicLLMProvider` is still a planned exercise.
- `CALL_MCP_TOOL` uses the hardcoded fake registry in `tools.py`, not a real MCP client.
- There is no real queue or worker process boundary. The queue is represented by `tasks.status='SCHEDULED'` and claimed in-process.
- The web UI is intentionally read-only and dependency-free at runtime.
- The project intentionally avoids production concerns such as auth, multi-user isolation, deployment, and cloud infrastructure.
