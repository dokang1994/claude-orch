"""The "brain" of the engine -- mirrors Conductor's DeciderService.

`walk()` is a pure function of (workflow definition, persisted task state):
given the full task history for an execution, it recomputes what should
happen next. It never keeps state of its own between calls. That's the same
trick the real DeciderService uses to make a workflow resumable after a
crash: nothing that matters lives only in memory.

Supported task types:

- Leaf types (need a worker to execute): SIMPLE, LLM_CHAT_COMPLETE,
  CALL_MCP_TOOL, HUMAN.
- Control types (resolved entirely by the decider, no worker involved):
  SWITCH, DO_WHILE, FORK_JOIN, TERMINATE.

Known simplifications vs. real Conductor (see tasks.md for the exercises
that lift these):

- FORK_JOIN always does an implicit join (completes when every branch is
  done) -- there's no separate JOIN task type with `joinOn`.
- DO_WHILE cannot be nested inside another DO_WHILE (`_leaf_ref_names`
  does not recurse into nested loops).
- No retries, no timeouts.
"""

import json
import uuid
from dataclasses import dataclass, field

from . import expr
from .util import now_iso

LEAF_TYPES = {"SIMPLE", "LLM_CHAT_COMPLETE", "CALL_MCP_TOOL", "HUMAN"}


@dataclass
class WalkResult:
    done: bool
    to_schedule: list = field(default_factory=list)
    failed: bool = False
    terminate: bool = False


class ExecContext:
    """Snapshot of one execution's persisted task rows, grouped by ref name."""

    def __init__(self, conn, execution):
        self.conn = conn
        self.execution = execution
        rows = conn.execute(
            "SELECT * FROM tasks WHERE execution_id=? ORDER BY iteration", (execution["id"],)
        ).fetchall()
        self.by_ref: dict[str, list] = {}
        for row in rows:
            self.by_ref.setdefault(row["ref_name"], []).append(row)

    def latest(self, ref_name, iteration=None):
        rows = self.by_ref.get(ref_name)
        if not rows:
            return None
        if iteration is None:
            return rows[-1]
        for row in rows:
            if row["iteration"] == iteration:
                return row
        return None

    def eval_context(self) -> dict:
        tasks_ctx = {}
        for ref, rows in self.by_ref.items():
            last = rows[-1]
            tasks_ctx[ref] = {
                "status": last["status"],
                "output": json.loads(last["output"]) if last["output"] else {},
            }
        return {"tasks": tasks_ctx, "input": json.loads(self.execution["input"])}


def _record_switch(ctx: ExecContext, ref: str, iteration: int, value, chosen_key: str):
    """SWITCH has no worker -- the decider evaluates and completes it inline."""
    now = now_iso()
    task_id = str(uuid.uuid4())
    ctx.conn.execute(
        "INSERT INTO tasks (id, execution_id, ref_name, type, iteration, status, input, output, "
        "retry_count, scheduled_at, started_at, completed_at) VALUES (?,?,?,?,?,?,?,?,0,?,?,?)",
        (
            task_id,
            ctx.execution["id"],
            ref,
            "SWITCH",
            iteration,
            "COMPLETED",
            "{}",
            json.dumps({"value": value, "chosenCase": chosen_key}),
            now,
            now,
            now,
        ),
    )
    ctx.conn.commit()
    row = ctx.conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    ctx.by_ref.setdefault(ref, []).append(row)


def _leaf_ref_names(steps) -> list:
    """Flatten a step list down to the ref names of its leaf (worker) tasks.

    Used to figure out how many DO_WHILE iterations have run so far. Does
    not recurse into nested DO_WHILE (documented limitation -- see tasks.md).
    """
    names = []
    for step in steps:
        stype = step["type"]
        if stype in LEAF_TYPES:
            names.append(step["taskReferenceName"])
        elif stype == "SWITCH":
            for branch in step.get("decisionCases", {}).values():
                names.extend(_leaf_ref_names(branch))
            names.extend(_leaf_ref_names(step.get("defaultCase", [])))
        elif stype == "FORK_JOIN":
            for branch in step["forkTasks"]:
                names.extend(_leaf_ref_names(branch))
        # DO_WHILE intentionally not recursed into: nested loops are an exercise.
    return names


def _current_iteration(ctx: ExecContext, loop_over_steps) -> int:
    max_iteration = 0
    for name in _leaf_ref_names(loop_over_steps):
        rows = ctx.by_ref.get(name)
        if rows:
            max_iteration = max(max_iteration, rows[-1]["iteration"])
    return max_iteration


def walk(steps, ctx: ExecContext, iteration: int = 0) -> WalkResult:
    for step in steps:
        stype = step["type"]
        ref = step["taskReferenceName"]

        if stype in LEAF_TYPES:
            inst = ctx.latest(ref, iteration)
            if inst is None:
                return WalkResult(done=False, to_schedule=[{"ref_name": ref, "type": stype, "iteration": iteration, "step": step}])
            if inst["status"] in ("SCHEDULED", "IN_PROGRESS"):
                return WalkResult(done=False, to_schedule=[])
            if inst["status"] == "FAILED":
                return WalkResult(done=False, to_schedule=[], failed=True)
            continue  # COMPLETED -> proceed to the next step in this sequence

        if stype == "TERMINATE":
            return WalkResult(done=True, to_schedule=[], terminate=True)

        if stype == "SWITCH":
            inst = ctx.latest(ref, iteration)
            cases = step.get("decisionCases", {})
            if inst is None:
                value = expr.evaluate(step["expression"], ctx.eval_context())
                chosen_key = str(value) if str(value) in cases else "__default__"
                chosen_steps = cases.get(str(value), step.get("defaultCase", []))
                _record_switch(ctx, ref, iteration, value, chosen_key)
            else:
                chosen_key = json.loads(inst["output"])["chosenCase"]
                chosen_steps = (
                    step.get("defaultCase", []) if chosen_key == "__default__" else cases.get(chosen_key, [])
                )
            sub = walk(chosen_steps, ctx, iteration)
            if not sub.done:
                return sub
            continue

        if stype == "DO_WHILE":
            loop_over = step["loopOver"]
            iter_n = _current_iteration(ctx, loop_over)
            sub = walk(loop_over, ctx, iteration=iter_n)
            if not sub.done:
                return sub
            if sub.failed:
                return sub
            cond = bool(expr.evaluate(step["loopCondition"], ctx.eval_context()))
            max_iterations = step.get("maxIterations", 50)
            if cond and (iter_n + 1) < max_iterations:
                return walk(loop_over, ctx, iteration=iter_n + 1)
            continue  # loop finished (condition false, or safety cap reached)

        if stype == "FORK_JOIN":
            branch_results = [walk(branch, ctx, iteration) for branch in step["forkTasks"]]
            pending = [r for r in branch_results if not r.done]
            if pending:
                to_schedule = [item for r in pending for item in r.to_schedule]
                failed = any(r.failed for r in pending)
                return WalkResult(done=False, to_schedule=to_schedule, failed=failed)
            continue

        raise ValueError(f"unknown task type: {stype}")

    return WalkResult(done=True, to_schedule=[])


def compute_output(wf: dict, ctx: ExecContext) -> dict:
    params = wf.get("outputParameters")
    eval_ctx = ctx.eval_context()
    if not params:
        return eval_ctx["tasks"]
    return {key: expr.evaluate(expression, eval_ctx) for key, expression in params.items()}
