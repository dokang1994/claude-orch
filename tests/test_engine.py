import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator import db, engine  # noqa: E402

HELLO_WORLD = {
    "name": "hello_world_test",
    "version": 1,
    "tasks": [
        {"name": "greet", "taskReferenceName": "greet", "type": "SIMPLE", "input": {}},
        {"name": "farewell", "taskReferenceName": "farewell", "type": "SIMPLE", "input": {}},
    ],
    "outputParameters": {"greeting": "tasks['greet']['output']['message']"},
}


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.conn = db.connect(self.tmp.name)

    def tearDown(self):
        self.conn.close()
        os.unlink(self.tmp.name)

    def test_start_workflow_schedules_first_task_only(self):
        engine.register_workflow(self.conn, HELLO_WORLD)
        execution_id = engine.start_workflow(self.conn, "hello_world_test", 1, {"name": "Do"})
        tasks = engine.list_tasks(self.conn, execution_id)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["ref_name"], "greet")
        self.assertEqual(tasks[0]["status"], "SCHEDULED")

    def test_completing_tasks_advances_and_completes_workflow(self):
        engine.register_workflow(self.conn, HELLO_WORLD)
        execution_id = engine.start_workflow(self.conn, "hello_world_test", 1, {"name": "Do"})

        greet = engine.list_tasks(self.conn, execution_id)[0]
        engine.update_task(self.conn, greet["id"], "COMPLETED", {"message": "Hello, Do!"})

        tasks = engine.list_tasks(self.conn, execution_id)
        self.assertEqual([t["ref_name"] for t in tasks], ["greet", "farewell"])

        farewell = tasks[1]
        engine.update_task(self.conn, farewell["id"], "COMPLETED", {"message": "bye"})

        execution = engine.get_execution(self.conn, execution_id)
        self.assertEqual(execution["status"], "COMPLETED")
        self.assertEqual(json.loads(execution["output"])["greeting"], "Hello, Do!")

    def test_failed_leaf_task_fails_the_execution(self):
        engine.register_workflow(self.conn, HELLO_WORLD)
        execution_id = engine.start_workflow(self.conn, "hello_world_test", 1, {})
        greet = engine.list_tasks(self.conn, execution_id)[0]
        engine.update_task(self.conn, greet["id"], "FAILED", reason="boom")
        execution = engine.get_execution(self.conn, execution_id)
        self.assertEqual(execution["status"], "FAILED")
        # a terminal execution's decide() is a no-op: no farewell task appears
        self.assertEqual(len(engine.list_tasks(self.conn, execution_id)), 1)


if __name__ == "__main__":
    unittest.main()
