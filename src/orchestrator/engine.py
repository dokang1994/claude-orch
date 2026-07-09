"""Orchestrates decide/schedule/update -- mirrors Conductor's WorkflowExecutorOps.

This is the only module that mutates `executions` / `tasks`. Everything here
is intentionally synchronous and single-process: `decide()` is called once
when a workflow starts and again every time a worker reports a task result
(`update_task`), exactly matching the loop described in the design doc this
project is based on:

    start/update -> decide -> schedule task -> queue -> worker execute
    -> update task result -> decide again

There is no separate queue table. `claim_next_task` filters the `tasks`
table for `status='SCHEDULED'` rows of the requested type(s) -- that filter
*is* the queue (conceptually the same role Conductor's QueueDAO plays,
just without a real broker behind it).
"""

import json
import uuid

from . import decider, expr
from .util import now_iso


def register_workflow(conn, definition: dict) -> tuple[str, int]:
    name = definition["name"]
    version = definition.get("version", 1)
    conn.execute(
        "INSERT OR REPLACE INTO workflow_definitions (name, version, definition, created_at) VALUES (?,?,?,?)",
        (name, version, json.dumps(definition), now_iso()),
    )
    conn.commit()
    return name, version


def get_workflow(conn, name: str, version: int = 1) -> dict:
    row = conn.execute(
        "SELECT * FROM workflow_definitions WHERE name=? AND version=?", (name, version)
    ).fetchone()
    if not row:
        raise LookupError(f"workflow '{name}' v{version} is not registered")
    return json.loads(row["definition"])


def start_workflow(conn, name: str, version: int = 1, input: dict | None = None) -> str:
    get_workflow(conn, name, version)  # fail fast if not registered
    execution_id = str(uuid.uuid4())
    now = now_iso()
    conn.execute(
        "INSERT INTO executions (id, workflow_name, workflow_version, status, input, output, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (execution_id, name, version, "RUNNING", json.dumps(input or {}), None, now, now),
    )
    conn.commit()
    decide(conn, execution_id)
    return execution_id


def get_execution(conn, execution_id: str):
    row = conn.execute("SELECT * FROM executions WHERE id=?", (execution_id,)).fetchone()
    if not row:
        raise LookupError(f"execution '{execution_id}' not found")
    return row


def list_tasks(conn, execution_id: str):
    return conn.execute(
        "SELECT * FROM tasks WHERE execution_id=? ORDER BY rowid", (execution_id,)
    ).fetchall()


def decide(conn, execution_id: str) -> None:
    execution = get_execution(conn, execution_id)
    if execution["status"] != "RUNNING":
        return

    wf = get_workflow(conn, execution["workflow_name"], execution["workflow_version"])
    ctx = decider.ExecContext(conn, execution)
    result = decider.walk(wf["tasks"], ctx)

    if result.failed:
        conn.execute(
            "UPDATE executions SET status=?, updated_at=? WHERE id=?",
            ("FAILED", now_iso(), execution_id),
        )
        conn.commit()
        return

    if result.done:
        output = decider.compute_output(wf, ctx)
        conn.execute(
            "UPDATE executions SET status=?, output=?, updated_at=? WHERE id=?",
            ("COMPLETED", json.dumps(output), now_iso(), execution_id),
        )
        conn.commit()
        return

    eval_ctx = ctx.eval_context()
    for item in result.to_schedule:
        step = item["step"]
        resolved_input = expr.resolve_value(step.get("input", {}), eval_ctx)
        conn.execute(
            "INSERT INTO tasks (id, execution_id, ref_name, type, iteration, status, input, output, "
            "retry_count, scheduled_at) VALUES (?,?,?,?,?,?,?,?,0,?)",
            (
                str(uuid.uuid4()),
                execution_id,
                item["ref_name"],
                item["type"],
                item["iteration"],
                "SCHEDULED",
                json.dumps(resolved_input),
                None,
                now_iso(),
            ),
        )
    conn.execute("UPDATE executions SET updated_at=? WHERE id=?", (now_iso(), execution_id))
    conn.commit()


def claim_next_task(conn, task_types: list[str]):
    """Poll for one SCHEDULED task of the given type(s) and mark it IN_PROGRESS.

    Stands in for Conductor's `queueDAO.pop()` + `ExecutionService` poll path,
    collapsed into a single call since this project has no real worker
    process boundary.
    """
    placeholders = ",".join("?" for _ in task_types)
    row = conn.execute(
        f"SELECT * FROM tasks WHERE status='SCHEDULED' AND type IN ({placeholders}) "
        "ORDER BY scheduled_at LIMIT 1",
        tuple(task_types),
    ).fetchone()
    if not row:
        return None
    conn.execute("UPDATE tasks SET status='IN_PROGRESS', started_at=? WHERE id=?", (now_iso(), row["id"]))
    conn.commit()
    return conn.execute("SELECT * FROM tasks WHERE id=?", (row["id"],)).fetchone()


def update_task(conn, task_id: str, status: str, output: dict | None = None, reason: str | None = None) -> None:
    conn.execute(
        "UPDATE tasks SET status=?, output=?, completed_at=?, reason=? WHERE id=?",
        (status, json.dumps(output) if output is not None else None, now_iso(), reason, task_id),
    )
    conn.commit()
    row = conn.execute("SELECT execution_id FROM tasks WHERE id=?", (task_id,)).fetchone()
    decide(conn, row["execution_id"])
