from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ProgressExporter:
    def __init__(self, workspace: Path):
        self.path = workspace / "progress.jsonl"
        self.disabled_reason: str | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.touch(exist_ok=True)
        except OSError as exc:
            self.disabled_reason = str(exc)

    def emit(
        self,
        *,
        level: str,
        event: str,
        message: str,
        round_id: int = 0,
        phase: str = "init",
        category: str = "unknown",
        artifacts: list[str] | None = None,
        extra: dict[str, Any] | None = None,
        console: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "time": datetime.now(timezone.utc).isoformat(),
            "level": level.upper(),
            "round": round_id,
            "phase": phase,
            "category": category,
            "event": event,
            "message": message,
            "artifacts": artifacts or [],
        }
        if extra:
            payload.update(extra)
        if self.disabled_reason:
            payload["progress_write_warning"] = self.disabled_reason
        else:
            try:
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
            except OSError as exc:
                self.disabled_reason = str(exc)
                payload["progress_write_warning"] = str(exc)
        line = (
            f"[AIXCTF][{payload['level']}] round={round_id} phase={phase} "
            f"category={category} event={event} msg={json.dumps(message, ensure_ascii=False)}"
        )
        if console:
            try:
                print(line, file=sys.stdout, flush=True)
            except OSError:
                pass
        return payload
