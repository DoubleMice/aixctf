from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class StatusWriter:
    def __init__(self, workspace: Path):
        self.path = workspace / "status.json"

    def write(self, state: dict, event: str, message: str) -> dict:
        status = {
            "time": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "message": message,
            "challenge_id": state.get("challenge_id"),
            "round": state.get("round", 0),
            "phase": state.get("phase", "init"),
            "category": state.get("category", "unknown"),
            "solved": state.get("solved", False),
            "confirmed_flag": state.get("confirmed_flag"),
            "current_question": state.get("research_loop", {}).get("current_question"),
            "next_experiment": state.get("research_loop", {}).get("next_experiment"),
        }
        tmp = self.path.with_suffix(".json.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            status["status_write_warning"] = str(exc)
        return status
