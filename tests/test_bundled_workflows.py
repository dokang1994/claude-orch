"""Runs every bundled workflow in workflows/*.json end to end.

These double as regression tests for decider.py's SWITCH / DO_WHILE /
FORK_JOIN handling, and as a guard against the example JSON files rotting.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orchestrator import db, engine, llm, workers  # noqa: E402

WORKFLOWS_DIR = ROOT / "workflows"


def run_to_completion(conn, execution_id, max_steps=100):
    provider = llm.MockLLMProvider()
    for _ in range(max_steps):
        execution = engine.get_execution(conn, execution_id)
        if execution["status"] != "RUNNING":
            return execution
        task = engine.claim_next_task(conn, ["SIMPLE", "LLM_CHAT_COMPLETE", "CALL_MCP_TOOL", "HUMAN"])
        if task is None:
            raise AssertionError("workflow stuck: no schedulable task but execution is still RUNNING")
        status, output, reason = workers.execute(conn, task, execution_id, llm_provider=provider)
        engine.update_task(conn, task["id"], status, output, reason)
    raise AssertionError(f"execution did not reach a terminal state within {max_steps} steps")


class BundledWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.conn = db.connect(self.tmp.name)
        for f in WORKFLOWS_DIR.glob("*.json"):
            engine.register_workflow(self.conn, json.loads(f.read_text(encoding="utf-8")))

    def tearDown(self):
        self.conn.close()
        os.unlink(self.tmp.name)

    def test_hello_world(self):
        execution_id = engine.start_workflow(self.conn, "hello_world", 1, {"name": "world"})
        execution = run_to_completion(self.conn, execution_id)
        self.assertEqual(execution["status"], "COMPLETED")

    def test_switch_routes_to_gold_case(self):
        execution_id = engine.start_workflow(self.conn, "pricing_switch_demo", 1, {"userTier": "gold"})
        execution = run_to_completion(self.conn, execution_id)
        self.assertEqual(execution["status"], "COMPLETED")
        refs = [t["ref_name"] for t in engine.list_tasks(self.conn, execution_id)]
        self.assertIn("apply_gold_discount", refs)
        self.assertNotIn("apply_silver_discount", refs)
        self.assertNotIn("apply_standard_pricing", refs)

    def test_switch_routes_unknown_tier_to_default_case(self):
        execution_id = engine.start_workflow(self.conn, "pricing_switch_demo", 1, {"userTier": "unknown"})
        execution = run_to_completion(self.conn, execution_id)
        refs = [t["ref_name"] for t in engine.list_tasks(self.conn, execution_id)]
        self.assertIn("apply_standard_pricing", refs)

    def test_fork_join_runs_both_branches_and_combines(self):
        execution_id = engine.start_workflow(self.conn, "multi_agent_trip_planner", 1, {"from": "ICN", "to": "SFO"})
        execution = run_to_completion(self.conn, execution_id)
        self.assertEqual(execution["status"], "COMPLETED")
        refs = {t["ref_name"] for t in engine.list_tasks(self.conn, execution_id)}
        self.assertTrue({"book_flight", "book_hotel", "combine_results"} <= refs)
        self.assertIn("KE001", json.loads(execution["output"])["summary"])

    def test_think_act_observe_loop_runs_scripted_plan_to_completion(self):
        execution_id = engine.start_workflow(
            self.conn,
            "think_act_observe_demo",
            1,
            {
                "question": "why does it break",
                "scriptedPlan": [
                    {"action": "search_files", "arguments": {"query": "x"}},
                    {"action": "finish", "answer": "done"},
                ],
            },
        )
        execution = run_to_completion(self.conn, execution_id)
        self.assertEqual(execution["status"], "COMPLETED")

        think_tasks = [t for t in engine.list_tasks(self.conn, execution_id) if t["ref_name"] == "think"]
        self.assertEqual(len(think_tasks), 2, "expected two loop iterations: one tool call, then finish")

        tool_calls = [t for t in engine.list_tasks(self.conn, execution_id) if t["ref_name"] == "tool_call"]
        self.assertEqual(len(tool_calls), 1)

        self.assertEqual(json.loads(execution["output"])["answer"], "done")


if __name__ == "__main__":
    unittest.main()
