from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sync.sync_event import make_event
from tools.flag_utils import redact_flags


class SyncQueue:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.sync_dir = workspace / "sync"
        self.disabled_reason: str | None = None
        try:
            self.sync_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.disabled_reason = str(exc)
        self.events_path = self.sync_dir / "events.jsonl"
        self.spool_path = self.sync_dir / "spool.jsonl"
        self.log_path = self.sync_dir / "sync_log.jsonl"
        if not self.disabled_reason:
            for path in [self.events_path, self.spool_path, self.log_path]:
                try:
                    path.touch(exist_ok=True)
                except OSError as exc:
                    self.disabled_reason = str(exc)
                    break

    def emit(self, event: dict[str, Any]) -> dict[str, Any]:
        event = redact_payload(event)
        if self.disabled_reason:
            event["sync_write_warning"] = self.disabled_reason
            return event
        try:
            append_jsonl(self.events_path, event)
        except OSError as exc:
            event["sync_write_warning"] = str(exc)
        return event

    def emit_simple(self, **kwargs: Any) -> dict[str, Any]:
        return self.emit(make_event(**kwargs))

    def read_events(self, limit: int = 100) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        try:
            lines = self.events_path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
        except OSError:
            return events
        for line in lines:
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events

    def spool(self, payload: dict[str, Any]) -> None:
        payload.setdefault("time", datetime.now(timezone.utc).isoformat())
        if self.disabled_reason:
            return
        try:
            append_jsonl(self.spool_path, redact_payload(payload))
        except OSError:
            pass

    def log(self, payload: dict[str, Any]) -> None:
        payload.setdefault("time", datetime.now(timezone.utc).isoformat())
        if self.disabled_reason:
            return
        try:
            append_jsonl(self.log_path, redact_payload(payload))
        except OSError:
            pass


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def redact_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: redact_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, str):
        return redact_flags(value)
    return value
