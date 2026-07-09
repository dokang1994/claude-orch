"""Command-line entry point.

    orchestrator demo                          # register bundled workflows, run the flagship demo
    orchestrator register workflows/x.json
    orchestrator start <workflow-name> --input '{"...": "..."}'
    orchestrator run <execution-id> [--max-steps N]
    orchestrator status <execution-id>
    orchestrator list
"""

import argparse
import json
from pathlib import Path

from . import db, engine, llm, workers

WORKFLOWS_DIR = Path(__file__).resolve().parents[2] / "workflows"


def _print_task_row(row) -> None:
    print(f"  [{row['type']:<16}] {row['ref_name']:<20} iter={row['iteration']} status={row['status']}")


def cmd_register(args) -> None:
    conn = db.connect(args.db)
    definition = json.loads(Path(args.file).read_text(encoding="utf-8"))
    name, version = engine.register_workflow(conn, definition)
    print(f"registered {name} v{version}")


def cmd_start(args) -> None:
    conn = db.connect(args.db)
    input_data = json.loads(args.input) if args.input else {}
    execution_id = engine.start_workflow(conn, args.name, args.version, input_data)
    print(execution_id)


def cmd_run(args) -> None:
    conn = db.connect(args.db)
    provider = llm.MockLLMProvider()
    steps = 0
    while True:
        execution = engine.get_execution(conn, args.execution_id)
        if execution["status"] != "RUNNING":
            print(f"execution {args.execution_id} -> {execution['status']}")
            break
        task = engine.claim_next_task(conn, ["SIMPLE", "LLM_CHAT_COMPLETE", "CALL_MCP_TOOL", "HUMAN"])
        if task is None:
            print("no schedulable task found while execution is still RUNNING -- inspect with `status`")
            break
        status, output, reason = workers.execute(conn, task, args.execution_id, llm_provider=provider)
        engine.update_task(conn, task["id"], status, output, reason)
        print(f"  {task['type']:<16} {task['ref_name']:<20} iter={task['iteration']} -> {status}")
        if output:
            print(f"    output: {json.dumps(output, ensure_ascii=False)}")
        if reason:
            print(f"    reason: {reason}")
        steps += 1
        if args.max_steps and steps >= args.max_steps:
            print(f"stopped after {steps} step(s) (--max-steps). Re-run `run {args.execution_id}` to resume.")
            break


def cmd_status(args) -> None:
    conn = db.connect(args.db)
    execution = engine.get_execution(conn, args.execution_id)
    print(f"execution {execution['id']}  workflow={execution['workflow_name']} v{execution['workflow_version']}  status={execution['status']}")
    print(f"input:  {execution['input']}")
    if execution["output"]:
        print(f"output: {execution['output']}")
    print("tasks:")
    for row in engine.list_tasks(conn, args.execution_id):
        _print_task_row(row)


def cmd_list(args) -> None:
    conn = db.connect(args.db)
    rows = conn.execute(
        "SELECT id, workflow_name, status, created_at FROM executions ORDER BY created_at DESC"
    ).fetchall()
    for row in rows:
        print(f"{row['id']}  {row['workflow_name']:<28} {row['status']:<10} {row['created_at']}")


def cmd_demo(args) -> None:
    conn = db.connect(args.db)
    for f in sorted(WORKFLOWS_DIR.glob("*.json")):
        definition = json.loads(f.read_text(encoding="utf-8"))
        engine.register_workflow(conn, definition)
        print(f"registered {definition['name']}")

    print("\n--- running think_act_observe_demo (DO_WHILE agent loop) ---")
    execution_id = engine.start_workflow(
        conn,
        "think_act_observe_demo",
        1,
        {
            "question": "Why is LoginAct.asp throwing a 500?",
            "scriptedPlan": [
                {"action": "search_files", "arguments": {"query": "LoginAct.asp 500"}},
                {"action": "read_file", "arguments": {"path": "src/LoginAct.asp"}},
                {"action": "finish", "answer": "An unvalidated querystring parameter is concatenated straight into the SQL query."},
            ],
        },
    )
    args.execution_id = execution_id
    args.max_steps = None
    cmd_run(args)
    cmd_status(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="orchestrator", description="Toy durable workflow/agent orchestration engine for practice."
    )
    parser.add_argument("--db", default=None, help="path to sqlite db (default: ./data/orchestrator.db)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("register", help="register a workflow definition JSON file")
    p.add_argument("file")
    p.set_defaults(func=cmd_register)

    p = sub.add_parser("start", help="start a new workflow execution")
    p.add_argument("name")
    p.add_argument("--version", type=int, default=1)
    p.add_argument("--input", default=None, help="JSON input for the execution")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("run", help="poll and execute schedulable tasks until the execution finishes or blocks")
    p.add_argument("execution_id")
    p.add_argument("--max-steps", type=int, default=None, help="stop after N steps (Ctrl+C-then-resume demo)")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("status", help="show execution + task states")
    p.add_argument("execution_id")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("list", help="list executions")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("demo", help="register bundled workflows and run the think-act-observe demo end to end")
    p.set_defaults(func=cmd_demo)

    return parser


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
