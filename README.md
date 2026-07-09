# orchestrator-lab

A small, local, dependency-free Python re-implementation of the core ideas behind
[`conductor-oss/conductor`](https://github.com/conductor-oss/conductor)'s workflow engine
and its AI/agent orchestration extensions — built to practice the concepts hands-on rather
than to be a production tool.

The design is based on `docs/references/conductor-agent-orchestration-summary.ko.md`, a
write-up of how Conductor's `WorkflowExecutorOps`, `DeciderService`, `ExecutionService`,
and `QueueDAO` fit together, and how it expresses an LLM "think → act → observe" agent loop
as a `DO_WHILE` + `SWITCH` + `CALL_MCP_TOOL` workflow.

## Concept mapping

| Conductor concept | This project |
| --- | --- |
| Workflow definition (JSON) | `workflows/*.json`, loaded by `engine.register_workflow` |
| Workflow execution | a row in the `executions` table (`db.py`) |
| `DeciderService.decide()` | `decider.walk()` — pure function of persisted task state |
| `WorkflowExecutorOps` | `engine.py` — the only module that mutates `executions`/`tasks` |
| `QueueDAO.pop(queueName)` | `engine.claim_next_task(task_types)` — a `status='SCHEDULED'` filter |
| External worker poll/execute/update-result | `workers.execute()` + `engine.update_task()` |
| `LLM_CHAT_COMPLETE` | `llm.MockLLMProvider` (default) / `llm.AnthropicLLMProvider` (exercise, unimplemented) |
| `CALL_MCP_TOOL` | `tools.invoke()` — a hardcoded fake tool registry |
| `SWITCH` / `DO_WHILE` / `FORK_JOIN` | handled entirely inside `decider.walk()`, no worker needed |
| Durable execution / crash recovery | every task transition is a SQLite write; `run --max-steps` + re-run demonstrates resuming |

See `CLAUDE.md` for the known simplifications vs. real Conductor, and `tasks.md` for
exercises that fill each of them in.

## Requirements

Python 3.10+. No third-party dependencies for the core engine (the `anthropic` package is
only needed for the optional P1-002 exercise).

## Setup

```powershell
# from the orchestrator-lab directory
pip install -e .
```

or, without installing anything:

```powershell
$env:PYTHONPATH = "src"
python -m orchestrator.cli demo
```

## Quickstart

```powershell
python -m orchestrator.cli demo
```

This registers all four bundled workflows and runs `think_act_observe_demo` — a DO_WHILE
agent loop — end to end, printing every task transition, then the final execution status.

Explore the individual pieces:

```powershell
python -m orchestrator.cli register workflows/switch_example.json
python -m orchestrator.cli start pricing_switch_demo --input "{\"userTier\": \"gold\"}"
python -m orchestrator.cli run <execution-id>
python -m orchestrator.cli status <execution-id>
python -m orchestrator.cli list
```

### Watching durability/resume in action

`run` supports single-stepping so you can interrupt an execution mid-flight and resume it
later purely from what's in `data/orchestrator.db`:

```powershell
python -m orchestrator.cli start think_act_observe_demo --input "{...}"
python -m orchestrator.cli run <execution-id> --max-steps 1   # Ctrl+C-able; only does one step
python -m orchestrator.cli status <execution-id>               # inspect what's persisted so far
python -m orchestrator.cli run <execution-id> --max-steps 1    # resumes from exactly where it left off
```

Nothing about "where we are in the loop" lives in a Python variable between these
invocations — it's all re-derived from the `tasks` table on every `decide()` call.

## Workflow JSON schema

A workflow definition is `{"name", "version", "tasks": [...], "outputParameters": {...}}`.
Each entry in `tasks` is a step with a `type`:

- **Leaf types** (need a worker): `SIMPLE`, `LLM_CHAT_COMPLETE`, `CALL_MCP_TOOL`, `HUMAN`.
  `input` values may use `"$(expression)"` to pull in prior task outputs or the workflow
  input, e.g. `"tool": "$(tasks['think']['output']['action'])"`.
- **Control types** (resolved by the decider, no worker involved):
  - `SWITCH` — `expression` is evaluated, then `decisionCases[str(value)]` (or
    `defaultCase`) is spliced into the flow.
  - `DO_WHILE` — repeats `loopOver` while `loopCondition` evaluates truthy, capped by
    `maxIterations` (default 50).
  - `FORK_JOIN` — runs each list in `forkTasks` in parallel; joins implicitly once every
    branch is done.
  - `TERMINATE` — ends the workflow immediately.

`expr.py` deliberately supports only a small, `ast`-validated subset of Python
expressions (comparisons, boolean ops, subscripting, literals) — no function calls, no
attribute access. It's a workflow-file sandbox, not a general scripting language.

## Bundled example workflows

| File | Demonstrates |
| --- | --- |
| `hello_world.json` | plain sequential `SIMPLE` tasks |
| `switch_example.json` | `SWITCH` branching |
| `multi_agent_fork_join.json` | `FORK_JOIN` running two "agents" in parallel, then combining results |
| `think_act_observe.json` | the full think-act-observe agent loop via `DO_WHILE` + `SWITCH` + `CALL_MCP_TOOL` |

## Tests

```powershell
python -m unittest discover -s tests
```

## Next steps

Work through `tasks.md` — it's ordered roughly by how much each exercise teaches about
durable agent orchestration, starting with retries (P1-001) and a real LLM-backed think
step (P1-002).
