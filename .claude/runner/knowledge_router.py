from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


class KnowledgeRouter:
    def __init__(self, agent_root: Path):
        self.agent_root = agent_root
        self.index_path = agent_root / "docs" / "knowledge_index.yaml"
        if not self.index_path.exists():
            self.index_path = agent_root / "docs" / "skill_index.yaml"
        self.index = self._load_index()

    def select(self, state: dict[str, Any], last_round: dict[str, Any] | None = None) -> dict[str, list[str]]:
        category = state.get("category", "unknown")
        selected = {
            "templates": [self.template_for(category)],
            "skills": self._select_group("skills", state, last_round, limit=2),
            "tools": self._select_group("tool_docs", state, last_round, limit=2),
            "debug": self._select_group("debug_docs", state, last_round, limit=1),
            "handoff": self._select_group("handoff_docs", state, last_round, limit=1),
        }
        if not selected["handoff"]:
            selected["handoff"] = ["docs/handoff/evidence_standard.md"]
        return selected

    def select_docs(self, state: dict[str, Any], last_round: dict[str, Any] | None = None, limit: int = 3) -> list[str]:
        grouped = self.select(state, last_round)
        docs: list[str] = []
        for key in ["skills", "tools", "debug", "handoff"]:
            docs.extend(grouped.get(key, []))
        return docs[:limit] or ["docs/handoff/evidence_standard.md"]

    def template_for(self, category: str) -> str:
        if category == "pwn":
            return "templates/pwn.md"
        if category == "web":
            return "templates/web.md"
        return "templates/generic.md"

    def read_doc_excerpt(self, relative_path: str, limit: int = 6000) -> str:
        path = self.agent_root / relative_path
        if not path.exists():
            return f"[missing doc: {relative_path}]"
        try:
            return path.read_text(encoding="utf-8", errors="replace")[:limit]
        except OSError as exc:
            return f"[unreadable doc: {relative_path}: {exc}]"

    def _load_index(self) -> dict[str, Any]:
        if not self.index_path.exists() or yaml is None:
            return {}
        try:
            data = yaml.safe_load(self.index_path.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        for key in ["skills", "tool_docs", "debug_docs", "handoff_docs"]:
            data.setdefault(key, [])
        return data

    def _select_group(self, group: str, state: dict[str, Any], last_round: dict[str, Any] | None, limit: int) -> list[str]:
        docs = []
        text = state_text(state, last_round)
        for doc in self.index.get(group, []):
            if not isinstance(doc, dict) or not doc.get("file"):
                continue
            score = score_doc(doc, state, text)
            if score > 0:
                docs.append((score, doc["file"]))
        docs.sort(key=lambda item: (-item[0], item[1]))
        selected = []
        for _, file_name in docs:
            if file_name not in selected:
                selected.append(file_name)
            if len(selected) >= limit:
                break
        return selected


def score_doc(doc: dict[str, Any], state: dict[str, Any], text: str) -> int:
    score = 0
    if doc.get("category") and doc.get("category") == state.get("category"):
        score += 3
    if doc.get("phase") and doc.get("phase") == state.get("phase"):
        score += 2
    for trigger in doc.get("triggers", []):
        if str(trigger).lower() in text:
            score += 2
    if doc.get("file") in state.get("recent_docs", []):
        score -= 2
    return score


def state_text(state: dict[str, Any], last_round: dict[str, Any] | None = None) -> str:
    research = state.get("research_loop", {})
    parts = [
        state.get("category", ""),
        state.get("phase", ""),
        state.get("last_observation", ""),
        state.get("next_plan", ""),
        research.get("current_question") or "",
        research.get("current_hypothesis") or "",
        research.get("active_strategy") or "",
        " ".join(str(item) for item in research.get("known_facts", [])),
        " ".join(str(item) for item in research.get("open_questions", [])),
        " ".join(str(item) for item in state.get("failures", [])),
        " ".join(str(item) for item in state.get("do_not_repeat", [])),
    ]
    if last_round:
        loop = last_round.get("loop", {})
        parts.extend(str(item) for item in loop.get("observation", []))
        parts.append(loop.get("conclusion", ""))
    return "\n".join(parts).lower()
