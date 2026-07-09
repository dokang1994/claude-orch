# orchestrator-lab

A small, local, dependency-free Python re-implementation of the core ideas behind
[`conductor-oss/conductor`](https://github.com/conductor-oss/conductor)'s workflow engine
and its AI/agent orchestration extensions — built to practice the concepts hands-on rather
than to be a production tool.

The design is based on `docs/references/conductor-agent-orchestration-summary.ko.md`, a
write-up of how Conductor's `WorkflowExecutorOps`, `DeciderService`, `ExecutionService`,
and `QueueDAO` fit together, and how it expresses an LLM "think → act → observe" agent loop
as a `DO_WHILE` + `SWITCH` + `CALL_MCP_TOOL` workflow.

## 배경

이 프로젝트는 두 종류의 문서를 기반으로 만들어졌습니다.

- `docs/references/conductor-agent-orchestration-summary.ko.md` — Netflix에서 시작된
  오픈소스 workflow orchestration engine `conductor-oss/conductor`가 LLM/MCP/A2A agent를
  어떻게 durable workflow로 실행하는지 정리한 문서. Workflow definition → Decider →
  Task queue → Worker → 결과 저장 → 다음 task 결정이라는 핵심 루프, 그리고 그 루프로
  think-act-observe agent loop와 multi-agent `FORK_JOIN`을 표현하는 방식을 다룹니다.
- `CLAUDE.md` / `tasks.md` — 대형 프로덕션 코드베이스에서 AI 코딩 에이전트가 안전하게
  작업하기 위한 운영 매뉴얼과 작업 트래커 템플릿(원본은 `claude-config-templates/`에
  별도 보관). 이 저장소의 `CLAUDE.md` / `tasks.md`는 그 템플릿을 이 프로젝트 규모에
  맞게 다시 쓴 버전입니다.

## 이 프로젝트의 의의

일반적인 LLM agent framework(LangChain류)는 "생각 → 도구 호출 → 생각 → 도구 호출" 루프를
하나의 프로세스 메모리 안에서 실행합니다. 빠르게 시작하기엔 좋지만, 프로세스가 죽거나 중간
도구 호출이 실패하면 보통 처음부터 다시 시작해야 합니다. Conductor는 이 루프의 각 단계를
durable task로 쪼개 저장하기 때문에, 서버가 재시작되거나 특정 단계만 실패해도 마지막으로
완료된 지점부터 이어갈 수 있습니다 — 이 저장소가 실습하려는 핵심이 바로 이 지점입니다.

문서를 읽고 넘어가는 것과, 그 원리를 최소 구현으로 직접 만들어 동작을 눈으로 보는 것 사이에는
이해도 차이가 큽니다. 그래서:

- Conductor의 Java 구현을 그대로 옮기는 대신, 핵심만 뽑아 Python 표준 라이브러리만으로
  재구현했습니다: decider는 *영속 상태로부터 다음 행동을 매번 다시 계산하는 순수 함수*라는
  점(`decider.walk()`), task 상태 전이가 곧 durability라는 점, `SWITCH`/`DO_WHILE`/
  `FORK_JOIN`이 하나의 decider 안에서 재귀적으로 처리되는 방식.
- `run --max-steps 1`로 실행을 중간에 멈추고 다시 `run`을 호출해 재개되는 과정을 직접
  확인할 수 있게 만들었습니다 — "durable execution"이 추상적 개념이 아니라 sqlite 파일에
  기록된 task row 몇 개라는 것을 체감하기 위함입니다 (아래 "Watching durability/resume in
  action" 참고).
- `think_act_observe.json` 예제는 요약 문서 8~9절의 "LoginAct.asp 500 에러" 예시를 그대로
  재현해서, 문서에서 읽은 시나리오와 실제로 실행되는 워크플로를 1:1로 대응시켰습니다.
- 이 저장소 자체의 `CLAUDE.md` / `tasks.md` 운영 방식도 outputs 템플릿의 철학(변경을
  작게 유지하고, 실제로 검증한 것만 검증했다고 말하고, 알려진 제약을 숨기지 않고 명시하는
  것)을 그대로 따르고 있습니다. 즉 이 프로젝트는 orchestration 개념 실습인 동시에, 같은
  운영 문서 세트를 실제 프로젝트에 적용해본 사례이기도 합니다.

`tasks.md`에 정리된 실습 과제(재시도 정책, 실제 Anthropic 연동, timeout, nested loop 등)는
의도적으로 미구현 상태로 남겨뒀습니다 — 이 저장소를 계속 실습 대상으로 쓰기 위함입니다.

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
