from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class EventStore:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.events_dir = workspace / "events"
        self.disabled_reason: str | None = None
        try:
            self.events_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.disabled_reason = str(exc)

    def append(self, round_id: int, event: dict[str, Any]) -> dict[str, Any]:
        event = dict(event)
        event.setdefault("event_id", self.next_event_id(round_id))
        event.setdefault("round", round_id)
        event.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        if self.disabled_reason:
            event["event_store_warning"] = self.disabled_reason
            return event
        path = self.events_dir / f"round_{round_id:03d}_{event['event_id']}.json"
        try:
            atomic_write_json(path, event)
        except OSError as exc:
            event["event_store_warning"] = str(exc)
        return event

    def collect(self, round_id: int) -> list[dict[str, Any]]:
        events = []
        try:
            paths = sorted(self.events_dir.glob(f"round_{round_id:03d}_*.json"))
        except OSError:
            return events
        for path in paths:
            try:
                events.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                events.append({"event_id": path.stem, "parse_error": str(path)})
        return events

    def next_event_id(self, round_id: int) -> str:
        try:
            count = len(list(self.events_dir.glob(f"round_{round_id:03d}_evt_*.json"))) + 1
        except OSError:
            count = 1
        return f"evt_{count:06d}"

    def current_round(self) -> int:
        env_round = os.environ.get("AIXCTF_ROUND_ID")
        if env_round:
            try:
                return max(1, int(env_round))
            except ValueError:
                pass
        state_path = self.workspace / "state.json"
        if not state_path.exists():
            return 0
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            return int(state.get("round", 0)) + 1
        except Exception:
            return 0


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def event_action(event: dict[str, Any]) -> dict[str, Any]:
    tool = event.get("tool") or event.get("tool_name") or "unknown"
    command = event.get("command") or nested_get(event, ["tool_input", "command"]) or summarize_tool_input(event.get("tool_input") or {})
    result = nested_get(event, ["post_check", "summary"]) or event.get("summary") or ""
    artifact = nested_get(event, ["post_check", "log_path"])
    action = {"type": "tool", "tool": tool, "content": command, "result": result, "artifact": artifact}
    task_result = nested_get(event, ["post_check", "task_result_path"])
    if task_result:
        action["task_result"] = task_result
    return action


def nested_get(data: dict[str, Any], keys: list[str]) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def summarize_tool_input(data: dict[str, Any]) -> str:
    if not isinstance(data, dict):
        return ""
    if data.get("description") or data.get("prompt"):
        agent_type = data.get("subagent_type") or data.get("agent_type") or data.get("type") or "general-purpose"
        description = data.get("description") or ""
        prompt = str(data.get("prompt") or data.get("instructions") or data.get("content") or "").replace("\n", " ").strip()[:240]
        return "; ".join(part for part in [f"subagent_type={agent_type}", f"description={description}" if description else "", f"prompt={prompt}" if prompt else ""] if part)
    return ""


def signals_from_text(text: str) -> list[str]:
    patterns = {
        "crash": r"segmentation fault|core dumped|stack smashing detected",
        "timeout": r"timeout|timed out",
        "eof": r"EOFError|Got EOF|Broken pipe",
        "http_403": r"\b403\b|forbidden",
        "http_404": r"\b404\b|not found",
        "http_500": r"\b500\b|internal server error",
        "sql_error": r"SQL syntax|mysql_fetch|sqlite error|PostgreSQL.*ERROR",
        "template_error": r"TemplateSyntaxError|UndefinedError|jinja2",
        "libc_error": r"GLIBC_|ld-linux|version .* not found",
    }
    found = []
    for name, pattern in patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            found.append(name)
    return found
