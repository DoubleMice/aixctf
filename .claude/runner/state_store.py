from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_STATE: dict[str, Any] = {
    "challenge_id": "unknown",
    "category": "unknown",
    "phase": "init",
    "round": 0,
    "solved": False,
    "confirmed_flag": None,
    "candidate_flags": [],
    "evidence_records": [],
    "allowed_scope": {"targets": [], "hosts": [], "ports": [], "urls": []},
    "artifacts": {"scripts": [], "logs": [], "evidence": [], "subtasks": []},
    "research_loop": {
        "current_question": None,
        "current_hypothesis": None,
        "active_strategy": None,
        "last_action": None,
        "last_observation": None,
        "evidence_collected": [],
        "known_facts": [],
        "falsified_hypotheses": [],
        "open_questions": [],
        "next_experiment": None,
    },
    "hypotheses": [],
    "failures": [],
    "do_not_repeat": [],
    "last_observation": "",
    "next_plan": "",
    "recent_docs": [],
    "scheduler": {"status": "pending", "pause_reason": None, "updated_at": None},
    "runtime_limits": {"max_rounds": 12, "max_seconds": 7200, "max_command_seconds": 7200},
    "sync": {"enabled": True, "last_sync_at": None, "last_sync_event_id": None},
    "created_at": None,
    "updated_at": None,
}


class StateStore:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.path = workspace / "state.json"

    def load_or_create(self, initial: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.path.exists():
            try:
                state = self._read_json(self.path)
                return self.validate(state)
            except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
                return self.recover_from_unreadable_state(initial, exc)

        state = copy.deepcopy(DEFAULT_STATE)
        if initial:
            state = self.deep_merge(state, initial)
        now = utc_now()
        state["created_at"] = now
        state["updated_at"] = now
        state = self.validate(state)
        self.save(state)
        return state

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self.load_or_create()
        try:
            return self.validate(self._read_json(self.path))
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            return self.recover_from_unreadable_state(None, exc)

    def save(self, state: dict[str, Any]) -> None:
        state = self.validate(state)
        state["updated_at"] = utc_now()
        self._atomic_write_json(self.path, state)
        snap_round = safe_int(state.get("round", 0), 0, minimum=0)
        snap = self.workspace / "state_snapshots" / f"round_{snap_round:03d}_{compact_timestamp()}.json"
        try:
            self._atomic_write_json(snap, state)
        except Exception:
            pass

    def apply_round_result(self, state: dict[str, Any], round_result: dict[str, Any]) -> dict[str, Any]:
        next_state = self.validate(copy.deepcopy(state))
        next_state["round"] = max(safe_int(next_state.get("round", 0), 0, minimum=0), safe_int(round_result.get("round", 0), 0, minimum=0))
        if round_result.get("category") and round_result.get("category") != "unknown":
            next_state["category"] = round_result["category"]
        if round_result.get("phase_after"):
            next_state["phase"] = round_result["phase_after"]
        append_unique(next_state["candidate_flags"], round_result.get("candidate_flags", []))
        append_unique(next_state["evidence_records"], round_result.get("evidence_records", []))
        append_unique(next_state["do_not_repeat"], round_result.get("do_not_repeat", []))
        append_unique(next_state["recent_docs"], flatten_docs(round_result.get("recommended_docs_next", [])), max_items=12)

        loop = round_result.get("loop") or {}
        research_loop = next_state.setdefault("research_loop", copy.deepcopy(DEFAULT_STATE["research_loop"]))
        if loop.get("research_question"):
            research_loop["current_question"] = loop["research_question"]
        if loop.get("hypothesis"):
            research_loop["current_hypothesis"] = loop["hypothesis"]
            append_unique(next_state["hypotheses"], [loop["hypothesis"]])
        if loop.get("experiment"):
            research_loop["last_action"] = loop["experiment"]
        if loop.get("conclusion"):
            append_unique(research_loop["known_facts"], [loop["conclusion"]])
        if loop.get("next_experiment"):
            research_loop["next_experiment"] = loop["next_experiment"]
            next_state["next_plan"] = loop["next_experiment"]
        if loop.get("evidence"):
            append_unique(research_loop["evidence_collected"], loop["evidence"])
        state_delta = loop.get("state_delta") or {}
        if state_delta.get("active_strategy"):
            research_loop["active_strategy"] = state_delta["active_strategy"]
        append_unique(research_loop["open_questions"], state_delta.get("open_questions_added", []))
        append_unique(research_loop["falsified_hypotheses"], state_delta.get("falsified_hypotheses_added", []))

        observations = round_result.get("observations") or loop.get("observation") or []
        if observations:
            next_state["last_observation"] = observations[-1]
            research_loop["last_observation"] = observations[-1]
        if round_result.get("next_plan"):
            next_state["next_plan"] = round_result["next_plan"]

        failure_reason = round_result.get("failure_reason")
        if failure_reason:
            next_state["failures"].append(
                {
                    "round": round_result.get("round"),
                    "phase": round_result.get("phase_after") or round_result.get("phase_before"),
                    "reason": failure_reason,
                    "observation": next_state.get("last_observation", ""),
                    "timestamp": utc_now(),
                }
            )

        artifacts = next_state.setdefault("artifacts", {"scripts": [], "logs": [], "evidence": [], "subtasks": []})
        for artifact in round_result.get("new_artifacts", []):
            bucket = artifact_bucket(artifact)
            append_unique(artifacts.setdefault(bucket, []), [artifact])
        for subtask in round_result.get("subtasks", []):
            result_path = subtask.get("result_path")
            if result_path:
                append_unique(artifacts.setdefault("subtasks", []), [result_path])
                merge_subtask_result(self.workspace, result_path, next_state, research_loop)

        if round_result.get("status") == "solved" and round_result.get("confirmed_flag"):
            next_state["solved"] = True
            next_state["phase"] = "solved"
            next_state["confirmed_flag"] = round_result["confirmed_flag"]

        self.save(next_state)
        return next_state

    def validate(self, state: dict[str, Any]) -> dict[str, Any]:
        raw_state = state or {}
        merged = self.deep_merge(copy.deepcopy(DEFAULT_STATE), state or {})
        merged.setdefault("artifacts", {})
        for key in ["scripts", "logs", "evidence"]:
            merged["artifacts"].setdefault(key, [])
        merged["artifacts"].setdefault("subtasks", [])
        merged.setdefault("research_loop", {})
        merged["research_loop"] = self.deep_merge(copy.deepcopy(DEFAULT_STATE["research_loop"]), merged["research_loop"])
        legacy_limits = merged.pop("bud" "gets", {})
        merged.pop("context_" + "bud" + "get", None)
        merged.setdefault("sync", {})
        merged["sync"] = self.deep_merge(copy.deepcopy(DEFAULT_STATE["sync"]), merged["sync"])
        merged["sync"]["enabled"] = str(os.environ.get("SYNC_ENABLED", str(merged["sync"].get("enabled", True)))).lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
        merged.setdefault("allowed_scope", {})
        for key in ["targets", "hosts", "ports", "urls"]:
            merged["allowed_scope"].setdefault(key, [])
        merged.setdefault("runtime_limits", {})
        if isinstance(legacy_limits, dict) and not isinstance(raw_state.get("runtime_limits"), dict):
            for key in ["max_rounds", "max_seconds", "max_command_seconds"]:
                if key in legacy_limits:
                    merged["runtime_limits"][key] = legacy_limits[key]
        merged["runtime_limits"] = self.deep_merge(copy.deepcopy(DEFAULT_STATE["runtime_limits"]), merged["runtime_limits"])
        if "AIXCTF_MAX_SECONDS" not in os.environ and safe_int(merged["runtime_limits"].get("max_seconds", 0), 0) == 1800:
            merged["runtime_limits"]["max_seconds"] = DEFAULT_STATE["runtime_limits"]["max_seconds"]
        if "AIXCTF_MAX_CMD_SECONDS" not in os.environ and safe_int(merged["runtime_limits"].get("max_command_seconds", 0), 0) in {120, 600}:
            merged["runtime_limits"]["max_command_seconds"] = DEFAULT_STATE["runtime_limits"]["max_command_seconds"]
        merged["runtime_limits"]["max_rounds"] = safe_int(
            os.environ.get("AIXCTF_MAX_ROUNDS", merged["runtime_limits"].get("max_rounds", 12)), 12, minimum=1
        )
        merged["runtime_limits"]["max_seconds"] = safe_int(
            os.environ.get("AIXCTF_MAX_SECONDS", merged["runtime_limits"].get("max_seconds", 7200)), 7200, minimum=1
        )
        merged["runtime_limits"]["max_command_seconds"] = safe_int(
            os.environ.get("AIXCTF_MAX_CMD_SECONDS", merged["runtime_limits"].get("max_command_seconds", 7200)), 7200, minimum=1
        )
        return merged

    @staticmethod
    def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                base[key] = StateStore.deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as fh:
            value = json.load(fh)
        if not isinstance(value, dict):
            raise ValueError(f"state file must contain an object: {path}")
        return value

    def recover_from_unreadable_state(self, initial: dict[str, Any] | None, exc: Exception) -> dict[str, Any]:
        backup_path = self.path.with_name(f"{self.path.name}.corrupt.{compact_timestamp()}")
        backup_note = f"backup_failed:{backup_path}"
        try:
            self.path.replace(backup_path)
            backup_note = f"backed_up_to:{backup_path}"
        except OSError:
            pass

        state = copy.deepcopy(DEFAULT_STATE)
        if initial:
            state = self.deep_merge(state, initial)
        now = utc_now()
        state["created_at"] = now
        state["updated_at"] = now
        state.setdefault("failures", []).append(
            {
                "round": 0,
                "phase": "init",
                "reason": f"state_recovered:{type(exc).__name__}",
                "observation": f"{exc}; {backup_note}",
                "timestamp": now,
            }
        )
        state.setdefault("scheduler", {})["pause_reason"] = "state_recovered"
        state = self.validate(state)
        try:
            self.save(state)
        except OSError:
            pass
        return state

    @staticmethod
    def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        tmp.replace(path)


def append_unique(target: list[Any], values: list[Any], max_items: int | None = None) -> None:
    for value in values or []:
        if value not in target:
            target.append(value)
    if max_items and len(target) > max_items:
        del target[: len(target) - max_items]


def artifact_bucket(path: str) -> str:
    if path.startswith("subtasks/"):
        return "subtasks"
    if path.startswith("scripts/"):
        return "scripts"
    if path.startswith("evidence/"):
        return "evidence"
    return "logs"


def flatten_docs(value: Any) -> list[str]:
    if isinstance(value, dict):
        docs: list[str] = []
        for items in value.values():
            docs.extend(flatten_docs(items))
        return docs
    if isinstance(value, list):
        docs = []
        for item in value:
            docs.extend(flatten_docs(item))
        return docs
    if isinstance(value, str):
        return [value]
    return []


def merge_subtask_result(workspace: Path, result_path: str, state: dict[str, Any], research_loop: dict[str, Any]) -> None:
    path = workspace / result_path
    if not path.exists():
        append_unique(research_loop.setdefault("open_questions", []), [f"Missing subtask result: {result_path}"])
        return
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        append_unique(research_loop.setdefault("open_questions", []), [f"Unparseable subtask result: {result_path}"])
        return

    status = result.get("status")
    if status == "confirmed":
        append_unique(research_loop.setdefault("known_facts", []), result.get("facts_added", []))
        for evidence in result.get("evidence", []):
            evidence_path = evidence.get("path") if isinstance(evidence, dict) else evidence
            if evidence_path:
                evidence_text = str(evidence_path)
                append_unique(research_loop.setdefault("evidence_collected", []), [evidence_text[:500]])
                artifact_path = workspace_artifact_path(workspace, evidence_text)
                if artifact_path:
                    append_unique(state.setdefault("artifacts", {}).setdefault(artifact_bucket(artifact_path), []), [artifact_path])
    elif status == "falsified":
        append_unique(research_loop.setdefault("falsified_hypotheses", []), result.get("hypotheses_falsified", []))
    else:
        recommendation = result.get("next_recommendation")
        if recommendation:
            append_unique(research_loop.setdefault("open_questions", []), [recommendation])

    append_unique(state.setdefault("do_not_repeat", []), result.get("do_not_repeat", []))


def workspace_artifact_path(workspace: Path, raw_path: str) -> str | None:
    raw_path = raw_path.strip()
    if not raw_path or "\n" in raw_path or len(raw_path) > 400:
        return None
    path = Path(raw_path)
    try:
        rel = path.resolve().relative_to(workspace.resolve()) if path.is_absolute() else path
    except ValueError:
        return None
    if rel.is_absolute() or ".." in rel.parts:
        return None
    if not rel.parts or rel.parts[0] not in {"logs", "evidence", "scripts", "subtasks"}:
        return None
    if not (workspace / rel).exists():
        return None
    return str(rel)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def safe_int(value: Any, default: int, minimum: int | None = None) -> int:
    try:
        parsed = int(value if value is not None else default)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        return max(minimum, parsed)
    return parsed
