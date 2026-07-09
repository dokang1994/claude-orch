"""Fake tool registry for the CALL_MCP_TOOL task type.

Stands in for a real MCP server (`ai/src/.../MCPWorkers.java` in Conductor's
AI module calls out to actual `LIST_MCP_TOOLS`/`CALL_MCP_TOOL` targets).
Swapping this for a real MCP client is tasks.md P2-004.
"""


def _search_files(arguments: dict) -> dict:
    query = arguments.get("query", "")
    return {
        "matches": [
            {"file": "src/LoginAct.asp", "line": 42, "snippet": f"...matched '{query}'..."},
        ]
    }


def _read_file(arguments: dict) -> dict:
    path = arguments.get("path", "src/LoginAct.asp")
    return {
        "path": path,
        "content": 'userId = Request.QueryString("id")\nsql = "SELECT * FROM users WHERE id=" & userId',
    }


def _get_flight_options(arguments: dict) -> dict:
    return {
        "flightId": "KE001",
        "price": 450,
        "from": arguments.get("from"),
        "to": arguments.get("to"),
    }


def _get_hotel_options(arguments: dict) -> dict:
    return {
        "hotelId": "H-742",
        "price": 120,
        "city": arguments.get("city"),
    }


TOOLS = {
    "search_files": _search_files,
    "read_file": _read_file,
    "get_flight_options": _get_flight_options,
    "get_hotel_options": _get_hotel_options,
}


def invoke(tool_name: str, arguments: dict) -> dict:
    handler = TOOLS.get(tool_name)
    if handler is None:
        return {"error": f"unknown tool: {tool_name}", "arguments": arguments}
    return handler(arguments)
