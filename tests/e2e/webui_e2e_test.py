"""Playwright E2E tests for the read-only web UI (webui.py).

Not run by `python -m unittest discover -s tests` on purpose: this file is
named `webui_e2e_test.py` (not `test_*.py`) so unittest's default discovery
pattern skips it, keeping the core test suite dependency-free. pytest picks
it up via its own default `*_test.py` pattern.

Setup (once per machine/venv):

    pip install -e ".[test]"
    playwright install chromium   # downloads the browser binary; cached machine-wide

Run:

    pytest tests/e2e
"""

import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_up(base_url: str, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            urllib.request.urlopen(base_url, timeout=0.5)
            return
        except Exception as exc:  # noqa: BLE001 - retry loop, any failure just means "not up yet"
            last_error = exc
            time.sleep(0.2)
    raise TimeoutError(f"server at {base_url} did not start in time") from last_error


@pytest.fixture(scope="module")
def demo_server(tmp_path_factory):
    """Seed a fresh sqlite db with the bundled demo run, then serve it."""
    import os

    db_path = tmp_path_factory.mktemp("webui-e2e") / "orchestrator.db"
    port = _free_port()
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}

    subprocess.run(
        [sys.executable, "-m", "orchestrator.cli", "--db", str(db_path), "demo"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    proc = subprocess.Popen(
        [sys.executable, "-m", "orchestrator.cli", "--db", str(db_path), "serve", "--port", str(port)],
        cwd=ROOT,
        env=env,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_until_up(base_url)
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_executions_list_shows_the_demo_run(demo_server, page):
    page.goto(demo_server)
    rows = page.get_by_test_id("execution-row")
    assert rows.count() == 1
    assert page.get_by_test_id("execution-status").inner_text() == "COMPLETED"


def test_clicking_an_execution_shows_its_task_history(demo_server, page):
    page.goto(demo_server)
    page.get_by_test_id("execution-row").locator("a").click()
    page.wait_for_selector('[data-testid="tasks-table"]')

    # think -> act_or_finish -> tool_call, three loop iterations, then summarize
    assert page.get_by_test_id("task-row").count() == 9
    assert "unvalidated querystring parameter" in page.get_by_test_id("execution-output").inner_text()


def test_unknown_execution_id_returns_404(demo_server, page):
    response = page.goto(f"{demo_server}/executions/does-not-exist")
    assert response.status == 404
