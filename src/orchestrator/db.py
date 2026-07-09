import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "orchestrator.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_definitions (
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    definition TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (name, version)
);

CREATE TABLE IF NOT EXISTS executions (
    id TEXT PRIMARY KEY,
    workflow_name TEXT NOT NULL,
    workflow_version INTEGER NOT NULL,
    status TEXT NOT NULL,
    input TEXT NOT NULL,
    output TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    ref_name TEXT NOT NULL,
    type TEXT NOT NULL,
    iteration INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    input TEXT,
    output TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    scheduled_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_execution ON tasks(execution_id);
"""


def connect(db_path=None) -> sqlite3.Connection:
    """Open (and lazily initialize) the sqlite file that holds all durable state.

    This table set is the whole "durability" story: kill the process at any
    point and a fresh `connect()` + `decide()` picks up exactly where the
    tasks table left off.
    """
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn
