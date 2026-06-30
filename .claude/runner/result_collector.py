from __future__ import annotations

import json
import shutil
from pathlib import Path

from hooks.evidence_guard import validate_final_state


class ResultCollector:
    def __init__(self, workspace: Path, output_dir: Path):
        self.workspace = workspace
        self.output_dir = output_dir

    def write_result(self, state: dict) -> dict:
        solved = bool(state.get("solved") and state.get("confirmed_flag"))
        try:
            guard = validate_final_state(self.workspace, state, final=True)
        except Exception as exc:
            guard = {"ok": False, "reason": f"result_validation_error:{type(exc).__name__}:{exc}"}
        status = "solved" if solved and guard["ok"] else "failed"
        artifacts = safe_collect_artifacts(self.workspace, state)
        evidence = safe_evidence_entries(self.workspace, state) if status == "solved" else []
        result = {
            "status": status,
            "challenge_id": state.get("challenge_id", "unknown"),
            "category": state.get("category", "unknown"),
            "phase": state.get("phase", "unknown"),
            "scheduler": state.get("scheduler", {}),
            "flag": state.get("confirmed_flag") if status == "solved" else None,
            "confidence": 0.95 if status == "solved" else 0.0,
            "evidence": evidence,
            "artifacts": artifacts,
            "rounds": state.get("round", 0),
            "failure_reason": None if status == "solved" else failure_reason(state, guard),
        }
        workspace_result = self.workspace / "result.json"
        warnings = []
        workspace_written = False
        try:
            atomic_write_json(workspace_result, result)
            workspace_written = True
        except OSError as exc:
            warnings.append(f"could not write workspace result: {exc}")
        try:
            if workspace_written:
                self.output_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(workspace_result, self.output_dir / "result.json")
            else:
                atomic_write_json(self.output_dir / "result.json", result)
        except OSError as exc:
            warnings.append(f"could not write output result to {self.output_dir}: {exc}")
        if warnings:
            result["write_warnings"] = warnings
            for path in [workspace_result, self.output_dir / "result.json"]:
                try:
                    atomic_write_json(path, result)
                except OSError:
                    pass
        return result


def evidence_entries(workspace: Path, state: dict) -> list[dict]:
    entries = []
    for rel in state.get("artifacts", {}).get("evidence", []):
        if not artifact_exists(workspace, rel):
            continue
        path = workspace / rel
        if path.suffix != ".json":
            record = evidence_record_for(state, rel)
            entries.append(
                {
                    "type": "command_transcript",
                    "path": rel,
                    "summary": "artifact contains confirmed flag evidence",
                    "command": record.get("command") if record else None,
                    "tool": record.get("tool") if record else None,
                    "metadata": record.get("metadata") if record else None,
                }
            )
    return entries


def evidence_record_for(state: dict, artifact: str) -> dict | None:
    for record in state.get("evidence_records", []):
        if record.get("artifact") == artifact:
            return record
    return None


def collect_artifacts(workspace: Path, state: dict) -> list[str]:
    artifacts = ["notes.md", "handoff.md"]
    for fixed in ["status.json", "progress.jsonl", "sync/events.jsonl", "sync/spool.jsonl", "sync/sync_log.jsonl"]:
        if (workspace / fixed).exists():
            artifacts.append(fixed)
    for bucket in ["scripts", "logs", "evidence"]:
        artifacts.extend(artifact for artifact in state.get("artifacts", {}).get(bucket, []) if artifact_exists(workspace, artifact))
    artifacts.extend(artifact for artifact in state.get("artifacts", {}).get("subtasks", []) if artifact_exists(workspace, artifact))
    artifacts.extend(str(path.relative_to(workspace)) for path in sorted((workspace / "rounds").glob("round_*.json")))
    artifacts.extend(str(path.relative_to(workspace)) for path in sorted((workspace / "subtasks").glob("task_*/*")))
    return sorted(dict.fromkeys(artifact for artifact in artifacts if (workspace / artifact).exists()))


def safe_evidence_entries(workspace: Path, state: dict) -> list[dict]:
    try:
        return evidence_entries(workspace, state)
    except Exception:
        return []


def safe_collect_artifacts(workspace: Path, state: dict) -> list[str]:
    try:
        return collect_artifacts(workspace, state)
    except Exception:
        return []


def artifact_exists(workspace: Path, artifact: str) -> bool:
    path = Path(str(artifact))
    if path.is_absolute() or ".." in path.parts:
        return False
    return (workspace / path).exists()


def failure_reason(state: dict, guard: dict) -> str:
    if not guard["ok"]:
        return guard["reason"]
    failures = state.get("failures", [])
    if failures:
        return failures[-1].get("reason") or "failed_after_iterations"
    return "no_progress_after_iterations"


def atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
