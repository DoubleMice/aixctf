from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hooks.hook_io import command_from_payload, is_native_task_tool, tool_input, tool_name, tool_output_text
from runner.event_store import EventStore, signals_from_text
from runner.paths import workspace_root
from runner.state_store import StateStore, append_unique
from sync.sync_queue import SyncQueue
from tools.flag_utils import extract_flags, redact_flags


def check(payload: dict) -> dict:
    workspace = workspace_root()
    state_store = StateStore(workspace)
    state = state_store.load_or_create()
    round_id = EventStore(workspace).current_round()
    name = tool_name(payload)
    command = command_from_payload(payload)
    stdout, stderr = tool_output_text(payload)
    combined = stdout + "\n" + stderr
    flags = extract_flags(combined)
    signals = signals_from_text(combined)
    task_record = persist_task_result(workspace, round_id, name, tool_input(payload), stdout, stderr) if is_native_task_tool(name) else {}
    redacted_preview = redact_flags(combined).strip()[:800]

    log_rel = f"logs/round_{round_id:03d}_tool_{timestamp_slug()}.log"
    log_path = workspace / log_rel
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(render_transcript(command, stdout, stderr), encoding="utf-8", errors="replace")

    evidence_rel = None
    evidence_meta_rel = None
    if flags:
        evidence_rel = f"evidence/round_{round_id:03d}_candidate_flag_{timestamp_slug()}.log"
        evidence_path = workspace / evidence_rel
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(render_transcript(command, stdout, stderr), encoding="utf-8", errors="replace")
        evidence_meta_rel = evidence_rel.removesuffix(".log") + ".json"
        evidence_meta_path = workspace / evidence_meta_rel
        evidence_meta_path.write_text(
            json.dumps(
                {
                    "round": round_id,
                    "tool": name,
                    "command": command,
                    "artifact": evidence_rel,
                    "candidate_flags": flags,
                    "source": "PostToolUse",
                    "log_path": log_rel,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    event = {
        "tool": name,
        "tool_input": tool_input(payload),
        "command": command,
        "post_check": {
            "signals": ["candidate_flag"] * bool(flags) + signals,
            "candidate_flags": flags,
            "log_path": log_rel,
            "evidence_path": evidence_rel,
            "evidence_meta_path": evidence_meta_rel,
            "task_dir": task_record.get("task_dir"),
            "task_result_path": task_record.get("result_path"),
            "task_handoff_path": task_record.get("handoff_path"),
            "summary": summarize(flags, signals),
        },
    }
    EventStore(workspace).append(round_id, event)
    sync_queue = SyncQueue(workspace)
    sync_queue.emit_simple(
        source="hook",
        event_type="tool_finished",
        level="info",
        round_id=round_id,
        phase=state.get("phase"),
        category=state.get("category"),
        message=summarize(flags, signals),
        summary={"command": command, "signals": signals, "output_preview": redacted_preview},
        artifacts=[log_rel],
        hook="PostToolUse",
        tool=name,
    )
    if task_record:
        result_payload = task_record.get("result") or {}
        sync_queue.emit_simple(
            source="hook",
            event_type="subtask_completed" if result_payload.get("status") in {"confirmed", "falsified", "inconclusive"} else "subtask_blocked",
            level="info" if result_payload.get("status") in {"confirmed", "falsified", "inconclusive"} else "warning",
            round_id=round_id,
            phase=state.get("phase"),
            category=state.get("category"),
            message=f"Native Task subagent finished with status {result_payload.get('status', 'unknown')}.",
            summary={"conclusion": result_payload.get("conclusion"), "task": task_record.get("task_dir")},
            artifacts=[value for value in [task_record.get("result_path"), task_record.get("handoff_path")] if value],
            hook="PostToolUse",
            tool=name,
        )
    if signals:
        sync_queue.emit_simple(
            source="hook",
            event_type="failure_signal_detected",
            level="warning",
            round_id=round_id,
            phase=state.get("phase"),
            category=state.get("category"),
            message=f"Failure signal detected: {', '.join(signals)}",
            summary={"command": command, "signals": signals, "output_preview": redacted_preview},
            artifacts=[log_rel],
            hook="PostToolUse",
            tool=name,
        )
    if flags:
        sync_queue.emit_simple(
            source="hook",
            event_type="candidate_flag_found",
            level="success",
            round_id=round_id,
            phase=state.get("phase"),
            category=state.get("category"),
            message="Candidate flag found in tool output.",
            summary={"command": command, "candidate_flags_redacted": len(flags)},
            artifacts=[artifact for artifact in [log_rel, evidence_rel] if artifact],
            hook="PostToolUse",
            tool=name,
        )

    if flags:
        append_unique(state["candidate_flags"], flags)
        append_unique(state["artifacts"].setdefault("evidence", []), [evidence_rel])
        append_unique(state["artifacts"].setdefault("evidence", []), [evidence_meta_rel])
        append_unique(
            state.setdefault("evidence_records", []),
            [
                {
                    "round": round_id,
                    "tool": name,
                    "command": command,
                    "artifact": evidence_rel,
                    "metadata": evidence_meta_rel,
                    "candidate_flags": flags,
                    "source": "PostToolUse",
                }
            ],
        )
    append_unique(state["artifacts"].setdefault("logs", []), [log_rel])
    if task_record.get("result_path"):
        append_unique(state["artifacts"].setdefault("subtasks", []), [task_record["result_path"]])
    if signals:
        state["failures"].append({"round": round_id, "reason": ",".join(signals), "timestamp": datetime.now(timezone.utc).isoformat()})
    if combined.strip():
        state["last_observation"] = combined.strip()[:500]
    state_store.save(state)
    return {"flags": flags, "signals": signals, "log_path": log_rel, "evidence_path": evidence_rel}


def render_transcript(command: str, stdout: str, stderr: str) -> str:
    return f"$ {command}\n\n[stdout]\n{stdout}\n\n[stderr]\n{stderr}\n"


def persist_task_result(workspace: Path, round_id: int, tool: str, input_data: dict[str, Any], stdout: str, stderr: str) -> dict[str, Any]:
    task_dir = next_task_dir(workspace)
    task_dir.mkdir(parents=True, exist_ok=True)
    write_json(task_dir / "input.json", {"round": round_id, "tool": tool, "tool_input": input_data, "timestamp": datetime.now(timezone.utc).isoformat()})
    output = render_transcript(command_from_payload({"tool": tool, "tool_input": input_data}), stdout, stderr)
    (task_dir / "output.md").write_text(output, encoding="utf-8", errors="replace")
    parsed = parse_json_object(stdout) or parse_json_object(stderr)
    result = normalize_task_result(task_dir.name, input_data, parsed, stdout, stderr)
    write_json(task_dir / "result.json", result)
    (task_dir / "handoff.md").write_text(render_task_handoff(input_data, result), encoding="utf-8")
    rel_dir = str(task_dir.relative_to(workspace))
    return {
        "task_dir": rel_dir,
        "result_path": f"{rel_dir}/result.json",
        "handoff_path": f"{rel_dir}/handoff.md",
        "output_path": f"{rel_dir}/output.md",
        "result": result,
    }


def next_task_dir(workspace: Path) -> Path:
    subtasks_dir = workspace / "subtasks"
    subtasks_dir.mkdir(parents=True, exist_ok=True)
    count = len(list(subtasks_dir.glob("task_*"))) + 1
    return subtasks_dir / f"task_{count:03d}"


def normalize_task_result(task_id: str, input_data: dict[str, Any], parsed: dict[str, Any], stdout: str, stderr: str) -> dict[str, Any]:
    raw_status = str(parsed.get("status") or "").lower()
    status = raw_status if raw_status in {"confirmed", "falsified", "inconclusive", "blocked"} else "inconclusive"
    conclusion = parsed.get("conclusion") or first_nonempty_line(stdout) or first_nonempty_line(stderr) or "Native Task completed without a parseable conclusion."
    return {
        "subtask_id": task_id,
        "type": "claudecode_native_task",
        "agent_type": input_data.get("subagent_type") or input_data.get("agent_type") or input_data.get("type") or "general-purpose",
        "status": status,
        "conclusion": conclusion,
        "confidence": safe_float(parsed.get("confidence"), 0.0),
        "evidence": list_value(parsed.get("evidence")),
        "facts_added": list_value(parsed.get("facts_added") or parsed.get("known_facts")),
        "hypotheses_falsified": list_value(parsed.get("hypotheses_falsified")),
        "next_recommendation": parsed.get("next_recommendation") or parsed.get("next_experiment") or "",
        "do_not_repeat": list_value(parsed.get("do_not_repeat")),
    }


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return default


def list_value(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def render_task_handoff(input_data: dict[str, Any], result: dict[str, Any]) -> str:
    return f"""# Native Task Handoff

## Description

{input_data.get('description') or input_data.get('task') or 'n/a'}

## Status

{result.get('status')}

## Conclusion

{result.get('conclusion')}

## Next Recommendation

{result.get('next_recommendation') or 'n/a'}
"""


def parse_json_object(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        pass
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    for candidate in reversed(fenced):
        try:
            value = json.loads(candidate)
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            continue
    start = text.rfind("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            value = json.loads(text[start : end + 1])
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def first_nonempty_line(text: str) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()[:500]
    return ""


def write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def summarize(flags: list[str], signals: list[str]) -> str:
    parts = []
    if flags:
        parts.append(f"candidate flags: {len(flags)} redacted")
    if signals:
        parts.append(f"signals: {', '.join(signals)}")
    return "; ".join(parts) if parts else "tool output recorded"


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
