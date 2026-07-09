"""LLM providers for the LLM_CHAT_COMPLETE task type.

`MockLLMProvider` is what `workers.execute()` uses by default: it replays a
scripted plan from the workflow input instead of calling a real model, so
the whole engine (including the DO_WHILE agent loop) can be exercised
offline, deterministically, for free.

`AnthropicLLMProvider` is an intentionally unfinished exercise -- see
tasks.md P1-002.
"""


class MockLLMProvider:
    """Deterministic stand-in for a "think" step.

    Reads `ctx['input']['scriptedPlan']`, a list of steps shaped like:

        {"action": "search_files", "arguments": {"query": "..."}}
        {"action": "finish", "answer": "..."}

    and returns the one at index `task['iteration']` (the DO_WHILE loop
    iteration this particular `think` call belongs to), translated into the
    `{"done": ..., "action"/"answer": ...}` shape the workflow's SWITCH step
    branches on.
    """

    def chat(self, task, ctx: dict) -> dict:
        plan = ctx["input"].get("scriptedPlan", [])
        idx = task["iteration"]
        if idx >= len(plan):
            return {"done": True, "answer": "Scripted plan ran out of steps before finishing."}
        step = plan[idx]
        if step["action"] == "finish":
            return {"done": True, "answer": step["answer"]}
        return {
            "done": False,
            "action": step["action"],
            "arguments": step.get("arguments", {}),
            "reason": "scripted plan step",
        }


class AnthropicLLMProvider:
    """Exercise: back the `think` step with a real Claude call.

    See tasks.md P1-002 for the full spec. Once implemented, `chat()` should
    still return the same shape `MockLLMProvider.chat()` does, so it's a
    drop-in replacement wherever `llm_provider=` is passed (see
    `workers.execute` and `cli.py`).
    """

    def __init__(self, model: str = "claude-sonnet-5", api_key: str | None = None):
        self.model = model
        self.api_key = api_key

    def chat(self, task, ctx: dict) -> dict:
        raise NotImplementedError(
            "Implement this with the anthropic Python SDK: send ctx['input']['question'] "
            "plus the history of prior tool_call outputs from ctx['tasks'], and return a dict "
            "shaped like {'done': False, 'action': str, 'arguments': dict, 'reason': str} or "
            "{'done': True, 'answer': str}. See tasks.md P1-002."
        )
