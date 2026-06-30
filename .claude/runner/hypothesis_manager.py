from __future__ import annotations

from runner.state_store import append_unique


class HypothesisManager:
    def record(self, state: dict, hypothesis: str | None, conclusion: str | None) -> dict:
        if hypothesis:
            append_unique(state.setdefault("hypotheses", []), [hypothesis])
        if conclusion and "falsified" in conclusion.lower():
            append_unique(state.setdefault("research_loop", {}).setdefault("falsified_hypotheses", []), [hypothesis])
        return state
