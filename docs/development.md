# Development Guide

This guide describes the local environment for `orchestrator-lab`.

## Requirements

- Python 3.10 or newer
- Git
- PowerShell on Windows

The core project has no runtime third-party dependencies.

## Setup

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

Alternative without installation:

```powershell
$env:PYTHONPATH = "src"
python -m orchestrator.cli demo
```

## Common Commands

Run the demo:

```powershell
orchestrator demo
```

Register a workflow:

```powershell
orchestrator register workflows/hello_world.json
```

Start an execution:

```powershell
orchestrator start hello_world --input "{}"
```

Run an execution:

```powershell
orchestrator run <execution-id>
```

Inspect an execution:

```powershell
orchestrator status <execution-id>
orchestrator list
```

Serve the read-only web UI:

```powershell
orchestrator serve --port 8765
```

Run tests:

```powershell
python -m unittest discover -s tests
```

Run web UI E2E tests:

```powershell
python -m pip install -e ".[test]"
playwright install chromium
pytest tests/e2e
```

## Database

The default SQLite database is:

```text
data/orchestrator.db
```

The `data/` directory is gitignored. Delete the database when you want a fresh local state.

Commands accept a custom database path:

```powershell
orchestrator --db .tmp/demo.db demo
orchestrator --db .tmp/demo.db serve --port 8765
```

## Handoff And History

Before finishing meaningful work, update:

- `tasks.md` when backlog status changes or work is completed.
- `docs/handoff.md` with what changed, what was verified, and what the next AI session should do first.
- The commit message with the same high-level change summary.

## Optional Anthropic Setup

The optional dependency is declared but the real provider is not implemented yet.

```powershell
python -m pip install -e ".[anthropic]"
$env:ANTHROPIC_API_KEY = "..."
```

Track implementation in `tasks.md` under `P1-002`.

## AI Review Setup

Manual review:

```powershell
$env:OPENAI_API_KEY = "..."
powershell -ExecutionPolicy Bypass -File scripts/ai-review.ps1 -Mode working
```

Install pre-push review:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-ai-review-hook.ps1
```

PR review requires the GitHub Actions secret:

```text
OPENAI_API_KEY
```

See `docs/ai-review.md`.
