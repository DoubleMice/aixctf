from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runner.state_store import append_unique


class HandoffCollector:
    def __init__(self, workspace: Path):
        self.workspace = workspace

    def merge_subtasks(self, state: dict[str, Any], subtasks: list[dict[str, Any]]) -> dict[str, Any]:
        research = state.setdefault("research_loop", {})
        for subtask in subtasks:
            result_path = subtask.get("result_path")
            if not result_path:
                continue
            path = self.workspace / result_path
            if not path.exists():
                continue
            try:
                result = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if result.get("status") == "confirmed":
                append_unique(research.setdefault("known_facts", []), result.get("facts_added", []))
            elif result.get("status") == "falsified":
                append_unique(research.setdefault("falsified_hypotheses", []), result.get("hypotheses_falsified", []))
            else:
                recommendation = result.get("next_recommendation")
                if recommendation:
                    append_unique(research.setdefault("open_questions", []), [recommendation])
            append_unique(state.setdefault("do_not_repeat", []), result.get("do_not_repeat", []))
        return state
