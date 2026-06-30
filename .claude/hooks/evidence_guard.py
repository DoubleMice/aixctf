from __future__ import annotations

from pathlib import Path
import json

from tools.flag_utils import artifact_contains_flag


def validate_final_state(workspace: Path, state: dict, final: bool = False) -> dict:
    solved = bool(state.get("solved") or state.get("phase") == "solved")
    if solved:
        flag = state.get("confirmed_flag")
        if not flag:
            return {"ok": False, "reason": "solved state missing confirmed_flag"}
        evidence = state.get("artifacts", {}).get("evidence", [])
        if not evidence:
            return {"ok": False, "reason": "solved state missing evidence artifact"}
        matching_artifacts = [rel for rel in evidence if artifact_contains_flag(workspace, rel, flag)]
        if not matching_artifacts:
            return {"ok": False, "reason": "no evidence artifact contains confirmed flag"}
        if not has_known_provenance(workspace, state, flag, matching_artifacts):
            return {"ok": False, "reason": "confirmed flag lacks command or script provenance"}
        handoff = workspace / "handoff.md"
        if not handoff.exists() or flag not in handoff.read_text(encoding="utf-8", errors="replace"):
            return {"ok": False, "reason": "handoff.md does not explain flag source"}
        return {"ok": True, "reason": "solved evidence validated"}

    if final:
        if not (workspace / "handoff.md").exists():
            return {"ok": False, "reason": "failed result missing handoff.md"}
        if not (workspace / "notes.md").exists():
            return {"ok": False, "reason": "failed result missing notes.md"}
        if not list((workspace / "rounds").glob("round_*.json")):
            return {"ok": False, "reason": "failed result missing round results"}
    return {"ok": True, "reason": "non-solved state has required artifacts"}


def has_known_provenance(workspace: Path, state: dict, flag: str, matching_artifacts: list[str]) -> bool:
    for record in state.get("evidence_records", []):
        if record.get("artifact") in matching_artifacts and flag in record.get("candidate_flags", []):
            if record.get("command") or record.get("script") or record.get("tool"):
                return True

    if state.get("artifacts", {}).get("scripts"):
        return True

    events_dir = workspace / "events"
    for event_path in events_dir.glob("round_*_*.json"):
        try:
            event = json.loads(event_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        post = event.get("post_check", {})
        if post.get("evidence_path") in matching_artifacts and flag in post.get("candidate_flags", []):
            if event.get("command") or event.get("tool"):
                return True
    return False
