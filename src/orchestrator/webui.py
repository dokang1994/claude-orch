"""Minimal read-only web UI for inspecting executions -- tasks.md P3-002.

Deliberately dependency-free (stdlib `http.server`) so the runtime engine
stays zero-dependency; Playwright is a *test-only* dependency (see the
`test` extra in pyproject.toml and tests/e2e/) that drives this page in a
real browser rather than something the app itself needs.

Every element a test might want to assert on carries a stable
`data-testid` attribute instead of relying on CSS classes or text content,
which is what tests/e2e/test_webui.py selects on.
"""

import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import db as db_module
from . import engine


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #111; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
  th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.9rem; }}
  th {{ background: #f2f2f2; }}
  .status-COMPLETED {{ color: #087f23; font-weight: 600; }}
  .status-FAILED {{ color: #b00020; font-weight: 600; }}
  .status-RUNNING {{ color: #1565c0; font-weight: 600; }}
  a {{ color: #1565c0; }}
  pre {{ background: #f7f7f7; padding: 0.75rem; overflow-x: auto; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
{body}
</body>
</html>"""


def _executions_page(conn) -> str:
    rows = conn.execute(
        "SELECT id, workflow_name, status, created_at FROM executions ORDER BY created_at DESC"
    ).fetchall()
    parts = [
        '<table data-testid="executions-table"><tr><th>Execution</th><th>Workflow</th>'
        "<th>Status</th><th>Created</th></tr>"
    ]
    for row in rows:
        parts.append(
            '<tr data-testid="execution-row">'
            f'<td><a href="/executions/{row["id"]}">{row["id"][:8]}</a></td>'
            f'<td>{html.escape(row["workflow_name"])}</td>'
            f'<td class="status-{row["status"]}" data-testid="execution-status">{row["status"]}</td>'
            f'<td>{row["created_at"]}</td></tr>'
        )
    parts.append("</table>")
    if not rows:
        parts.append('<p data-testid="empty-state">No executions yet -- run `orchestrator start`.</p>')
    return _page("orchestrator-lab executions", "\n".join(parts))


def _execution_detail_page(conn, execution_id: str) -> str:
    execution = engine.get_execution(conn, execution_id)  # raises LookupError -> 404
    tasks = engine.list_tasks(conn, execution_id)
    parts = [
        '<p><a href="/">&larr; back</a></p>',
        f'<p data-testid="execution-status" class="status-{execution["status"]}">{execution["status"]}</p>',
        f'<h3>input</h3><pre data-testid="execution-input">{html.escape(execution["input"])}</pre>',
    ]
    if execution["output"]:
        parts.append(f'<h3>output</h3><pre data-testid="execution-output">{html.escape(execution["output"])}</pre>')
    parts.append(
        '<table data-testid="tasks-table"><tr><th>Ref</th><th>Type</th><th>Iteration</th><th>Status</th></tr>'
    )
    for t in tasks:
        parts.append(
            '<tr data-testid="task-row">'
            f'<td>{html.escape(t["ref_name"])}</td><td>{t["type"]}</td>'
            f'<td>{t["iteration"]}</td>'
            f'<td class="status-{t["status"]}" data-testid="task-status">{t["status"]}</td></tr>'
        )
    parts.append("</table>")
    return _page(f"execution {execution_id[:8]}", "\n".join(parts))


class Handler(BaseHTTPRequestHandler):
    db_path = None  # set by serve() before the server starts

    def _respond(self, status: int, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler's naming convention)
        parsed = urlparse(self.path)
        conn = db_module.connect(self.db_path)
        try:
            if parsed.path == "/":
                self._respond(200, _executions_page(conn))
            elif parsed.path.startswith("/executions/"):
                execution_id = parsed.path.removeprefix("/executions/")
                try:
                    self._respond(200, _execution_detail_page(conn, execution_id))
                except LookupError:
                    self._respond(404, _page("not found", "<p>No such execution.</p>"))
            else:
                self._respond(404, _page("not found", "<p>Unknown path.</p>"))
        finally:
            conn.close()

    def log_message(self, format, *args) -> None:  # noqa: A002
        pass  # keep demo/test output quiet; use --verbose logging elsewhere if you need it


def serve(db_path=None, port: int = 8765) -> None:
    Handler.db_path = db_path
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"orchestrator web UI at http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
