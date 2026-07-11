from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from hooks.post_tool_check import normalize_task_result
from runner.execution_lifecycle import (
    CHALLENGE_HANDOFF_PROTOCOL,
    TASK_HANDOFF_PROTOCOL,
    handoff_updated_since,
    recovery_notice,
)
from runner.paths import ensure_workspace_dirs
from runner.round_manager import RoundManager
from runner.state_store import DEFAULT_STATE


AGENT_ROOT = Path(__file__).resolve().parents[1]
HOOK = AGENT_ROOT / "hooks" / "hook_entrypoint.py"


class ExecutionLifecycleTests(unittest.TestCase):
    def test_handoff_must_be_newer_than_execution(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            handoff = workspace / "handoff.md"
            handoff.write_text("# Handoff\n", encoding="utf-8")
            started_at_ns = handoff.stat().st_mtime_ns + 1_000_000
            self.assertFalse(handoff_updated_since(workspace, started_at_ns))
            os.utime(handoff, ns=(started_at_ns + 1_000_000, started_at_ns + 1_000_000))
            self.assertTrue(handoff_updated_since(workspace, started_at_ns))

    def test_unfinished_execution_creates_recovery_notice(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            (workspace / "progress.jsonl").write_text(
                json.dumps(
                    {
                        "event": "execution_started",
                        "execution_id": "exec_001_test",
                        "round": 1,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            notice = recovery_notice(workspace)
            self.assertIn("no matching execution_completed", notice)
            self.assertIn("exec_001_test", notice)

    def test_complete_execution_clears_recovery_notice(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            events = [
                {"event": "execution_started", "execution_id": "exec_001_test", "round": 1},
                {
                    "event": "execution_completed",
                    "execution_id": "exec_001_test",
                    "round": 1,
                    "checkpoint_status": "complete",
                },
            ]
            (workspace / "progress.jsonl").write_text(
                "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
            )
            self.assertEqual(recovery_notice(workspace), "")


class HookCheckpointTests(unittest.TestCase):
    def run_hook(self, workspace: Path, mode: str, payload: dict, started_at_ns: int) -> dict:
        env = os.environ.copy()
        env.update(
            {
                "AIXCTF_AGENT_ROOT": str(AGENT_ROOT),
                "WORKDIR": str(workspace),
                "AIXCTF_EXECUTION_ID": "exec_test",
                "AIXCTF_EXECUTION_STARTED_AT_NS": str(started_at_ns),
            }
        )
        proc = subprocess.run(
            [sys.executable, str(HOOK), mode],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_stop_blocks_once_when_handoff_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            handoff = workspace / "handoff.md"
            handoff.write_text("# Old Handoff\n", encoding="utf-8")
            started_at_ns = handoff.stat().st_mtime_ns + 1_000_000
            result = self.run_hook(workspace, "stop", {"stop_hook_active": False}, started_at_ns)
            self.assertEqual(result.get("decision"), "block")
            result = self.run_hook(workspace, "stop", {"stop_hook_active": True}, started_at_ns)
            self.assertNotIn("decision", result)

    def test_stop_allows_fresh_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            handoff = workspace / "handoff.md"
            handoff.write_text("# Current Handoff\n", encoding="utf-8")
            started_at_ns = max(1, handoff.stat().st_mtime_ns - 1_000_000)
            result = self.run_hook(workspace, "stop", {"stop_hook_active": False}, started_at_ns)
            self.assertNotIn("decision", result)

    def test_precompact_blocks_automatic_compaction(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            result = self.run_hook(Path(raw), "pre_compact", {"trigger": "auto"}, 1)
            self.assertEqual(result.get("decision"), "block")


class ProtocolVersionTests(unittest.TestCase):
    def test_challenge_state_declares_protocol(self) -> None:
        self.assertEqual(DEFAULT_STATE["handoff_protocol_version"], CHALLENGE_HANDOFF_PROTOCOL)

    def test_task_result_declares_protocol(self) -> None:
        result = normalize_task_result("task_001", {}, {}, "done", "")
        self.assertEqual(result["protocol_version"], TASK_HANDOFF_PROTOCOL)


class ModelOwnedHandoffTests(unittest.TestCase):
    def test_real_execution_preserves_model_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            ensure_workspace_dirs(workspace)
            (workspace / "handoff.md").write_text("# Previous Handoff\n", encoding="utf-8")
            manager = RoundManager(AGENT_ROOT, workspace)

            def fake_run(round_id: int, prompt: str, timeout: int, dry_run: bool, execution: dict) -> dict:
                self.assertFalse(dry_run)
                self.assertIn("# Previous Handoff", prompt)
                (workspace / "handoff.md").write_text("# Model Handoff\n\nContinue from the leak.\n", encoding="utf-8")
                output = {
                    "research_question": "Can the current leak be stabilized?",
                    "hypothesis": "The existing script is a valid baseline.",
                    "experiment": "Preserve the current semantic checkpoint.",
                    "observations": ["Model-owned handoff was updated."],
                    "evidence": [],
                    "conclusion": "Continue from the leak.",
                    "state_delta": {},
                    "candidate_flags": [],
                    "confirmed_flag": None,
                    "failure_reason": None,
                    "next_experiment": "Validate the leak remotely.",
                    "do_not_repeat": [],
                }
                return {"mode": "real", "exit_code": 0, "stdout": json.dumps(output), "stderr": "", "log_path": ""}

            manager.claude_runner.run = fake_run  # type: ignore[method-assign]
            state = deepcopy(DEFAULT_STATE)
            state["sync"]["enabled"] = False
            result = manager.run_round(
                1,
                state,
                {"summary": "Test challenge"},
                {"max_command_seconds": 30},
                False,
            )
            self.assertEqual((workspace / "handoff.md").read_text(), "# Model Handoff\n\nContinue from the leak.\n")
            self.assertEqual(result["execution"]["checkpoint_status"], "complete")


if __name__ == "__main__":
    unittest.main()
