"""A deliberately tiny, restricted expression evaluator.

Workflow JSON needs a way to say things like:

    "tasks['think']['output']['done'] == False"

Conductor's real engine backs this with a JSONPath-ish templating language.
Building that is out of scope here, but bare `eval()`/`exec()` on
user-editable workflow files is a real injection risk even in a local tool,
so this module allow-lists a small subset of Python's expression grammar
(comparisons, boolean ops, subscripting, literals -- no calls, no attribute
access, no imports) and rejects anything outside of it before evaluating.
"""

import ast

_ALLOWED_NODES = (
    ast.Expression,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Subscript,
    ast.List,
    ast.Tuple,
    ast.Dict,
)


class UnsafeExpressionError(ValueError):
    pass


def _validate(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise UnsafeExpressionError(f"disallowed expression element: {type(node).__name__}")


def evaluate(expression: str, context: dict):
    """Evaluate a restricted expression against `context` (e.g. {"tasks": ..., "input": ...})."""
    tree = ast.parse(expression, mode="eval")
    _validate(tree)
    return eval(compile(tree, "<workflow-expression>", "eval"), {"__builtins__": {}}, dict(context))


def resolve_value(value, context: dict):
    """Resolve `$(...)` templated values inside task `input` dicts/lists, recursively.

    A plain string is returned unchanged unless it is wrapped exactly as
    `$(expression)`, in which case the inner expression is evaluated via
    `evaluate()` above and its result substituted.
    """
    if isinstance(value, str) and value.startswith("$(") and value.endswith(")"):
        return evaluate(value[2:-1], context)
    if isinstance(value, dict):
        return {k: resolve_value(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_value(v, context) for v in value]
    return value
