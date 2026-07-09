"""Leaf-task execution -- mirrors Conductor's worker poll/execute/update-result loop.

`execute()` dispatches on task type: SIMPLE tasks look up a handler by ref
name, LLM_CHAT_COMPLETE delegates to an `llm.py` provider, CALL_MCP_TOOL
delegates to the fake registry in `tools.py`, HUMAN prompts on stdin. It
returns `(status, output, reason)` -- it never touches the database itself;
the caller is responsible for calling `engine.update_task()`, keeping this
module a pure "do the work" layer.
"""

import json

from . import decider, engine, llm, tools

SIMPLE_HANDLERS: dict = {}


def simple_handler(ref_name: str):
    def register(fn):
        SIMPLE_HANDLERS[ref_name] = fn
        return fn

    return register


@simple_handler("greet")
def _greet(task_input, ctx):
    name = ctx["input"].get("name", "world")
    return {"message": f"Hello, {name}! Starting the workflow."}


@simple_handler("farewell")
def _farewell(task_input, ctx):
    return {"message": "Workflow finished. Bye!"}


@simple_handler("apply_gold_discount")
def _gold(task_input, ctx):
    return {"discountPercent": 20, "tier": "gold"}


@simple_handler("apply_silver_discount")
def _silver(task_input, ctx):
    return {"discountPercent": 10, "tier": "silver"}


@simple_handler("apply_standard_pricing")
def _standard(task_input, ctx):
    return {"discountPercent": 0, "tier": "standard"}


@simple_handler("combine_results")
def _combine(task_input, ctx):
    flights = ctx["tasks"].get("book_flight", {}).get("output", {})
    hotels = ctx["tasks"].get("book_hotel", {}).get("output", {})
    summary = f"Booked flight {flights.get('flightId', '?')} and hotel {hotels.get('hotelId', '?')}"
    return {"summary": summary, "flights": flights, "hotels": hotels}


@simple_handler("summarize")
def _summarize(task_input, ctx):
    return {"answer": ctx["tasks"].get("think", {}).get("output", {}).get("answer")}


def build_eval_context(conn, execution_id: str) -> dict:
    execution = engine.get_execution(conn, execution_id)
    return decider.ExecContext(conn, execution).eval_context()


def _run_human_task(task, task_input: dict) -> dict:
    prompt = task_input.get("prompt", "Approve this step?")
    answer = input(f"[HUMAN TASK:{task['ref_name']}] {prompt} (y/n) > ").strip().lower()
    return {"approved": answer in ("y", "yes"), "respondedBy": "cli-user"}


def execute(conn, task, execution_id: str, llm_provider=None):
    """Run one leaf task. Returns (status, output, reason)."""
    task_input = json.loads(task["input"]) if task["input"] else {}
    ctx = build_eval_context(conn, execution_id)
    ttype = task["type"]
    try:
        if ttype == "SIMPLE":
            handler = SIMPLE_HANDLERS.get(task["ref_name"])
            if handler is None:
                return "COMPLETED", {"echo": task_input}, None
            return "COMPLETED", handler(task_input, ctx), None

        if ttype == "LLM_CHAT_COMPLETE":
            provider = llm_provider or llm.MockLLMProvider()
            return "COMPLETED", provider.chat(task, ctx), None

        if ttype == "CALL_MCP_TOOL":
            tool_name = task_input.get("tool")
            arguments = task_input.get("arguments", {})
            return "COMPLETED", tools.invoke(tool_name, arguments), None

        if ttype == "HUMAN":
            return "COMPLETED", _run_human_task(task, task_input), None

        return "FAILED", None, f"no worker registered for task type {ttype}"
    except Exception as exc:  # a failed leaf task fails the task, not the process
        return "FAILED", None, str(exc)
