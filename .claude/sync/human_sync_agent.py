from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sync.mntn_skill_adapter import MntnSkillAdapter
from sync.sync_policy import load_policy
from sync.sync_queue import SyncQueue


class HumanSyncAgent:
    def __init__(self, agent_root: Path, workspace: Path):
        self.agent_root = agent_root
        self.workspace = workspace
        self.queue = SyncQueue(workspace)
        self.policy = load_policy(agent_root)
        self.adapter = MntnSkillAdapter(
            timeout_seconds=int(self.policy.get("mntn_skill", {}).get("timeout_seconds", 5)),
            fail_open=bool(self.policy.get("mntn_skill", {}).get("fail_open", True)),
        )

    def flush_round(self, state: dict[str, Any], round_result: dict[str, Any]) -> dict[str, Any]:
        if not state.get("sync", {}).get("enabled", True) or not self.policy.get("enabled", True):
            result = {"ok": False, "reason": "sync disabled"}
            self.queue.log({"action": "flush_round", "result": result})
            return result

        payload = {
            "type": "round_summary",
            "round": round_result.get("round"),
            "phase": round_result.get("phase_after"),
            "category": round_result.get("category"),
            "status": round_result.get("status"),
            "message": summarize_round(round_result),
            "artifacts": round_result.get("new_artifacts", []),
            "events": self.queue.read_events(limit=20),
        }
        policy_decision = self.should_submit(payload)
        if not policy_decision["ok"]:
            result = {"ok": False, "skipped": True, "reason": policy_decision["reason"]}
            self.queue.log({"action": "flush_round", "payload": payload, "result": result})
            return result

        result = self.submit_with_retries(payload)
        record = {"action": "flush_round", "payload": payload, "result": result}
        if not result.get("ok") and self.policy.get("spool", {}).get("enabled", True):
            self.queue.spool(record)
        self.queue.log(record)
        return result

    def should_submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        frequency = self.policy.get("frequency", {})
        logs = self.read_sync_logs()
        current_round = payload.get("round")
        if frequency.get("dedupe_same_message", True):
            for log in reversed(logs[-20:]):
                old_payload = log.get("payload") or {}
                if old_payload.get("message") == payload.get("message") and old_payload.get("round") == current_round:
                    return {"ok": False, "reason": "duplicate sync message for round"}

        max_per_round = int(frequency.get("max_messages_per_round", 3))
        sent_this_round = sum(1 for log in logs if (log.get("payload") or {}).get("round") == current_round)
        if sent_this_round >= max_per_round:
            return {"ok": False, "reason": "max sync messages per round reached"}

        min_interval = int(frequency.get("min_interval_seconds", 15))
        last_time = latest_log_time(logs)
        if last_time is not None and time.time() - last_time < min_interval:
            return {"ok": False, "reason": "sync rate limited"}
        return {"ok": True, "reason": "sync allowed"}

    def submit_with_retries(self, payload: dict[str, Any]) -> dict[str, Any]:
        mntn = self.policy.get("mntn_skill", {})
        max_retries = int(mntn.get("max_retries", 3))
        backoff = float(mntn.get("retry_backoff_seconds", 10))
        last_result: dict[str, Any] = {"ok": False, "reason": "not attempted"}
        for attempt in range(1, max_retries + 1):
            last_result = self.adapter.submit(payload)
            last_result["attempt"] = attempt
            if last_result.get("ok"):
                return last_result
            if attempt < max_retries and self.adapter.endpoint:
                time.sleep(backoff)
        return last_result

    def read_sync_logs(self) -> list[dict[str, Any]]:
        logs: list[dict[str, Any]] = []
        if not self.queue.log_path.exists():
            return logs
        try:
            lines = self.queue.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return logs
        for line in lines:
            if not line.strip():
                continue
            try:
                logs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return logs


def summarize_round(round_result: dict[str, Any]) -> str:
    loop = round_result.get("loop") or {}
    conclusion = loop.get("conclusion") or round_result.get("failure_reason") or round_result.get("status")
    next_experiment = loop.get("next_experiment") or round_result.get("next_plan") or "n/a"
    return f"Round {round_result.get('round')} {round_result.get('status')}: {conclusion}. Next: {next_experiment}"


def latest_log_time(logs: list[dict[str, Any]]) -> float | None:
    for log in reversed(logs):
        raw_time = log.get("time")
        if raw_time:
            try:
                return datetime.fromisoformat(raw_time).timestamp()
            except ValueError:
                pass
    return None
