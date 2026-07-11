from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


CHALLENGE_HANDOFF_PROTOCOL = "aixctf.challenge-handoff/v1"
TASK_HANDOFF_PROTOCOL = "aixctf.task-handoff/v1"


def new_execution(round_id: int) -> dict[str, Any]:
    return {
        "execution_id": f"exec_{round_id:03d}_{uuid.uuid4().hex[:12]}",
        "started_at_ns": time.time_ns(),
    }


def handoff_updated_since(workspace: Path, started_at_ns: int) -> bool:
    handoff = workspace / "handoff.md"
    try:
        return handoff.is_file() and handoff.stat().st_size > 0 and handoff.stat().st_mtime_ns > started_at_ns
    except OSError:
        return False


def handoff_for_prompt(workspace: Path, max_chars: int = 16000) -> str:
    path = workspace / "handoff.md"
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "No handoff is available. Reconstruct the current research state from state.json and durable artifacts."
    if len(content) <= max_chars:
        return content
    head = content[:4000]
    tail = content[-(max_chars - 4000) :]
    return f"{head}\n\n[... middle of handoff omitted by runtime ...]\n\n{tail}"


def recovery_notice(workspace: Path, max_lines: int = 1000) -> str:
    events = read_progress_events(workspace / "progress.jsonl", max_lines=max_lines)
    if not events:
        return ""

    starts: list[dict[str, Any]] = []
    completions: dict[str, dict[str, Any]] = {}
    for event in events:
        execution_id = str(event.get("execution_id") or "")
        if not execution_id:
            continue
        if event.get("event") == "execution_started":
            starts.append(event)
        elif event.get("event") == "execution_completed":
            completions[execution_id] = event

    if not starts:
        return ""
    event = starts[-1]
    execution_id = str(event.get("execution_id"))
    completion = completions.get(execution_id)
    if completion is None:
        return (
            f"Execution {event.get('execution_id')} started for round {event.get('round')} but has no matching "
            "execution_completed event. Treat the current handoff as potentially stale, inspect newer events/logs/"
            "scripts/evidence, reconcile durable observations, update handoff.md, and then continue."
        )
    if completion.get("checkpoint_status") == "incomplete":
        return (
            f"Execution {completion.get('execution_id')} ended without updating handoff.md. Reconcile state.json "
            "with newer events/logs/scripts/evidence and update handoff.md before continuing tactical work."
        )
    return ""


def read_progress_events(path: Path, max_lines: int = 1000) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_lines:]
    except OSError:
        return []
    events: list[dict[str, Any]] = []
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events
