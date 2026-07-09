# Architecture

`orchestrator-lab` is a compact workflow engine for learning durable orchestration.

## Core Loop

The runtime loop is:

```text
register workflow
start execution
decide next tasks
claim scheduled task
worker executes task
update task result
decide again
complete or fail execution
inspect through CLI or read-only web UI
```

The important property is that `decider.walk()` recomputes the next action from persisted
task rows. Workflow progress must not rely on in-memory state.

## Persistence Model

SQLite stores:

- workflow definitions
- workflow executions
- task instances

The task table also acts as the queue. `engine.claim_next_task()` finds a scheduled task
and marks it `IN_PROGRESS`.

## Workflow Definition

Workflow JSON files live in `workflows/`.

Each workflow has:

- `name`
- `version`
- `tasks`
- optional `outputParameters`

Task references use `taskReferenceName`. Expressions use a restricted evaluator and can
read workflow input and prior task outputs.

Example expression:

```text
tasks['think']['output']['done']
```

## Task Types

Leaf tasks require a worker:

- `SIMPLE`
- `LLM_CHAT_COMPLETE`
- `CALL_MCP_TOOL`
- `HUMAN`

Control tasks are resolved by the decider:

- `SWITCH`
- `DO_WHILE`
- `FORK_JOIN`
- `TERMINATE`

## Module Map

- `db.py`: schema and SQLite connection setup
- `engine.py`: mutation layer and execution lifecycle
- `decider.py`: scheduling decisions from persisted state
- `workers.py`: worker-task execution
- `llm.py`: mock LLM and future Anthropic provider
- `tools.py`: fake tool implementations
- `expr.py`: safe expression subset
- `cli.py`: command-line interface
- `webui.py`: dependency-free read-only HTTP UI

## Current Constraints

- No retry policy
- No timeout sweep
- No explicit `JOIN`
- No nested `DO_WHILE`
- No real Anthropic provider
- No real MCP client
- Web UI is read-only

These constraints are tracked in `tasks.md`.
